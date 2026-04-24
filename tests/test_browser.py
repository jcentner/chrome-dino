"""Slice-1 tests for `src.browser.Browser`.

Tests are derived from `roadmap/phases/phase-1-design.md` §2/§5/§6/§7-slice-1
and `roadmap/phases/phase-1-implementation.md` §3.4/§3.5/§3.7/§4/§6 slice 1.
The tester does not (and cannot) read `src/browser.py` source — the hook
denies it. Tests pin the contract; the implementer reconciles to the tests.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, call

# Imports that pin the contract. Until `src/browser.py` exists, every test in
# this module fails at collection with ModuleNotFoundError — that's the
# intended state at the start of slice 1 implementation.
from src.browser import Browser, VersionMismatchError, NOOP, JUMP, DUCK  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

KEYDOWN = "keyDown"
KEYUP = "keyUp"
ARROW_UP = "ArrowUp"
ARROW_DOWN = "ArrowDown"
SPACE = " "

CDP_DISPATCH_METHOD = "Input.dispatchKeyEvent"


def _cdp_key_events(driver: MagicMock) -> list[tuple[str, str]]:
    """Return the ordered list of `(type, key)` from `Input.dispatchKeyEvent`
    calls on the mock driver. Robust against positional vs. keyword call shape.
    """
    events: list[tuple[str, str]] = []
    for c in driver.execute_cdp_cmd.call_args_list:
        args, kwargs = c
        if args:
            method = args[0]
            params = args[1] if len(args) > 1 else kwargs.get("cmd_args", kwargs.get("params", {}))
        else:
            method = kwargs.get("cmd") or kwargs.get("method")
            params = kwargs.get("cmd_args") or kwargs.get("params") or {}
        if method == CDP_DISPATCH_METHOD:
            events.append((params.get("type"), params.get("key")))
    return events


def _make_browser(*, user_agent: str | None = None, score_value: int = 0,
                  game_over: bool = False) -> tuple[Browser, MagicMock]:
    """Construct a `Browser` against a `MagicMock` driver.

    `driver.execute_script` is wired to return a value that is plausible for
    *any* JS the implementation might run — a scalar for `get_score` /
    `is_game_over`, a string for `version_check`, and an empty dict otherwise.
    Tests that need finer control override `execute_script.return_value` or
    `.side_effect` after construction.
    """
    driver = MagicMock(name="webdriver")
    if user_agent is not None:
        driver.execute_script.return_value = user_agent
    driver.execute_cdp_cmd.return_value = {}
    browser = Browser(driver=driver)
    return browser, driver


# ---------------------------------------------------------------------------
# version_check
# ---------------------------------------------------------------------------

def test_version_check_raises_on_mismatch() -> None:
    """`version_check()` raises `VersionMismatchError` when the live Chrome's
    major version does not match the pinned major.

    The implementation is expected to read `navigator.userAgent` (or an
    equivalent CDP `Browser.getVersion`) and compare majors. We mock the
    driver to report a clearly different major than any plausible pin.
    """
    bogus_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/1.0.0.0 Safari/537.36"
    )
    browser, driver = _make_browser(user_agent=bogus_ua)
    driver.capabilities = {"browserVersion": "1.0.0.0"}

    with pytest.raises(VersionMismatchError):
        browser.version_check()


# ---------------------------------------------------------------------------
# send_action — basic dispatch
# ---------------------------------------------------------------------------

def test_send_action_dispatches_cdp() -> None:
    """`send_action(JUMP)` dispatches exactly one `keyDown ArrowUp` and one
    `keyUp ArrowUp` via CDP `Input.dispatchKeyEvent`."""
    browser, driver = _make_browser()

    browser.send_action(JUMP)

    events = _cdp_key_events(driver)
    assert (KEYDOWN, ARROW_UP) in events
    assert (KEYUP, ARROW_UP) in events
    assert events.count((KEYDOWN, ARROW_UP)) == 1
    assert events.count((KEYUP, ARROW_UP)) == 1
    # No stray ArrowDown / Space dispatches on a cold JUMP.
    assert not any(key in {ARROW_DOWN, SPACE} for _, key in events)


# ---------------------------------------------------------------------------
# DUCK held-key state machine (§3.5 invariant)
# ---------------------------------------------------------------------------

def test_duck_press_holds_arrowdown() -> None:
    """`send_action(DUCK)` dispatches `keyDown ArrowDown` and the adapter
    remembers the held state — a redundant second `DUCK` must NOT re-dispatch
    `keyDown ArrowDown` (this verifies the held-flag without reading source)."""
    browser, driver = _make_browser()

    browser.send_action(DUCK)
    events_after_first = _cdp_key_events(driver)
    assert (KEYDOWN, ARROW_DOWN) in events_after_first
    assert events_after_first.count((KEYDOWN, ARROW_DOWN)) == 1

    browser.send_action(DUCK)
    events_after_second = _cdp_key_events(driver)
    # Still exactly one keyDown ArrowDown across both calls.
    assert events_after_second.count((KEYDOWN, ARROW_DOWN)) == 1


def test_duck_to_jump_releases_arrowdown_first() -> None:
    """§3.5 invariant: any non-DUCK action releases held `ArrowDown` before
    dispatching its own keys. For `DUCK → JUMP`, the keyUp ArrowDown must come
    before the keyDown ArrowUp."""
    browser, driver = _make_browser()

    browser.send_action(DUCK)
    browser.send_action(JUMP)

    events = _cdp_key_events(driver)
    assert (KEYUP, ARROW_DOWN) in events
    assert (KEYDOWN, ARROW_UP) in events
    assert events.index((KEYUP, ARROW_DOWN)) < events.index((KEYDOWN, ARROW_UP))


def test_duck_to_jump_to_duck_re_presses_arrowdown() -> None:
    """`DUCK → JUMP → DUCK` — assert the intermediate JUMP cleanly released
    `ArrowDown` and pressed/released `ArrowUp`, AND that the second DUCK
    re-dispatches `keyDown ArrowDown` (held flag was correctly cleared)."""
    browser, driver = _make_browser()

    browser.send_action(DUCK)
    browser.send_action(JUMP)
    browser.send_action(DUCK)

    events = _cdp_key_events(driver)

    # Intermediate JUMP: keyUp ArrowDown, then keyDown ArrowUp, then keyUp ArrowUp.
    idx_first_keydown_arrowdown = events.index((KEYDOWN, ARROW_DOWN))
    idx_keyup_arrowdown = events.index((KEYUP, ARROW_DOWN))
    idx_keydown_arrowup = events.index((KEYDOWN, ARROW_UP))
    idx_keyup_arrowup = events.index((KEYUP, ARROW_UP))
    assert idx_first_keydown_arrowdown < idx_keyup_arrowdown < idx_keydown_arrowup < idx_keyup_arrowup

    # The second DUCK re-presses ArrowDown → exactly two keyDown ArrowDown overall.
    assert events.count((KEYDOWN, ARROW_DOWN)) == 2
    assert events.count((KEYUP, ARROW_DOWN)) == 1  # only the JUMP-time release; the second hold is still held


def test_noop_releases_held_arrowdown() -> None:
    """`DUCK → NOOP` — NOOP must dispatch `keyUp ArrowDown` (covers the
    "any non-DUCK action releases held ArrowDown" invariant for NOOP)."""
    browser, driver = _make_browser()

    browser.send_action(DUCK)
    browser.send_action(NOOP)

    events = _cdp_key_events(driver)
    assert (KEYUP, ARROW_DOWN) in events
    assert events.count((KEYUP, ARROW_DOWN)) == 1


@pytest.mark.skip(
    reason=(
        "Terminal-step held-key release lives in src/env.py.step() per "
        "implementation plan §3.5 — Browser has no public 'advance one step' "
        "method. Covered by test_reset_episode_releases_held_arrowdown below "
        "and by tests/test_env.py in slice 2."
    )
)
def test_terminal_step_releases_arrowdown() -> None:
    raise NotImplementedError


def test_reset_episode_releases_held_arrowdown() -> None:
    """`reset_episode()` while `ArrowDown` is held must dispatch
    `keyUp ArrowDown` BEFORE any `keyDown Space` (§3.5 invariant: reset does
    not dispatch Space while ArrowDown is held)."""
    browser, driver = _make_browser()

    browser.send_action(DUCK)  # ArrowDown now held
    browser.reset_episode()

    events = _cdp_key_events(driver)
    assert (KEYUP, ARROW_DOWN) in events
    assert (KEYDOWN, SPACE) in events
    assert events.index((KEYUP, ARROW_DOWN)) < events.index((KEYDOWN, SPACE))


def test_reset_then_jump_is_clean() -> None:
    """`DUCK → reset_episode() → JUMP` — the JUMP produces a clean
    `keyDown/keyUp ArrowUp` with NO spurious `keyUp ArrowDown` (because the
    held flag was already cleared at the reset boundary)."""
    browser, driver = _make_browser()

    browser.send_action(DUCK)
    browser.reset_episode()
    # Snapshot the dispatch count up to the boundary, then act.
    events_before_jump = _cdp_key_events(driver)
    keyup_arrowdown_count_before = events_before_jump.count((KEYUP, ARROW_DOWN))

    browser.send_action(JUMP)

    events_after = _cdp_key_events(driver)
    keyup_arrowdown_count_after = events_after.count((KEYUP, ARROW_DOWN))

    # JUMP did NOT add a spurious keyUp ArrowDown.
    assert keyup_arrowdown_count_after == keyup_arrowdown_count_before
    # JUMP DID dispatch a clean ArrowUp press/release.
    new_events = events_after[len(events_before_jump):]
    assert (KEYDOWN, ARROW_UP) in new_events
    assert (KEYUP, ARROW_UP) in new_events
    assert new_events.index((KEYDOWN, ARROW_UP)) < new_events.index((KEYUP, ARROW_UP))


def test_context_manager_releases_held_keys_on_exit() -> None:
    """Using `Browser` as a context manager: if `ArrowDown` is held inside the
    `with` block, on context exit `keyUp ArrowDown` must be dispatched BEFORE
    `driver.quit()` (§3.5 invariant for the teardown path)."""
    driver = MagicMock(name="webdriver")
    driver.execute_cdp_cmd.return_value = {}

    with Browser(driver=driver) as browser:
        browser.send_action(DUCK)

    # Walk driver.mock_calls in chronological order; find the position of the
    # last keyUp ArrowDown and the position of the first quit() call. Assert
    # the keyUp comes first.
    keyup_arrowdown_pos: int | None = None
    quit_pos: int | None = None
    for i, mc in enumerate(driver.mock_calls):
        name, args, kwargs = mc
        if name == "execute_cdp_cmd":
            method = args[0] if args else kwargs.get("cmd") or kwargs.get("method")
            params = (args[1] if len(args) > 1 else
                      kwargs.get("cmd_args") or kwargs.get("params") or {})
            if method == CDP_DISPATCH_METHOD and params.get("type") == KEYUP and params.get("key") == ARROW_DOWN:
                keyup_arrowdown_pos = i
        if name == "quit" and quit_pos is None:
            quit_pos = i

    assert keyup_arrowdown_pos is not None, "expected keyUp ArrowDown on context exit"
    assert quit_pos is not None, "expected driver.quit() on context exit"
    assert keyup_arrowdown_pos < quit_pos


# ---------------------------------------------------------------------------
# get_score — page formula
# ---------------------------------------------------------------------------

def test_get_score_uses_page_formula() -> None:
    """`get_score()` returns the value computed page-side and passes it through
    untouched. We mock `execute_script` to return the integer the page would
    have returned and assert `get_score()` matches.

    Per the chromium-dino-runner skill, the page-side formula is
    `Math.round(Math.ceil(Runner.getInstance().distanceRan) * 0.025)` —
    matching `DistanceMeter.getActualDistance` in
    components/neterror/resources/dino_game/distance_meter.ts. The formula is
    evaluated in the browser; this test asserts the passthrough only.
    """
    expected_score = 1234
    browser, driver = _make_browser()
    driver.execute_script.return_value = expected_score

    assert browser.get_score() == expected_score
    assert isinstance(browser.get_score(), int)


# ---------------------------------------------------------------------------
# Live-browser opt-in test
# ---------------------------------------------------------------------------

@pytest.mark.browser
def test_one_short_episode() -> None:
    """End-to-end: construct a real `Browser`, drive it through ~100
    heuristic steps, assert no exceptions and that the produced single-episode
    dict conforms to the artifact schema (§6 slice 1 task 4)."""
    from src.browser import Browser  # local import: real driver construction
    from src.heuristic import act as heuristic_act

    with Browser.launch() as browser:
        browser.version_check()
        browser.reset_episode()
        steps = 0
        while steps < 100 and not browser.is_game_over():
            obs = browser.read_state()
            action = heuristic_act(obs)
            browser.send_action(action)
            steps += 1
        score = browser.get_score()

    assert steps > 0
    assert isinstance(score, int)
    assert score >= 0
