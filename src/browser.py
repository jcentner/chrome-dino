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

# Pinned Chrome major. Lives next to the runtime install at
# C:\chrome-dino-runtime\ (see docs/setup/windows-chrome-pinning.md).
# Set to None to skip the check; set to a major-version int to enforce.
PINNED_CHROME_MAJOR: int | None = None


class VersionMismatchError(RuntimeError):
    """Raised by `Browser.version_check` when the live Chrome major does not
    match `PINNED_CHROME_MAJOR`."""


# JS one-liner that returns the full §3.4 raw state as a dict. Read in a
# single `execute_script` call so the returned snapshot is internally
# consistent (no torn read across two round-trips).
_READ_STATE_JS = r"""
const r = (typeof Runner !== 'undefined') ? Runner.instance_ : null;
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
  canvasWidth: r.dimensions ? r.dimensions.WIDTH : null,
  tRex: {
    yPos: t ? t.yPos : null,
    jumping: t ? !!t.jumping : false,
    ducking: t ? !!t.ducking : false
  },
  obstacles: [obstacle(obs[0]), obstacle(obs[1])]
};
"""

_GET_SCORE_JS = r"""
const r = (typeof Runner !== 'undefined') ? Runner.instance_ : null;
if (!r) { return 0; }
const c = (r.config && r.config.COEFFICIENT) ? r.config.COEFFICIENT : 0.025;
return Math.floor(r.distanceRan * c);
"""

_GAME_OVER_JS = r"""
const r = (typeof Runner !== 'undefined') ? Runner.instance_ : null;
return !!(r && r.crashed);
"""

_PLAYING_JS = r"""
const r = (typeof Runner !== 'undefined') ? Runner.instance_ : null;
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
        # §3.5 held-key invariant: track whether ArrowDown is currently held.
        self._arrow_down_held = False

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
        """
        if action != DUCK and self._arrow_down_held:
            self._dispatch_key(_KEYUP, _KEY_ARROW_DOWN)
            self._arrow_down_held = False

        if action == NOOP:
            return
        if action == JUMP:
            self._dispatch_key(_KEYDOWN, _KEY_ARROW_UP)
            self._dispatch_key(_KEYUP, _KEY_ARROW_UP)
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

        §3.5 invariant: release any held `ArrowDown` BEFORE dispatching the
        Space that starts the new run. Does not block on `Runner.playing`
        in the unit-test path; the live-browser path waits via `is_game_over`
        polling at the eval-loop level (kept out of the adapter to keep the
        adapter testable without a real timer).
        """
        self._release_held_keys()
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

    def _dispatch_key(self, type_: str, key: str) -> None:
        params = {"type": type_, "key": key}
        self._driver.execute_cdp_cmd(_CDP_DISPATCH, params)
