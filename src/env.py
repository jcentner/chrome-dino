"""Gymnasium environment wrapper around `src.browser.Browser`.

Owns: action/observation spaces, the §3.4 raw-state → 14-dim feature
vector mapping, the §3.3 reward function, and the no-op-when-terminal
contract. Holds the only copies of the normalization constants
(canvas height, T-Rex resting xPos, MAX_SPEED) per AC-SINGLETON.

See ADR-003 (observation) and ADR-004 (action). No code outside this
module re-derives observation features.
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium.spaces import Box, Discrete

from src.browser import Browser, NOOP, JUMP, DUCK

__all__ = [
    "DinoEnv",
    "_observation_from_state",
    "NOOP",
    "JUMP",
    "DUCK",
    "OBS_DIM",
]


# ----------------------------------------------------------------------
# Normalization constants (AC-SINGLETON: defined here, nowhere else).
# Values are the Chromium offline dino defaults from
# components/neterror/resources/dino_game/offline.ts:
#   - DEFAULT_HEIGHT = 150 (Runner.config / dimensions.HEIGHT)
#   - tRex.xPos initial = 21 (Trex.config.START_X_POS)
#   - MAX_SPEED = 13 (Runner.config.MAX_SPEED)
# Captured DOM fixtures expose `canvasWidth` per snapshot but not height
# or tRex.xPos (these never change for a given Chrome version), so they
# live as module-level constants. Recorded as a working assumption in
# ADR-003; if they ever vary they get hoisted into the env constructor
# (read once from `Runner.config` / `Runner.instance_.dimensions`).
# ----------------------------------------------------------------------

OBS_DIM = 14
CANVAS_HEIGHT = 150.0
TREX_XPOS = 21.0
MAX_SPEED = 13.0

REWARD_STEP = 1.0
REWARD_TERMINAL = -100.0

# Type-id mapping per ADR-003 §3.4. The page's `o.typeConfig.type` field
# is camelCase ("cactusSmall", "cactusLarge", "pterodactyl") in modern
# Chromium; the older uppercase form is accepted as a courtesy.
_TYPE_ID: dict[str, int] = {
    "cactusSmall": 0,
    "cactusLarge": 1,
    "pterodactyl": 2,
    "CACTUS_SMALL": 0,
    "CACTUS_LARGE": 1,
    "PTERODACTYL": 2,
}

# Sentinel block per §3.4 / ADR-003: empty obstacle slot →
# (xPos_rel=+1.0, yPos_norm=0, width_norm=0, height_norm=0, type_id=-1).
# `-1` is categorically distinct from real types {0,1,2}; this is the
# discriminator the network uses to recognize "no obstacle" without
# overloading the 0.0 from "obstacle at origin."
_SENTINEL = (1.0, 0.0, 0.0, 0.0, -1.0)


def _obstacle_block(
    obstacle: dict | None, *, canvas_width: float
) -> tuple[float, float, float, float, float]:
    """Map one entry of `raw_state["obstacles"]` to its 5-field block.

    A `None` slot returns the §3.4 sentinel. A populated slot returns
    `(xPos_rel, yPos_norm, width_norm, height_norm, type_id)` with
    normalization per ADR-003.
    """
    if obstacle is None:
        return _SENTINEL
    x_rel = (float(obstacle["xPos"]) - TREX_XPOS) / canvas_width
    y_norm = float(obstacle["yPos"]) / CANVAS_HEIGHT
    w_norm = float(obstacle["width"]) / canvas_width
    h_norm = float(obstacle["height"]) / CANVAS_HEIGHT
    type_id = float(_TYPE_ID.get(str(obstacle.get("type", "")), -1))
    return (x_rel, y_norm, w_norm, h_norm, type_id)


def _observation_from_state(raw_state: dict) -> np.ndarray:
    """Pure §3.4 mapping: raw `Browser.read_state()` dict → 14-dim float32.

    Pure (no env state, no I/O); safe to call from tests against captured
    fixture JSONs. Layout pinned by ADR-003.
    """
    canvas_width = float(raw_state.get("canvasWidth") or 600.0)
    trex = raw_state["tRex"]
    obstacles = raw_state.get("obstacles") or [None, None]
    # Defensive: pad to two slots if the page returns a shorter list.
    if len(obstacles) < 2:
        obstacles = list(obstacles) + [None] * (2 - len(obstacles))

    dino_y_norm = float(trex.get("yPos") or 0.0) / CANVAS_HEIGHT
    dino_jumping = 1.0 if trex.get("jumping") else 0.0
    dino_ducking = 1.0 if trex.get("ducking") else 0.0
    speed_norm = float(raw_state.get("currentSpeed") or 0.0) / MAX_SPEED

    o0 = _obstacle_block(obstacles[0], canvas_width=canvas_width)
    o1 = _obstacle_block(obstacles[1], canvas_width=canvas_width)

    return np.asarray(
        (dino_y_norm, dino_jumping, dino_ducking, speed_norm, *o0, *o1),
        dtype=np.float32,
    )


class DinoEnv(gym.Env):
    """Gymnasium env over a `Browser` instance (DI for fixture testing).

    Contract:
      - `observation_space`: `Box(shape=(14,), float32)` per ADR-003.
      - `action_space`: `Discrete(3)` per ADR-004 (NOOP/JUMP/DUCK).
      - `reset()`: calls `browser.reset_episode()`, reads initial state,
        returns `(obs, info)`.
      - `step(action)`: forwards `action` to `browser.send_action`, reads
        next state, returns `(obs, reward, terminated, truncated, info)`
        with `truncated == False` always; reward `+1` per step, `-100`
        on the terminal step. If the env is already terminal, the action
        is ignored (no `send_action` dispatch) and the env surfaces a
        no-op terminal step.
    """

    metadata: dict = {"render_modes": []}

    def __init__(self, browser: Browser) -> None:
        super().__init__()
        self._browser = browser
        # Bounded by ±~10 on speed/xPos extremes; finite in practice but the
        # gymnasium spec only requires shape/dtype to match. Use the open
        # box because the §3.4 fields have no hard analytic upper bound
        # (xPos can briefly exceed canvas_width before the page culls it).
        self.observation_space = Box(
            low=-np.inf,
            high=np.inf,
            shape=(OBS_DIM,),
            dtype=np.float32,
        )
        self.action_space = Discrete(3)
        self._last_state: dict | None = None
        self._terminal: bool = False

    # ------------------------------------------------------------------
    # gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self._browser.reset_episode()
        state = self._browser.read_state()
        self._last_state = state
        self._terminal = bool(state.get("crashed", False))
        obs = _observation_from_state(state)
        info = self._info_dict()
        return obs, info

    def step(
        self, action: int
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        # No-op when already terminal: surface a valid terminal tuple
        # without dispatching to the browser. Per impl §6 slice 2 task 4.
        if self._terminal:
            assert self._last_state is not None  # set by reset()
            obs = _observation_from_state(self._last_state)
            return obs, REWARD_TERMINAL, True, False, self._info_dict()

        self._browser.send_action(int(action))
        state = self._browser.read_state()
        self._last_state = state
        terminated = bool(state.get("crashed", False))
        self._terminal = terminated
        obs = _observation_from_state(state)
        reward = REWARD_TERMINAL if terminated else REWARD_STEP
        return obs, reward, terminated, False, self._info_dict()

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _info_dict(self) -> dict[str, Any]:
        try:
            score = int(self._browser.get_score())
        except Exception:
            score = 0
        return {"score": score}
