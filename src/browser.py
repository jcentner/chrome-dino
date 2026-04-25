"""Selenium + CDP adapter for `chrome://dino`.

Owns: pinned-version verification, single-call DOM read, CDP key dispatch
(with the §3.5 held-key invariant), score readout via the page's own
formula, game-over detection, episode reset, teardown.

No Gym contract here — that lives in `src.env` (slice 2).
"""

from __future__ import annotations

import re
from typing import Any

# Action constants (also imported by tests and by src.heuristic).
NOOP = 0
JUMP = 1
DUCK = 2

# CDP method + key identifiers.
_CDP_DISPATCH = "Input.dispatchKeyEvent"
_KEYDOWN = "keyDown"
_KEYUP = "keyUp"
_KEY_ARROW_UP = "ArrowUp"
_KEY_ARROW_DOWN = "ArrowDown"
_KEY_SPACE = " "

# CDP requires `code` and `windowsVirtualKeyCode` (which becomes `e.keyCode`
# in the page) for the dino game's onKeyDown/onKeyUp handlers to recognize
# the press. The handlers check `runnerKeycodes.{jump,duck}.includes(keyCode)`
# — without keyCode the event is silently dropped. See chromium-dino-runner
# skill ("Action dispatch via CDP").
_KEY_META: dict[str, tuple[str, int]] = {
    _KEY_SPACE: ("Space", 32),
    _KEY_ARROW_UP: ("ArrowUp", 38),
    _KEY_ARROW_DOWN: ("ArrowDown", 40),
}

# Pinned Chrome major. Lives next to the runtime install at
# C:\chrome-dino-runtime\ (see docs/setup/windows-chrome-pinning.md).
# Set to None to skip the check; set to a major-version int to enforce.
PINNED_CHROME_MAJOR: int | None = 148


class VersionMismatchError(RuntimeError):
    """Raised by `Browser.version_check` when the live Chrome major does not
    match `PINNED_CHROME_MAJOR`."""


# JS one-liner that returns the full §3.4 raw state as a dict. Read in a
# single `execute_script` call so the returned snapshot is internally
# consistent (no torn read across two round-trips).
_READ_STATE_JS = r"""
const r = (typeof Runner !== 'undefined' && typeof Runner.getInstance === 'function')
  ? (function(){ try { return Runner.getInstance(); } catch (e) { return null; } })()
  : (typeof Runner !== 'undefined' ? Runner.instance_ : null);
if (!r) { return null; }
const t = r.tRex;
const obs = (r.horizon && r.horizon.obstacles) ? r.horizon.obstacles : [];
function obstacle(o) {
  if (!o) { return null; }
  return {
    xPos: o.xPos,
    yPos: o.yPos,
    width: o.width,
    height: (o.typeConfig && o.typeConfig.height) || 0,
    type: (o.typeConfig && o.typeConfig.type) || ''
  };
}
return {
  crashed: !!r.crashed,
  playing: !!r.playing,
  activated: !!r.activated,
  currentSpeed: r.currentSpeed,
  distanceRan: r.distanceRan,
  time: r.time,
  canvasWidth: r.dimensions ? (r.dimensions.WIDTH || r.dimensions.width) : null,
  tRex: {
    yPos: t ? t.yPos : null,
    jumping: t ? !!t.jumping : false,
    ducking: t ? !!t.ducking : false
  },
  obstacles: [obstacle(obs[0]), obstacle(obs[1])]
};
"""

# Score formula per components/neterror/resources/dino_game/distance_meter.ts
# getActualDistance(): Math.round(Math.ceil(distanceRan) * 0.025).
# Match the on-screen number exactly. distanceMeter is null pre-init, so fall
# back to computing from distanceRan when needed.
_GET_SCORE_JS = r"""
const r = (typeof Runner !== 'undefined' && typeof Runner.getInstance === 'function')
  ? (function(){ try { return Runner.getInstance(); } catch (e) { return null; } })()
  : (typeof Runner !== 'undefined' ? Runner.instance_ : null);
if (!r) { return 0; }
const d = Math.ceil(r.distanceRan || 0);
if (r.distanceMeter && typeof r.distanceMeter.getActualDistance === 'function') {
  return r.distanceMeter.getActualDistance(d);
}
return d ? Math.round(d * 0.025) : 0;
"""

_GAME_OVER_JS = r"""
const r = (typeof Runner !== 'undefined' && typeof Runner.getInstance === 'function')
  ? (function(){ try { return Runner.getInstance(); } catch (e) { return null; } })()
  : (typeof Runner !== 'undefined' ? Runner.instance_ : null);
return !!(r && r.crashed);
"""

_PLAYING_JS = r"""
const r = (typeof Runner !== 'undefined' && typeof Runner.getInstance === 'function')
  ? (function(){ try { return Runner.getInstance(); } catch (e) { return null; } })()
  : (typeof Runner !== 'undefined' ? Runner.instance_ : null);
return !!(r && r.playing);
"""

_USER_AGENT_JS = "return navigator.userAgent;"


def _parse_chrome_major(user_agent: str) -> int | None:
    """Pull the Chrome major version int out of a userAgent string. Returns
    None if no `Chrome/<int>` token is present.
    """
    m = re.search(r"Chrome/(\d+)\.", user_agent)
    return int(m.group(1)) if m else None


class Browser:
    """Read-only-mostly adapter to a `chrome://dino` page.

    Constructor takes a Selenium WebDriver via DI so unit tests can pass a
    `MagicMock`. Production code calls `Browser.launch()` to construct the
    real driver against the pinned runtime (slice-1 task 1).
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        # §3.5 held-key invariant: track whether ArrowDown / ArrowUp are
        # currently held. ArrowUp must be held through the full jump or the
        # dino-game's `endJump()` truncates the arc to DROP_VELOCITY once
        # `MIN_JUMP_HEIGHT` (~30 px) is reached.
        self._arrow_down_held = False
        self._arrow_up_held = False

    @classmethod
    def launch(cls) -> "Browser":
        """Construct a `Browser` against the pinned runtime.

        Lazy-imports Selenium so unit tests (which inject a `MagicMock`
        driver) don't pay for it. Reads the runtime location from the
        `CHROME_DINO_RUNTIME` env var, defaulting to
        `C:\\chrome-dino-runtime` per ADR-002 / setup doc.
        """
        import os
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        runtime_dir = os.environ.get("CHROME_DINO_RUNTIME", r"C:\chrome-dino-runtime")
        chrome_binary = os.path.join(runtime_dir, "chrome-win64", "chrome.exe")
        chromedriver_binary = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "chromedriver",
            "chromedriver.exe",
        )

        options = Options()
        options.binary_location = chrome_binary
        options.add_argument("--user-data-dir=" + os.path.join(runtime_dir, "profile"))
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")

        service = Service(executable_path=chromedriver_binary)
        driver = webdriver.Chrome(service=service, options=options)
        # Force the page to behave as if it always has focus. Without this,
        # the dino game's `onVisibilityChange` handler (bound to
        # `document.visibilitychange`, `window.blur`, `window.focus`) calls
        # `Runner.stop()` whenever the OS window loses focus or is
        # minimized, flipping `playing` to false mid-episode. The env then
        # observes a frozen game (`currentSpeed=0`, no obstacle motion,
        # `crashed` never becomes true) and the policy steps indefinitely
        # against a paused game. `Emulation.setFocusEmulationEnabled`
        # spoofs the focus state at the renderer level so the game keeps
        # ticking even when the operator alt-tabs to another window during
        # a long training run.
        try:
            driver.execute_cdp_cmd(
                "Emulation.setFocusEmulationEnabled", {"enabled": True}
            )
        except Exception:
            # Best-effort. Older Chrome / non-CDP drivers may lack this
            # domain; the env still works, the operator just must keep the
            # window in the foreground.
            pass
        # Trigger offline mode, then navigate to chrome://dino.
        driver.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {
                "offline": True,
                "latency": 0,
                "downloadThroughput": 0,
                "uploadThroughput": 0,
            },
        )
        try:
            driver.get("chrome://dino")
        except Exception:
            # Some Chrome versions throw on chrome://dino navigation; the
            # canonical fallback is any unreachable URL — Chrome's offline
            # error page hosts the same dino game. Selenium also raises
            # ERR_INTERNET_DISCONNECTED on the offline page itself, which is
            # *exactly the page we want*, so swallow that too.
            try:
                driver.get("http://chrome-dino-offline.invalid/")
            except Exception:
                pass
        return cls(driver=driver)

    # ------------------------------------------------------------------
    # Construction / teardown
    # ------------------------------------------------------------------

    def __enter__(self) -> "Browser":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self._release_held_keys()
        finally:
            self._driver.quit()

    def close(self) -> None:
        """Explicit teardown for non-context-manager usage."""
        self.__exit__(None, None, None)

    # ------------------------------------------------------------------
    # Version pinning
    # ------------------------------------------------------------------

    def version_check(self) -> None:
        """Verify the live Chrome major matches `PINNED_CHROME_MAJOR`.

        Reads `navigator.userAgent` via `execute_script` and parses the
        `Chrome/<major>` token. Falls back to `driver.capabilities`'s
        `browserVersion` if the userAgent doesn't expose a Chrome token.

        Raises `VersionMismatchError` on mismatch, on inability to determine
        the live major, or when `PINNED_CHROME_MAJOR is None` (the pin must
        be configured before any live run — see
        `docs/setup/windows-chrome-pinning.md`).
        """
        live_major: int | None = None
        try:
            ua = self._driver.execute_script(_USER_AGENT_JS)
            if isinstance(ua, str):
                live_major = _parse_chrome_major(ua)
        except Exception:
            live_major = None

        if live_major is None:
            caps = getattr(self._driver, "capabilities", None) or {}
            bv = caps.get("browserVersion") or caps.get("version") or ""
            if isinstance(bv, str) and bv:
                head = bv.split(".", 1)[0]
                if head.isdigit():
                    live_major = int(head)

        if live_major != PINNED_CHROME_MAJOR:
            raise VersionMismatchError(
                f"Chrome major mismatch: pinned={PINNED_CHROME_MAJOR}, "
                f"live={live_major!r}"
            )    # ------------------------------------------------------------------
    # State reads
    # ------------------------------------------------------------------

    def read_state(self) -> dict:
        """Return the §3.4 raw DOM-state dict in a single round-trip."""
        return self._driver.execute_script(_READ_STATE_JS)

    def get_score(self) -> int:
        """Return the page's currently displayed integer score."""
        v = self._driver.execute_script(_GET_SCORE_JS)
        return int(v)

    def is_game_over(self) -> bool:
        return bool(self._driver.execute_script(_GAME_OVER_JS))

    # ------------------------------------------------------------------
    # Action dispatch (§3.5 invariant)
    # ------------------------------------------------------------------

    def send_action(self, action: int) -> None:
        """Dispatch one action via CDP `Input.dispatchKeyEvent`.

        Invariant: any action that is NOT DUCK first releases held
        `ArrowDown` if it is currently down. DUCK presses `ArrowDown` once;
        repeated DUCK does not re-press while already held.

        JUMP holds `ArrowUp` down on first call and only releases it when a
        non-JUMP action follows. Releasing immediately after keyDown
        truncates the dino's jump arc once `MIN_JUMP_HEIGHT` is reached
        (the page's `endJump()` caps velocity at `DROP_VELOCITY=-5`).
        """
        if action != DUCK and self._arrow_down_held:
            self._dispatch_key(_KEYUP, _KEY_ARROW_DOWN)
            self._arrow_down_held = False
        if action != JUMP and self._arrow_up_held:
            self._dispatch_key(_KEYUP, _KEY_ARROW_UP)
            self._arrow_up_held = False

        if action == NOOP:
            return
        if action == JUMP:
            if not self._arrow_up_held:
                self._dispatch_key(_KEYDOWN, _KEY_ARROW_UP)
                self._arrow_up_held = True
            return
        if action == DUCK:
            if not self._arrow_down_held:
                self._dispatch_key(_KEYDOWN, _KEY_ARROW_DOWN)
                self._arrow_down_held = True
            return
        raise ValueError(f"unknown action: {action!r}")

    # ------------------------------------------------------------------
    # Episode reset (§3.5 invariant)
    # ------------------------------------------------------------------

    def reset_episode(self) -> None:
        """Begin a new episode.

        \u00a73.5 invariant: release any held `ArrowDown` BEFORE dispatching the
        Space that starts the new run. Does not block on `Runner.playing`
        in the unit-test path; the live-browser path waits via `is_game_over`
        polling at the eval-loop level (kept out of the adapter to keep the
        adapter testable without a real timer).

        If the live page exposes a `Runner` instance and the game is not
        crashed, force `gameOver()` first so that the subsequent `Space`
        triggers a real `restart()` (otherwise Space is a no-op once the
        dino is already running).
        """
        self._release_held_keys()
        try:
            self._driver.execute_script(
                "const r = (typeof Runner !== 'undefined' && Runner.getInstance) ? "
                "(function(){try{return Runner.getInstance();}catch(e){return null;}})() : null; "
                "if (r && r.playing && !r.crashed && typeof r.gameOver === 'function') { r.gameOver(); }"
            )
        except Exception:
            pass
        self._dispatch_key(_KEYDOWN, _KEY_SPACE)
        self._dispatch_key(_KEYUP, _KEY_SPACE)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _release_held_keys(self) -> None:
        """Release every key the adapter currently believes is held. Called
        from action dispatch, reset, and teardown."""
        if self._arrow_down_held:
            try:
                self._dispatch_key(_KEYUP, _KEY_ARROW_DOWN)
            finally:
                self._arrow_down_held = False
        if self._arrow_up_held:
            try:
                self._dispatch_key(_KEYUP, _KEY_ARROW_UP)
            finally:
                self._arrow_up_held = False

    def _dispatch_key(self, type_: str, key: str) -> None:
        code, vkey = _KEY_META[key]
        params = {
            "type": type_,
            "key": key,
            "code": code,
            "windowsVirtualKeyCode": vkey,
        }
        self._driver.execute_cdp_cmd(_CDP_DISPATCH, params)
