"""Selenium + CDP adapter for `chrome://dino`.

Owns: pinned-version verification, single-call DOM read, CDP key dispatch
(with the §3.5 held-key invariant), score readout via the page's own
formula, game-over detection, episode reset, teardown.

No Gym contract here — that lives in `src.env` (slice 2).
"""

from __future__ import annotations

import re
import time
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
// Last-resort wakeup: if the game is paused (playing=false, !crashed) but
// has been activated at least once, resume it before snapshotting state.
// Belt-and-braces against `Browser.launch`'s pre-load visibility pinning;
// see the comment block in `Browser.launch`. Skipped pre-activation so
// the boot-retry loop in `DinoEnv.reset` still observes the legitimate
// pre-kickoff `playing=false` state and dispatches Space.
if (r.activated && !r.playing && !r.crashed && typeof r.play === 'function') {
  try { r.play(); } catch (e) {}
}
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

# Injected via `Page.addScriptToEvaluateOnNewDocument` so it runs BEFORE
# any chrome://dino script. Pins `document.visibilityState='visible'` /
# `document.hidden=false` and intercepts visibility/blur/pagehide events
# at the capture phase before the Runner's own bubble-phase listener can
# call `Runner.stop()`. See `Browser.launch` for context.
_PIN_VISIBILITY_JS = r"""
(function () {
  try {
    Object.defineProperty(document, 'visibilityState',
      { configurable: true, get: function () { return 'visible'; } });
    Object.defineProperty(document, 'hidden',
      { configurable: true, get: function () { return false; } });
    Object.defineProperty(document, 'webkitVisibilityState',
      { configurable: true, get: function () { return 'visible'; } });
    Object.defineProperty(document, 'webkitHidden',
      { configurable: true, get: function () { return false; } });
  } catch (e) { /* property already locked; capture-phase listener still helps */ }
  function swallow(e) {
    try { e.stopImmediatePropagation(); } catch (_) {}
    try { e.stopPropagation(); } catch (_) {}
  }
  // Capture phase fires before any bubble-phase listener.
  document.addEventListener('visibilitychange', swallow, true);
  document.addEventListener('webkitvisibilitychange', swallow, true);
  window.addEventListener('blur', swallow, true);
  window.addEventListener('pagehide', swallow, true);
  // Override hasFocus too so any code that polls it sees focused.
  try { document.hasFocus = function () { return true; }; } catch (_) {}
})();
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
        # Force the page to behave as if it always has focus. The dino
        # game's `Runner` constructor wires `onVisibilityChange` to
        # `document.visibilitychange`, `window.blur`, and `window.focus`
        # (see chromium-dino-runner skill, "Visibility/focus pitfall").
        # When the OS window loses focus, `Runner.stop()` is called and
        # `playing` flips false mid-episode; the env then observes a
        # frozen game (`currentSpeed=0`, no obstacle motion, `crashed`
        # never becomes true) and steps indefinitely against a paused
        # game. The slice-1 manual eval didn't trip this because the
        # operator watched the window for ~20 episodes; a 4h training
        # run cannot rely on continuous foreground focus.
        #
        # Defense in depth — three independent mitigations:
        #
        # 1. CDP `Emulation.setFocusEmulationEnabled` spoofs focus at the
        #    renderer level (best-effort; not all Chrome builds honor it
        #    reliably for visibility-change events specifically).
        # 2. `Page.addScriptToEvaluateOnNewDocument` injects, BEFORE any
        #    page script runs, a script that pins
        #    `document.visibilityState = 'visible'` /
        #    `document.hidden = false` and registers capture-phase
        #    `visibilitychange` / `blur` / `pagehide` listeners that call
        #    `stopImmediatePropagation` so the Runner's bubble-phase
        #    handler never fires. This is the load-bearing fix.
        # 3. `Runner.getInstance().play()` is called from `read_state`
        #    whenever `playing` is observed false without `crashed` —
        #    last-resort wakeup if anything bypasses the event
        #    suppression.
        try:
            driver.execute_cdp_cmd(
                "Emulation.setFocusEmulationEnabled", {"enabled": True}
            )
        except Exception:
            pass
        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": _PIN_VISIBILITY_JS},
            )
        except Exception:
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
            )

    def sanity_probe(self, *, timeout_s: float = 2.0, poll_s: float = 0.05) -> None:
        """Verify the page is actually ticking the dino game loop.

        Catches the failure mode that produced two slice-3 hotfixes:
        the page loaded, `Runner.getInstance()` returned an object, but
        the game loop wasn't advancing (paused via visibility, frozen on
        the static "Press space to play" landing, etc.). A no-op env
        run against such a page burns wall-clock without producing any
        learning signal.

        Protocol: dispatch a single Space (kickoff), then poll
        `read_state` every `poll_s` seconds for up to `timeout_s`.
        Success = at least one read shows `playing && currentSpeed > 0`
        AND `distanceRan` strictly increased between two consecutive
        such reads. Either condition alone is insufficient: a paused
        post-crash page still has `currentSpeed` from the previous
        episode, and a single `playing` read could be a transient.

        Raises `RuntimeError` on timeout. Caller owns teardown.
        """
        # Kick the page out of its initial idle. Safe to call even if the
        # page somehow auto-started: Space on an already-playing dino is
        # a jump, and the probe just measures distance over time.
        self._dispatch_key(_KEYDOWN, _KEY_SPACE)
        self._dispatch_key(_KEYUP, _KEY_SPACE)

        deadline = time.perf_counter() + timeout_s
        first_distance: float | None = None
        last_state: dict | None = None
        while time.perf_counter() < deadline:
            state = self.read_state()
            if state is None:
                time.sleep(poll_s)
                continue
            last_state = state
            playing = bool(state.get("playing"))
            speed = float(state.get("currentSpeed") or 0.0)
            distance = float(state.get("distanceRan") or 0.0)
            if playing and speed > 0:
                if first_distance is None:
                    first_distance = distance
                elif distance > first_distance:
                    return
            time.sleep(poll_s)

        raise RuntimeError(
            f"Browser.sanity_probe: game loop did not advance within "
            f"{timeout_s}s (last_state={last_state!r}). The page is "
            f"reachable but the dino is not running \u2014 check "
            f"visibility/focus state or whether navigation actually "
            f"loaded the offline page."
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
