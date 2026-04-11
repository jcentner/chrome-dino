"""
Headless Chrome Dino game environment for Gymnasium.

Physics and obstacle data sourced from Chromium source:
https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/neterror/resources/dino_game/

This is a faithful recreation of the game mechanics for fast RL training,
not a pixel-perfect visual clone.
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from typing import Optional


# ---------------------------------------------------------------------------
# Constants from Chromium source (normal mode)
# ---------------------------------------------------------------------------

# Canvas / world
CANVAS_WIDTH = 600
CANVAS_HEIGHT = 150
FPS = 60
GROUND_Y = 0  # We use y=0 as ground, positive = up (inverted from canvas)

# Runner config (offline.ts — normalModeConfig)
INITIAL_SPEED = 6.0        # pixels per frame at 60fps
ACCELERATION = 0.001       # per frame
MAX_SPEED = 13.0
GAP_COEFFICIENT = 0.6
MAX_GAP_COEFFICIENT = 1.5

# T-Rex config (trex.ts — normalJumpConfig + defaultTrexConfig)
TREX_WIDTH = 44
TREX_HEIGHT = 47
TREX_HEIGHT_DUCK = 25
TREX_WIDTH_DUCK = 59
TREX_START_X = 50
INITIAL_JUMP_VELOCITY = 10.0   # positive = upward in our coords
GRAVITY = 0.6                   # per frame
SPEED_DROP_COEFFICIENT = 3.0
DROP_VELOCITY = 5.0

# Obstacle types (offline_sprite_definitions.ts)
# yPos in Chromium is from canvas top; we convert to bottom-up
OBSTACLE_TYPES = [
    {
        "name": "cactus_small",
        "width": 17,
        "height": 35,
        "y": 0,  # ground level
        "multiple_speed": 4,
        "min_gap": 120,
        "min_speed": 0,
    },
    {
        "name": "cactus_large",
        "width": 25,
        "height": 50,
        "y": 0,  # ground level
        "multiple_speed": 7,
        "min_gap": 120,
        "min_speed": 0,
    },
    {
        "name": "pterodactyl",
        "width": 46,
        "height": 40,
        "y_options": [0, 25, 50],  # ground, mid, high (bottom-up)
        "multiple_speed": 999,  # never groups
        "min_gap": 150,
        "min_speed": 8.5,
        "speed_offset": 0.8,
    },
]

# Collision box simplification: use single AABB per entity
# (Chromium uses multiple sub-boxes; we use a tighter single box)
TREX_COLLISION_RUNNING = {"x": 1, "y": 0, "w": 40, "h": 42}
TREX_COLLISION_DUCKING = {"x": 1, "y": 0, "w": 55, "h": 22}

MAX_OBSTACLES = 3
CLEAR_TIME_MS = 3000  # ms before obstacles start spawning


class DinoEnv(gym.Env):
    """
    Headless Chrome Dino game as a Gymnasium environment.

    Observation: 1D vector of game state features (normalized).
    Actions: 0 = do nothing, 1 = jump, 2 = duck

    The environment runs at an accelerated "logical frame" rate —
    no real-time delay, enabling ~100k steps/sec on CPU.
    """

    metadata = {"render_modes": ["human", "ansi"], "render_fps": 60}

    def __init__(self, render_mode: Optional[str] = None):
        super().__init__()
        self.render_mode = render_mode

        # Actions: 0=noop, 1=jump, 2=duck
        self.action_space = spaces.Discrete(3)

        # Observation: fixed-size feature vector
        # [speed, trex_y, trex_vy, is_jumping, is_ducking,
        #  obs1_dx, obs1_y, obs1_w, obs1_h, obs1_type,
        #  obs2_dx, obs2_y, obs2_w, obs2_h, obs2_type,
        #  obs3_dx, obs3_y, obs3_w, obs3_h, obs3_type]
        # All normalized to roughly [-1, 1]
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(20,), dtype=np.float32
        )

        self._rng = np.random.default_rng()
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        self.speed = INITIAL_SPEED
        self.distance = 0.0
        self.frame_count = 0

        # T-Rex state
        self.trex_y = 0.0  # ground = 0
        self.trex_vy = 0.0
        self.jumping = False
        self.ducking = False
        self.speed_drop = False

        # Obstacles: list of dicts
        self.obstacles: list[dict] = []
        self.time_since_last_obstacle = 0.0

        self.game_over = False
        self.score = 0.0

        return self._get_obs(), self._get_info()

    def step(self, action):
        assert not self.game_over, "Call reset() after game over"

        # --- Process action ---
        if action == 1 and not self.jumping:
            # Jump
            self.jumping = True
            self.ducking = False
            self.trex_vy = INITIAL_JUMP_VELOCITY
            self.speed_drop = False
        elif action == 2:
            # Duck
            if self.jumping:
                # Fast drop while in air
                self.speed_drop = True
            else:
                self.ducking = True
        else:
            if not self.jumping:
                self.ducking = False
            self.speed_drop = False

        # --- Update T-Rex physics ---
        if self.jumping:
            gravity = GRAVITY
            if self.speed_drop:
                # Faster fall when ducking in air
                self.trex_vy -= gravity * SPEED_DROP_COEFFICIENT
            else:
                self.trex_vy -= gravity

            self.trex_y += self.trex_vy

            if self.trex_y <= 0:
                self.trex_y = 0.0
                self.trex_vy = 0.0
                self.jumping = False
                self.speed_drop = False

        # --- Update speed ---
        if self.speed < MAX_SPEED:
            self.speed += ACCELERATION

        # --- Update obstacles ---
        # Move existing obstacles
        for obs in self.obstacles:
            speed_offset = obs.get("speed_offset", 0)
            obs["x"] -= self.speed - speed_offset

        # Remove off-screen obstacles
        self.obstacles = [o for o in self.obstacles if o["x"] + o["w"] > -50]

        # Spawn new obstacles
        self._maybe_spawn_obstacle()

        # --- Collision detection ---
        if self._check_collision():
            self.game_over = True
            reward = -10.0
            return self._get_obs(), reward, True, False, self._get_info()

        # --- Update counters ---
        self.frame_count += 1
        self.distance += self.speed
        self.score = self.distance / 10.0  # Roughly matches Chrome's scoring

        # Reward: proportional to speed (surviving at higher speed = more reward)
        reward = self.speed / MAX_SPEED

        return self._get_obs(), reward, False, False, self._get_info()

    def _maybe_spawn_obstacle(self):
        """Spawn obstacles following Chromium's gap/speed logic."""
        # Don't spawn during clear time
        if self.frame_count < (CLEAR_TIME_MS / 1000.0) * FPS:
            return

        # Check if we need a new obstacle
        if len(self.obstacles) > 0:
            last_obs = max(self.obstacles, key=lambda o: o["x"])
            # Chromium formula: gap = width * speed + minGap * gapCoefficient
            min_gap = round(last_obs["w"] * self.speed +
                            last_obs["min_gap"] * GAP_COEFFICIENT)
            max_gap = round(min_gap * MAX_GAP_COEFFICIENT)
            gap = min_gap + self._rng.random() * (max_gap - min_gap)
            if last_obs["x"] + last_obs["w"] + gap > CANVAS_WIDTH:
                return
        elif self.frame_count % 30 != 0:
            # Throttle initial spawn check
            return

        if len(self.obstacles) >= MAX_OBSTACLES:
            return

        # Choose obstacle type based on current speed
        eligible = [
            t for t in OBSTACLE_TYPES if self.speed >= t["min_speed"]
        ]
        if not eligible:
            return

        otype = eligible[self._rng.integers(len(eligible))]

        # Determine size (grouping for cacti)
        size = 1
        if otype["name"].startswith("cactus") and self.speed >= otype["multiple_speed"]:
            size = self._rng.integers(1, 4)  # 1-3

        # Determine y position
        if "y_options" in otype:
            y = otype["y_options"][self._rng.integers(len(otype["y_options"]))]
        else:
            y = otype["y"]

        obs = {
            "x": float(CANVAS_WIDTH),
            "y": float(y),
            "w": float(otype["width"] * size),
            "h": float(otype["height"]),
            "type": otype["name"],
            "min_gap": otype["min_gap"],
            "speed_offset": otype.get("speed_offset", 0),
        }
        self.obstacles.append(obs)

    def _check_collision(self) -> bool:
        """AABB collision between T-Rex and obstacles."""
        if self.ducking and not self.jumping:
            tx, ty = TREX_START_X + TREX_COLLISION_DUCKING["x"], self.trex_y
            tw, th = TREX_COLLISION_DUCKING["w"], TREX_COLLISION_DUCKING["h"]
        else:
            tx, ty = TREX_START_X + TREX_COLLISION_RUNNING["x"], self.trex_y
            tw, th = TREX_COLLISION_RUNNING["w"], TREX_COLLISION_RUNNING["h"]

        for obs in self.obstacles:
            ox, oy, ow, oh = obs["x"], obs["y"], obs["w"], obs["h"]

            # AABB overlap check
            if (tx < ox + ow and tx + tw > ox and
                    ty < oy + oh and ty + th > oy):
                return True

        return False

    def _get_obs(self) -> np.ndarray:
        """Build normalized observation vector."""
        obs = np.zeros(20, dtype=np.float32)

        # Game state
        obs[0] = self.speed / MAX_SPEED
        obs[1] = self.trex_y / 100.0  # normalize jump height
        obs[2] = self.trex_vy / INITIAL_JUMP_VELOCITY
        obs[3] = 1.0 if self.jumping else 0.0
        obs[4] = 1.0 if self.ducking else 0.0

        # Sort obstacles by distance (closest first)
        sorted_obs = sorted(
            [o for o in self.obstacles if o["x"] + o["w"] > TREX_START_X - 20],
            key=lambda o: o["x"]
        )

        for i, o in enumerate(sorted_obs[:3]):
            base = 5 + i * 5
            obs[base + 0] = (o["x"] - TREX_START_X) / CANVAS_WIDTH  # dx
            obs[base + 1] = o["y"] / 100.0  # y position
            obs[base + 2] = o["w"] / 100.0  # width
            obs[base + 3] = o["h"] / 100.0  # height
            # Type encoding: cactus_small=0.33, cactus_large=0.66, pterodactyl=1.0
            type_map = {"cactus_small": 0.33, "cactus_large": 0.66, "pterodactyl": 1.0}
            obs[base + 4] = type_map.get(o["type"], 0.0)

        return obs

    def _get_info(self):
        return {
            "score": self.score,
            "speed": self.speed,
            "distance": self.distance,
            "frame_count": self.frame_count,
        }

    def render(self):
        if self.render_mode == "ansi":
            return self._render_ansi()
        return None

    def _render_ansi(self) -> str:
        """Simple text rendering for debugging."""
        width = 80
        height = 10
        grid = [[" "] * width for _ in range(height)]

        # Ground line
        for x in range(width):
            grid[height - 1][x] = "-"

        # Scale factor
        sx = width / CANVAS_WIDTH
        sy = (height - 1) / 100.0

        # T-Rex
        tx = int(TREX_START_X * sx)
        ty = height - 2 - int(self.trex_y * sy)
        ty = max(0, min(height - 2, ty))
        char = "v" if self.ducking else "T"
        if 0 <= tx < width:
            grid[ty][tx] = char

        # Obstacles
        for obs in self.obstacles:
            ox = int(obs["x"] * sx)
            oy = height - 2 - int(obs["y"] * sy)
            oy = max(0, min(height - 2, oy))
            char = "^" if obs["type"] == "pterodactyl" else "#"
            if 0 <= ox < width:
                grid[oy][ox] = char

        lines = ["".join(row) for row in grid]
        lines.append(f"Score: {self.score:.0f}  Speed: {self.speed:.1f}  "
                      f"Y: {self.trex_y:.1f}  Obstacles: {len(self.obstacles)}")
        return "\n".join(lines)
