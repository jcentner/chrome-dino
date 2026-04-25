"""Slice-3 tests for `src.policy.LearnedPolicy`.

Tests are derived from `roadmap/phases/phase-1-implementation.md` §3.1
(algorithm: SB3 DQN) and §6 slice 3 (task list + tests). The tester does
not (and cannot) read `src/policy.py` source — the isolation hook denies it.
Tests pin the contract; the implementer reconciles to the tests.

Resolved spec ambiguities (documented inline below):

- The wrapper sidecar metadata path (`<ckpt>.json` vs co-located `metadata.json`)
  is implementation-defined; tests only pin that load works against a checkpoint
  produced by SB3's own `DQN.save`. If the implementer requires sidecar JSON,
  these tests will fail and the missing-sidecar contract should be added then.
- `act` must return a builtin `int` (not `np.int64` / `np.ndarray` / `bool`) so
  `Browser.send_action(int)` doesn't get a numpy scalar that could fail an
  edge-case `int()` cast.
- Determinism: `act` is greedy (no exploration noise) at eval time per
  impl-plan §3.1; two calls on the same obs return the same int.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

# Imports that pin the contract. Until `src/policy.py` exists, every test in
# this module fails at collection with ModuleNotFoundError — that's the
# intended state at the start of slice 3 implementation.
from src.policy import LearnedPolicy  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — a self-contained gymnasium.Env that never touches src.browser.
# ---------------------------------------------------------------------------


def _make_dummy_env():
    """Return a tiny gymnasium.Env with the slice-2 obs/action shapes.

    Box(14, float32) observation + Discrete(3) action — matches the env that
    DQN was trained against per impl-plan §3.4 / §3.5. The env never crashes,
    never reads from a real browser, and terminates after one step so SB3 can
    do its `learning_starts=0, total_timesteps=10` dry-run quickly.
    """
    import gymnasium as gym

    class _DummyEnv(gym.Env):
        metadata = {"render_modes": []}

        def __init__(self) -> None:
            super().__init__()
            self.observation_space = gym.spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=(14,),
                dtype=np.float32,
            )
            self.action_space = gym.spaces.Discrete(3)
            self._steps = 0

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            self._steps = 0
            return np.zeros(14, dtype=np.float32), {}

        def step(self, action):
            self._steps += 1
            terminated = self._steps >= 1
            return (
                np.zeros(14, dtype=np.float32),
                0.0,
                terminated,
                False,
                {},
            )

    return _DummyEnv()


@pytest.fixture
def trained_checkpoint(tmp_path: Path) -> Path:
    """Build & save a tiny SB3 DQN checkpoint; return the on-disk path.

    `learning_starts=0, total_timesteps=10` keeps fit time near-zero. SB3
    appends `.zip` to the save path; we return the actual file path that
    exists on disk.
    """
    from stable_baselines3 import DQN

    env = _make_dummy_env()
    model = DQN(
        "MlpPolicy",
        env,
        learning_starts=0,
        buffer_size=100,
        batch_size=4,
        verbose=0,
        seed=0,
    )
    model.learn(total_timesteps=10)

    save_stem = tmp_path / "ckpt"
    model.save(str(save_stem))
    # SB3 appends .zip — this is the path LearnedPolicy.load receives.
    ckpt_path = save_stem.with_suffix(".zip")
    assert ckpt_path.exists(), f"SB3 did not produce the expected zip at {ckpt_path}"
    return ckpt_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_load_round_trip_returns_valid_action(trained_checkpoint: Path) -> None:
    """SB3 DQN.save → LearnedPolicy.load → act returns an action in {0,1,2}."""
    policy = LearnedPolicy.load(str(trained_checkpoint))
    obs = np.zeros(14, dtype=np.float32)
    action = policy.act(obs)
    assert action in (0, 1, 2), f"action {action!r} not in NOOP/JUMP/DUCK"


def test_act_returns_int_not_numpy_scalar(trained_checkpoint: Path) -> None:
    """`act` returns a builtin int (not np.int64 / np.ndarray / bool)."""
    policy = LearnedPolicy.load(str(trained_checkpoint))
    action = policy.act(np.zeros(14, dtype=np.float32))
    # Strict type check — `isinstance(np.int64(0), int)` is False on Windows
    # but True on Linux; pin to the exact builtin to avoid platform skew.
    assert type(action) is int, (
        f"expected builtin int, got {type(action).__name__}: {action!r}"
    )
    # bool is a subclass of int — guard against accidental bool returns.
    assert not isinstance(action, bool), "act must not return bool"


def test_act_is_deterministic(trained_checkpoint: Path) -> None:
    """Greedy eval: two `act` calls on the same obs return the same int."""
    policy = LearnedPolicy.load(str(trained_checkpoint))
    obs = np.zeros(14, dtype=np.float32)
    a1 = policy.act(obs)
    a2 = policy.act(obs)
    assert a1 == a2, f"non-deterministic act: {a1} != {a2}"


def test_load_missing_file_raises_informatively(tmp_path: Path) -> None:
    """Missing checkpoint → exception whose message mentions the path or
    one of {'checkpoint', 'not found', 'missing'} (case-insensitive)."""
    bogus = tmp_path / "nonexistent" / "does_not_exist.zip"
    with pytest.raises(Exception) as exc_info:
        LearnedPolicy.load(str(bogus))
    msg = str(exc_info.value).lower()
    assert (
        "does_not_exist" in msg
        or "checkpoint" in msg
        or "not found" in msg
        or "missing" in msg
        or "no such file" in msg
    ), f"uninformative error message: {exc_info.value!r}"


def test_load_non_sb3_zip_raises_informatively(tmp_path: Path) -> None:
    """Junk bytes at a .zip path → load raises (any exception type).

    The message should reference one of {'checkpoint', 'load', 'sb3', 'zip',
    'invalid'} (case-insensitive). Exact exception type is not pinned — the
    impl may bubble up SB3's native error.
    """
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"not a real zip")
    with pytest.raises(Exception) as exc_info:
        LearnedPolicy.load(str(junk))
    msg = str(exc_info.value).lower()
    assert any(
        token in msg for token in ("checkpoint", "load", "sb3", "zip", "invalid")
    ), f"uninformative error message: {exc_info.value!r}"
