"""Learned-policy wrapper around a stable-baselines3 DQN checkpoint.

Single surface per ADR-007. `LearnedPolicy.load(path)` constructs a
ready-to-`act` policy; `LearnedPolicy.act(observation)` returns a Python
`int` in `{NOOP, JUMP, DUCK}` greedy w.r.t. the loaded Q-network.

The class is deliberately thin — SB3's `DQN.load` does the actual
deserialization and shape validation; this wrapper only enforces:
  - the load failure message names the path (helpful errors over leaky
    SB3 stack traces),
  - `act` returns a builtin `int` (so `Browser.send_action(int)` doesn't
    receive a `numpy.int64` that misbehaves on cross-platform casts).
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np

from src.browser import NOOP, JUMP, DUCK  # noqa: F401 — re-exported

__all__ = ["LearnedPolicy", "NOOP", "JUMP", "DUCK"]


class LearnedPolicy:
    """Greedy wrapper around an SB3 DQN checkpoint."""

    def __init__(self, model: Any) -> None:
        self._model = model

    @classmethod
    def load(cls, checkpoint_path: str) -> "LearnedPolicy":
        """Load an SB3 DQN checkpoint and return a ready-to-`act` policy.

        Raises `FileNotFoundError` if the checkpoint file does not exist
        (SB3's own error wraps the path in a less-readable form). Re-raises
        SB3 load errors with a wrapping `RuntimeError` that includes the
        path string for triage.
        """
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(
                f"checkpoint not found: {checkpoint_path}"
            )
        try:
            from stable_baselines3 import DQN
        except ImportError as exc:  # pragma: no cover — requirements pin SB3
            raise RuntimeError(
                f"stable-baselines3 unavailable; cannot load checkpoint "
                f"{checkpoint_path}: {exc}"
            ) from exc
        try:
            model = DQN.load(checkpoint_path)
        except Exception as exc:
            raise RuntimeError(
                f"failed to load SB3 DQN checkpoint at {checkpoint_path}: "
                f"{exc}"
            ) from exc
        return cls(model)

    def act(self, observation: np.ndarray) -> int:
        """Return greedy action for `observation` (14-dim float32 vector
        per ADR-003). Output is a Python `int` in `{0, 1, 2}`.
        """
        # SB3 expects a batched observation if the policy was trained on
        # batched obs; pass shape (14,) — SB3's MlpPolicy accepts a single
        # un-batched observation and returns a numpy int.
        action, _state = self._model.predict(observation, deterministic=True)
        # `action` may be a 0-d ndarray, a numpy scalar, or a 1-element
        # array depending on SB3 version. Coerce to a Python int via .item()
        # which handles every np.integer subtype consistently.
        if isinstance(action, np.ndarray):
            action = action.item()
        return int(action)
