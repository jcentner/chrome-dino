"""
Chrome Dino game environment — Gymnasium wrapper around the real Chrome game.

Uses JS frame-stepping to control Chrome's game loop deterministically,
eliminating timing artifacts. Each step advances Chrome by exactly N×16.67ms.

Observation: Same 20-dim vector as the headless DinoEnv, extracted from
    Chrome's actual game state.
Actions: 0=noop, 1=jump, 2=duck

This is SLOW (~30 steps/sec) compared to the headless env (~100K steps/sec)
but trains on the REAL game — zero sim-to-real gap by definition.

Usage:
    from src.chrome_env import ChromeDinoEnv
    env = ChromeDinoEnv(frame_skip=4)  # fewer steps needed, faster training
"""

import json
import shutil
import time
from typing import Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys

# ---------------------------------------------------------------------------
# Observation constants — must match DinoEnv for model compatibility
# ---------------------------------------------------------------------------
MAX_SPEED = 13.0
CANVAS_WIDTH = 600
TREX_HEIGHT = 47
# Chrome's T-Rex starts at xPos=25 (vs headless TREX_START_X=50).
# We use Chrome's actual value for accurate observation computation.
CHROME_TREX_X = 25

# ---------------------------------------------------------------------------
# JavaScript hooks (shared with validate_browser_framestepped.py)
# ---------------------------------------------------------------------------
INSTALL_HOOKS_JS = """(function() {
    window.__fakeClock = performance.now();
    window.__frameMs = 1000.0 / 60.0;
    window.__realPerfNow = performance.now.bind(performance);
    performance.now = function() { return window.__fakeClock; };
    window.__rafCallback = null;
    window.__realRAF = window.requestAnimationFrame;
    window.requestAnimationFrame = function(cb) {
        window.__rafCallback = cb;
        return 0;
    };
    window.cancelAnimationFrame = function() {};
    window.__hookInstalled = true;
})();
"""

STEP_AND_READ_JS = """(function(nFrames, actionCode) {
    var r = Runner.getInstance();

    if (actionCode === 1 && !r.tRex.jumping) {
        r.tRex.startJump(r.currentSpeed);
    } else if (actionCode === 2) {
        if (r.tRex.jumping) {
            r.tRex.setSpeedDrop();
        } else if (!r.tRex.ducking) {
            r.tRex.setDuck(true);
        }
    } else if (actionCode === 0) {
        if (r.tRex.ducking && !r.tRex.jumping) {
            r.tRex.setDuck(false);
        }
        if (r.tRex.speedDrop) {
            r.tRex.speedDrop = false;
        }
    }

    for (var i = 0; i < nFrames; i++) {
        if (r.crashed) break;
        window.__fakeClock += window.__frameMs;
        if (window.__rafCallback) {
            var cb = window.__rafCallback;
            window.__rafCallback = null;
            cb(window.__fakeClock);
        }
    }

    var tRex = r.tRex;
    var obstacles = r.horizon ? r.horizon.obstacles : [];
    var obs = [];
    for (var i = 0; i < Math.min(obstacles.length, 3); i++) {
        var o = obstacles[i];
        obs.push({
            x: o.xPos, y: o.yPos, w: o.width,
            h: o.typeConfig.height, type: o.typeConfig.type
        });
    }
    return JSON.stringify({
        playing: r.playing,
        crashed: r.crashed,
        speed: r.currentSpeed,
        distance: r.distanceRan,
        tRex: { y: tRex.yPos, jumping: tRex.jumping, ducking: tRex.ducking },
        groundY: tRex.groundYPos,
        obstacles: obs
    });
})"""


class ChromeDinoEnv(gym.Env):
    """Gymnasium wrapper around Chrome's actual Dino game via frame-stepping.

    Each step() call executes one Selenium roundtrip (~30ms). At frame_skip=4,
    each step advances 4 game frames (66.7ms game time) at ~30 steps/sec actual.

    Args:
        frame_skip: Game frames per step. Higher = fewer steps but coarser control.
            4 is a good default (matches 15Hz decision rate at 60fps game).
        chromedriver_url: ChromeDriver remote URL. Default: localhost:9515.
        max_steps: Episode step limit. Default: 3000 (~200s game time at frame_skip=4).
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        frame_skip: int = 4,
        chromedriver_url: str = "http://localhost:9515",
        max_steps: int = 3000,
    ):
        super().__init__()
        self.frame_skip = frame_skip
        self.chromedriver_url = chromedriver_url
        self.max_steps = max_steps

        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(20,), dtype=np.float32
        )

        self._driver = None
        self._ground_y: float = 93.0  # default, updated from Chrome
        self._prev_trex_y: float = 93.0
        self._step_count = 0
        self._prev_distance = 0.0
        self._stuck_count = 0
        self._needs_full_reload = True  # first reset always reloads

    def _connect(self):
        """Lazy-connect to Chrome."""
        if self._driver is not None:
            return

        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--window-size=800,400")
        chrome_options.add_argument("--no-sandbox")

        self._driver = webdriver.Remote(
            command_executor=self.chromedriver_url,
            options=chrome_options,
        )

        try:
            self._driver.get("chrome://dino")
        except Exception:
            pass  # ERR_INTERNET_DISCONNECTED expected
        time.sleep(2)

        # Verify Runner exists
        check = self._driver.execute_script(
            "return typeof Runner !== 'undefined' ? 'found' : 'not_found';")
        if check != "found":
            body = self._driver.find_element("tag name", "body")
            body.send_keys(Keys.SPACE)
            time.sleep(1)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._connect()

        if self._needs_full_reload:
            # Full page reload for clean state (first time or after stuck episode)
            try:
                self._driver.get("chrome://dino")
            except Exception:
                pass
            time.sleep(1.5)
            self._needs_full_reload = False
        else:
            # Fast restart: just reinstall hooks and restart game
            time.sleep(0.1)

        # Install hooks
        self._driver.execute_script(INSTALL_HOOKS_JS)

        # Start/restart game
        body = self._driver.find_element("tag name", "body")
        body.send_keys(Keys.SPACE)
        time.sleep(0.2)
        self._driver.execute_script(
            "var r=Runner.getInstance(); "
            "if(r.crashed) r.restart(); "
            "else if(!r.playing) r.playIntro();")
        time.sleep(0.2)

        # Warm up: let intro animation complete + T-Rex settle on ground
        for _ in range(30):
            self._driver.execute_script(f"return {STEP_AND_READ_JS}(1, 0)")

        # Read initial state
        result = self._driver.execute_script(f"return {STEP_AND_READ_JS}(0, 0)")
        state = json.loads(result)
        self._ground_y = state.get("groundY", 93.0)
        self._prev_trex_y = state["tRex"]["y"]
        self._step_count = 0
        self._prev_distance = state["distance"]
        self._stuck_count = 0

        obs = self._state_to_obs(state)
        info = self._state_to_info(state)
        return obs, info

    def step(self, action):
        action = int(action)
        assert 0 <= action <= 2

        # Step with action on first frame, continue-action on subsequent frames
        result = self._driver.execute_script(
            f"return {STEP_AND_READ_JS}({self.frame_skip}, {action})")

        if result is None:
            # Chrome session lost — treat as terminal
            return self._zero_obs(), -1.0, True, False, {"score": 0}

        state = json.loads(result)
        self._step_count += 1

        # Check termination
        crashed = state["crashed"]
        truncated = self._step_count >= self.max_steps

        # Stuck detection
        if state["distance"] == self._prev_distance:
            self._stuck_count += 1
            if self._stuck_count >= 200:
                truncated = True
                self._needs_full_reload = True  # rAF loop may be dead
        else:
            self._stuck_count = 0
            self._prev_distance = state["distance"]

        # Reward: proportional to speed (same as headless env)
        if crashed:
            reward = -1.0
        else:
            reward = state["speed"] * 0.01

        # Estimate velocity from position delta
        trex_y = state["tRex"]["y"]
        vel_canvas = trex_y - self._prev_trex_y  # negative = moving up
        self._prev_trex_y = trex_y

        obs = self._state_to_obs(state, vel_canvas)
        info = self._state_to_info(state)

        return obs, reward, crashed, truncated, info

    def _state_to_obs(self, state: dict, vel_canvas: float = 0.0) -> np.ndarray:
        """Convert Chrome game state to 20-dim observation."""
        obs = np.zeros(20, dtype=np.float32)

        # Game state
        obs[0] = state["speed"] / MAX_SPEED
        trex = state["tRex"]
        ground_y = state.get("groundY", self._ground_y)
        trex_y_up = max(0, ground_y - trex["y"])
        obs[1] = trex_y_up / 100.0

        # Velocity estimate (negative canvas delta = upward in headless)
        vel_norm = -(vel_canvas / self.frame_skip)  # per-frame velocity
        max_vel = 10.0 + MAX_SPEED / 10.0
        obs[2] = np.clip(vel_norm / max_vel, -1.0, 1.0)

        obs[3] = 1.0 if trex["jumping"] else 0.0
        obs[4] = 1.0 if trex["ducking"] else 0.0

        # Obstacles
        ground_line = ground_y + TREX_HEIGHT
        browser_obs = sorted(state["obstacles"], key=lambda o: o["x"])
        browser_obs = [o for o in browser_obs
                       if o["x"] + o["w"] > CHROME_TREX_X - 20]

        type_map = {
            "cactusSmall": 0.33, "cactusLarge": 0.66, "pterodactyl": 1.0,
            "CACTUS_SMALL": 0.33, "CACTUS_LARGE": 0.66, "PTERODACTYL": 1.0,
        }

        for i in range(3):
            base = 5 + i * 5
            if i < len(browser_obs):
                o = browser_obs[i]
                obs[base + 0] = (o["x"] - CHROME_TREX_X) / CANVAS_WIDTH
                obs[base + 1] = max(0, ground_line - o["y"] - o["h"]) / 100.0
                obs[base + 2] = o["w"] / 100.0
                obs[base + 3] = o["h"] / 100.0
                obs[base + 4] = type_map.get(o["type"], 0.0)
            else:
                obs[base + 0] = 1.0

        return obs

    def _state_to_info(self, state: dict) -> dict:
        return {
            "score": round(state["distance"] * 0.025),
            "speed": state["speed"],
            "distance": state["distance"],
            "step_count": self._step_count,
        }

    def _zero_obs(self) -> np.ndarray:
        obs = np.zeros(20, dtype=np.float32)
        obs[5] = obs[10] = obs[15] = 1.0  # max distance sentinels
        return obs

    def close(self):
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
