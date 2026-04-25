"""Slice-2 tests for `src.env.DinoEnv` and `src.env._observation_from_state`.

Tests are derived from `roadmap/phases/phase-1-design.md` §6/§7-slice-2 and
`roadmap/phases/phase-1-implementation.md` §3.3 (reward), §3.4 (observation
feature vector + sentinels), §3.5 (action space + held-key invariant),
§6 slice 2 (task list). The tester does not (and cannot) read `src/env.py` —
the isolation hook denies it. Tests pin the contract; the implementer
reconciles to the tests.

Working assumptions documented inline (resolving spec ambiguities — the
captured fixtures only carry `canvasWidth`, not canvas height, and never carry
`tRex.xPos`):

- `CANVAS_HEIGHT_DEFAULT = 150` — Chromium offline dino default canvas height
  (the captured fixtures have only `canvasWidth: 600`; canvas height is a
  module-level constant in the env per impl-plan §3.4 "normalization constants
  read once at env construction").
- `TREX_XPOS_DEFAULT = 21` — Chromium offline dino default `tRex.xPos`
  (fixtures have `tRex.yPos` only; xPos is also a normalization constant
  held by the env).
- `MAX_SPEED = 13` — explicitly stated by the spec/caller, matches Chromium
  `Runner.config.MAX_SPEED` default.

If the implementation uses different constants, these are real contract
disagreements to negotiate — not test bugs to silently relax.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

# Imports that pin the contract. Until `src/env.py` exists, every test in this
# module fails at collection with ModuleNotFoundError — that's the intended
# state at the start of slice 2 implementation.
from src.env import DinoEnv, _observation_from_state  # noqa: E402
from src.browser import Browser, NOOP, JUMP, DUCK  # noqa: E402


# ---------------------------------------------------------------------------
# Constants / layout
# ---------------------------------------------------------------------------

OBS_DIM = 14
MAX_SPEED = 13.0
CANVAS_HEIGHT_DEFAULT = 150.0
TREX_XPOS_DEFAULT = 21.0

# Feature-vector layout per impl-plan §3.4 (rows 1-14, in declaration order):
#   0: dino_y_norm
#   1: dino_jumping     (bool -> 0/1)
#   2: dino_ducking     (bool -> 0/1)
#   3: current_speed_norm
#   4-8:  obstacle[0] = (xPos_rel, yPos_norm, width_norm, height_norm, type_id)
#   9-13: obstacle[1] = (xPos_rel, yPos_norm, width_norm, height_norm, type_id)
IDX_DINO_Y = 0
IDX_DINO_JUMP = 1
IDX_DINO_DUCK = 2
IDX_SPEED = 3
IDX_OBS0_XREL = 4
IDX_OBS0_YPOS = 5
IDX_OBS0_W = 6
IDX_OBS0_H = 7
IDX_OBS0_TYPE = 8
IDX_OBS1_XREL = 9
IDX_OBS1_YPOS = 10
IDX_OBS1_W = 11
IDX_OBS1_H = 12
IDX_OBS1_TYPE = 13

# Sentinel block per §3.4: [xPos_rel=+1.0, yPos_norm=0, width_norm=0,
# height_norm=0, type_id=-1].
SENTINEL_BLOCK = (1.0, 0.0, 0.0, 0.0, -1.0)

# Type-id mapping per §3.4: CACTUS_SMALL=0, CACTUS_LARGE=1, PTERODACTYL=2.
TYPE_ID = {
    "cactusSmall": 0,
    "cactusLarge": 1,
    "pterodactyl": 2,
}

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "dom_state"
FIXTURE_NAMES = [
    "no_obstacles.json",
    "mid_jump.json",
    "normal_mid_episode.json",
    "both_obstacle_slots_populated.json",
    "terminal.json",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def _make_fake_browser(states: list[dict], score_value: int = 0) -> MagicMock:
    """Build a `Browser`-shaped MagicMock that emits `states` from
    `read_state()` in order and returns `score_value` from `get_score()`.

    `is_game_over()` mirrors the most-recently-served state's `crashed` flag.
    """
    browser = MagicMock(name="fake_browser")
    served: dict = {"last": None}

    def _read_state() -> dict:
        s = states.pop(0) if states else served["last"]
        served["last"] = s
        return s

    def _is_game_over() -> bool:
        last = served["last"] or {}
        return bool(last.get("crashed", False))

    browser.read_state.side_effect = _read_state
    browser.is_game_over.side_effect = _is_game_over
    browser.get_score.return_value = score_value
    browser.reset_episode.return_value = None
    browser.send_action.return_value = None
    return browser


# ---------------------------------------------------------------------------
# Env construction / spaces
# ---------------------------------------------------------------------------

def test_env_is_gymnasium_env() -> None:
    """`DinoEnv` is a `gymnasium.Env` subclass with the locked spaces."""
    import gymnasium as gym

    browser = _make_fake_browser([])
    env = DinoEnv(browser)
    assert isinstance(env, gym.Env)


def test_observation_space_shape_and_dtype() -> None:
    """`observation_space` is a 14-dim float32 Box per impl §3.4."""
    from gymnasium.spaces import Box

    browser = _make_fake_browser([])
    env = DinoEnv(browser)
    assert isinstance(env.observation_space, Box)
    assert env.observation_space.shape == (OBS_DIM,)
    assert env.observation_space.dtype == np.float32


def test_action_space_is_discrete_three() -> None:
    """`action_space` is `Discrete(3)` per impl §3.5 — NOOP/JUMP/DUCK."""
    from gymnasium.spaces import Discrete

    browser = _make_fake_browser([])
    env = DinoEnv(browser)
    assert isinstance(env.action_space, Discrete)
    assert env.action_space.n == 3
    assert {NOOP, JUMP, DUCK} == {0, 1, 2}


# ---------------------------------------------------------------------------
# _observation_from_state — shape / dtype / finiteness across all fixtures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_observation_shape_and_finite(fixture_name: str) -> None:
    """Every captured fixture maps to a well-formed (14,) float32 vector
    with no NaN/Inf — the basic vector-validity contract."""
    raw = _load_fixture(fixture_name)
    obs = _observation_from_state(raw)
    assert isinstance(obs, np.ndarray)
    assert obs.shape == (OBS_DIM,)
    assert obs.dtype == np.float32
    assert np.all(np.isfinite(obs)), f"non-finite value in obs for {fixture_name}: {obs}"


# ---------------------------------------------------------------------------
# Sentinel handling — empty obstacle slots
# ---------------------------------------------------------------------------

def test_no_obstacles_uses_exact_sentinels() -> None:
    """When both `obstacles` slots are empty, both 5-field obstacle blocks
    take the exact §3.4 sentinel values: xPos_rel=+1.0, yPos_norm=0.0,
    width_norm=0.0, height_norm=0.0, type_id=-1.

    This is the post-mortem bug-fix codification: 0.0 must NOT mean both
    'no obstacle' and 'imminent collision'.
    """
    raw = _load_fixture("no_obstacles.json")
    # Sanity-check the fixture matches its filename's promise.
    assert raw["obstacles"] == [None, None], (
        "Fixture invariant violated: no_obstacles.json must have both slots empty."
    )
    obs = _observation_from_state(raw)
    obs0 = tuple(float(x) for x in obs[IDX_OBS0_XREL:IDX_OBS0_TYPE + 1])
    obs1 = tuple(float(x) for x in obs[IDX_OBS1_XREL:IDX_OBS1_TYPE + 1])
    assert obs0 == SENTINEL_BLOCK
    assert obs1 == SENTINEL_BLOCK


def test_partially_populated_slots_mix_real_and_sentinel() -> None:
    """When `obstacles[0]` is populated and `obstacles[1]` is empty, slot 0
    carries real values (xPos_rel < +1.0, type_id ∈ {0,1,2}) and slot 1
    carries the §3.4 sentinels exactly.
    """
    raw = _load_fixture("mid_jump.json")
    assert raw["obstacles"][0] is not None and raw["obstacles"][1] is None, (
        "Fixture invariant violated: mid_jump.json must have only slot 0 populated."
    )
    obs = _observation_from_state(raw)

    # Slot 0: real cactusSmall, on-screen → xPos_rel < 1.0, type_id == 0.
    assert obs[IDX_OBS0_TYPE] == TYPE_ID["cactusSmall"]
    assert obs[IDX_OBS0_XREL] < 1.0
    assert obs[IDX_OBS0_W] > 0.0
    assert obs[IDX_OBS0_H] > 0.0

    # Slot 1: sentinels, exact.
    obs1 = tuple(float(x) for x in obs[IDX_OBS1_XREL:IDX_OBS1_TYPE + 1])
    assert obs1 == SENTINEL_BLOCK


# ---------------------------------------------------------------------------
# Field semantics — obstacle-populated fixtures
# ---------------------------------------------------------------------------

def test_field_semantics_normal_mid_episode() -> None:
    """A subset of fields on `normal_mid_episode.json` matches the §3.4
    formulae: `current_speed_norm = currentSpeed / MAX_SPEED`,
    `dino_jumping/ducking` are 0/1 mirrors of the booleans, and the slot-0
    `xPos_rel = (obstacle.xPos - tRex.xPos) / canvasWidth` and `type_id`
    map per §3.4.
    """
    raw = _load_fixture("normal_mid_episode.json")
    obs = _observation_from_state(raw)

    expected_speed = raw["currentSpeed"] / MAX_SPEED
    assert obs[IDX_SPEED] == pytest.approx(expected_speed, rel=1e-5)

    # tRex flags: ducking=False, jumping=False in this fixture.
    assert obs[IDX_DINO_JUMP] == pytest.approx(1.0 if raw["tRex"]["jumping"] else 0.0)
    assert obs[IDX_DINO_DUCK] == pytest.approx(1.0 if raw["tRex"]["ducking"] else 0.0)

    obstacle = raw["obstacles"][0]
    expected_xrel = (obstacle["xPos"] - TREX_XPOS_DEFAULT) / raw["canvasWidth"]
    # Allow a small absolute tolerance for tRex.xPos default uncertainty (~±5px / 600).
    assert obs[IDX_OBS0_XREL] == pytest.approx(expected_xrel, abs=0.01)
    assert obs[IDX_OBS0_TYPE] == TYPE_ID[obstacle["type"]]


def test_field_semantics_both_slots_populated() -> None:
    """`both_obstacle_slots_populated.json` — both obstacle slots map to
    real values, with type_ids matching the cactusSmall/cactusLarge ids
    and `current_speed_norm` matching `currentSpeed / MAX_SPEED`.
    """
    raw = _load_fixture("both_obstacle_slots_populated.json")
    assert raw["obstacles"][0] is not None and raw["obstacles"][1] is not None, (
        "Fixture invariant violated: both_obstacle_slots_populated.json must "
        "have both slots populated."
    )
    obs = _observation_from_state(raw)

    expected_speed = raw["currentSpeed"] / MAX_SPEED
    assert obs[IDX_SPEED] == pytest.approx(expected_speed, rel=1e-5)

    o0, o1 = raw["obstacles"][0], raw["obstacles"][1]
    assert obs[IDX_OBS0_TYPE] == TYPE_ID[o0["type"]]
    assert obs[IDX_OBS1_TYPE] == TYPE_ID[o1["type"]]

    # Both slots have real values (not sentinels): width/height > 0.
    assert obs[IDX_OBS0_W] > 0.0 and obs[IDX_OBS0_H] > 0.0
    assert obs[IDX_OBS1_W] > 0.0 and obs[IDX_OBS1_H] > 0.0


def test_dino_y_norm_in_unit_range_when_jumping() -> None:
    """`dino_y_norm` for `mid_jump.json` is in [0, 1] (canvas-height
    normalized). Exact value not asserted because canvas height is a
    module-level constant in the env, not a field of the captured fixture.
    """
    raw = _load_fixture("mid_jump.json")
    obs = _observation_from_state(raw)
    assert 0.0 <= float(obs[IDX_DINO_Y]) <= 1.0


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_calls_browser_and_returns_obs_info() -> None:
    """`reset()` calls `browser.reset_episode()`, reads initial state, and
    returns `(obs_ndarray_14, info_dict)`.
    """
    initial = _load_fixture("normal_mid_episode.json")
    browser = _make_fake_browser([initial], score_value=0)
    env = DinoEnv(browser)

    out = env.reset(seed=None, options=None)
    assert isinstance(out, tuple) and len(out) == 2
    obs, info = out

    browser.reset_episode.assert_called_once()
    assert isinstance(obs, np.ndarray)
    assert obs.shape == (OBS_DIM,)
    assert obs.dtype == np.float32
    assert isinstance(info, dict)


# ---------------------------------------------------------------------------
# Reward signal — §3.3
# ---------------------------------------------------------------------------

def test_reward_per_step_then_terminal() -> None:
    """Per impl §3.3: reward is `+1.0` per non-terminal step and `-100.0`
    on the terminal step. Terminal flag mirrors `raw_state["crashed"]`.
    Truncated is always False.
    """
    initial = _load_fixture("normal_mid_episode.json")
    survive = _load_fixture("mid_jump.json")
    terminal = _load_fixture("terminal.json")
    browser = _make_fake_browser([initial, survive, terminal], score_value=42)
    env = DinoEnv(browser)
    env.reset()

    obs1, reward1, terminated1, truncated1, info1 = env.step(NOOP)
    assert reward1 == pytest.approx(1.0)
    assert terminated1 is False
    assert truncated1 is False
    assert obs1.shape == (OBS_DIM,) and obs1.dtype == np.float32
    assert info1.get("score") == 42

    obs2, reward2, terminated2, truncated2, info2 = env.step(NOOP)
    assert reward2 == pytest.approx(-100.0)
    assert terminated2 is True
    assert truncated2 is False
    assert obs2.shape == (OBS_DIM,) and obs2.dtype == np.float32
    assert info2.get("score") == 42


# ---------------------------------------------------------------------------
# Action encoding — §3.5
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action", [NOOP, JUMP, DUCK])
def test_step_forwards_action_to_browser(action: int) -> None:
    """`step(action)` forwards `action` (an int in {0,1,2}) to
    `browser.send_action(...)` exactly once with the matching int.

    The browser-adapter owns the key-event translation per impl §3.5; the
    env must not re-encode actions.
    """
    initial = _load_fixture("normal_mid_episode.json")
    next_state = _load_fixture("mid_jump.json")
    browser = _make_fake_browser([initial, next_state])
    env = DinoEnv(browser)
    env.reset()

    env.step(action)
    browser.send_action.assert_called_once_with(action)


# ---------------------------------------------------------------------------
# Episode-boundary detection
# ---------------------------------------------------------------------------

def test_terminal_fixture_yields_terminated_true() -> None:
    """A `terminal.json`-shaped state (crashed=True) → `terminated == True`."""
    initial = _load_fixture("normal_mid_episode.json")
    terminal = _load_fixture("terminal.json")
    browser = _make_fake_browser([initial, terminal])
    env = DinoEnv(browser)
    env.reset()

    _obs, _reward, terminated, truncated, _info = env.step(NOOP)
    assert terminated is True
    assert truncated is False


def test_non_terminal_fixture_yields_terminated_false() -> None:
    """A non-crashed state (crashed=False) → `terminated == False`."""
    initial = _load_fixture("normal_mid_episode.json")
    next_state = _load_fixture("mid_jump.json")
    browser = _make_fake_browser([initial, next_state])
    env = DinoEnv(browser)
    env.reset()

    _obs, _reward, terminated, truncated, _info = env.step(NOOP)
    assert terminated is False
    assert truncated is False


# ---------------------------------------------------------------------------
# Action-during-terminal is a no-op (impl §6 slice 2 task 4)
# ---------------------------------------------------------------------------

def test_step_when_already_terminal_is_noop_no_exception() -> None:
    """If the env is stepped while already in a terminal state, the action
    is ignored: the env returns a valid terminal tuple, raises no exception,
    and (preferably) does not dispatch the action to the browser.
    """
    terminal = _load_fixture("terminal.json")
    # Reset reads terminal state; subsequent step also reads terminal.
    browser = _make_fake_browser([terminal, terminal])
    env = DinoEnv(browser)
    env.reset()

    # Reset's read should already register as crashed; clear send_action call
    # history (reset must NOT have dispatched any action — defensive check).
    browser.send_action.reset_mock()

    obs, _reward, terminated, truncated, _info = env.step(JUMP)
    assert terminated is True
    assert truncated is False
    assert obs.shape == (OBS_DIM,) and obs.dtype == np.float32
    # Per impl §6 slice 2 task 4: "Action ignored if game is already in the
    # terminal state — env does not crash, surfaces a no-op terminal step."
    # We assert the send_action call count is 0 (strict no-op).
    assert browser.send_action.call_count == 0


# ---------------------------------------------------------------------------
# Live integration — opt-in via `-m browser`
# ---------------------------------------------------------------------------

@pytest.mark.browser
def test_random_policy_episode_live_browser() -> None:
    """One full live-Chrome episode under a seeded random policy.

    Asserts: at least one terminal step occurred; episode length > 0; every
    observation has shape (14,) and dtype float32; no NaN/Inf in any obs.
    Per impl §6 slice 2 task 7.
    """
    rng = np.random.default_rng(42)
    with Browser.launch() as browser:  # type: ignore[attr-defined]
        env = DinoEnv(browser)
        obs, _info = env.reset()
        assert obs.shape == (OBS_DIM,) and obs.dtype == np.float32
        assert np.all(np.isfinite(obs))

        steps = 0
        terminated = False
        max_steps = 10_000  # safety cap; a real episode terminates well before this
        while not terminated and steps < max_steps:
            action = int(rng.integers(0, 3))
            obs, _reward, terminated, _truncated, _info = env.step(action)
            assert obs.shape == (OBS_DIM,)
            assert obs.dtype == np.float32
            assert np.all(np.isfinite(obs))
            steps += 1

        assert steps > 0, "episode produced zero steps"
        assert terminated, "episode never reached a terminal state within max_steps"
