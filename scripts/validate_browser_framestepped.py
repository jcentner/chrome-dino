"""
Frame-stepped browser validation for the Chrome Dino PPO agent.

Instead of running in real-time (where Chrome's variable framerate causes
timing mismatches), this script injects JavaScript to take over Chrome's
game loop and step it exactly one frame at a time. Each frame advances
by exactly 1000/60 ≈ 16.67ms, matching the headless training environment.

This eliminates the timing mismatch that caused v1-v3 real-time validation
to fail (browser ~51fps vs the 60fps the model was trained on).

Usage:
    python scripts/validate_browser_framestepped.py \
        --model models/ppo_dino_v3/best/best_model.zip --episodes 10

Requires: ChromeDriver running on port 9515
    /mnt/c/Temp/chromedriver.exe --port=9515
"""

import argparse
import json
import shutil
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from stable_baselines3 import PPO

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.env import (
    CANVAS_WIDTH,
    INITIAL_JUMP_VELOCITY,
    MAX_SPEED,
    TREX_HEIGHT,
    TREX_START_X,
)

VEL_NORM = INITIAL_JUMP_VELOCITY + MAX_SPEED / 10.0

# ---------------------------------------------------------------------------
# JavaScript: install frame-stepping hooks
# ---------------------------------------------------------------------------
# This JS does three things:
# 1. Overrides performance.now() to return a controllable fake clock
# 2. Overrides requestAnimationFrame to NOT auto-schedule (we'll call manually)
# 3. Exposes window.__dinoStep(n) to advance n frames and return game state
INSTALL_HOOKS_JS = """(function() {
    // Fake clock starts at current time (may be real or previously overridden)
    window.__fakeClock = performance.now();
    window.__frameMs = 1000.0 / 60.0;  // 16.6667ms per frame

    // Override performance.now to return our controlled clock
    // Keep real reference for debugging: window.__realPerfNow
    var _realPerfNow = performance.now.bind(performance);
    window.__realPerfNow = _realPerfNow;
    performance.now = function() { return window.__fakeClock; };

    // Override requestAnimationFrame to capture the callback but NOT schedule it
    window.__rafCallback = null;
    window.__realRAF = window.requestAnimationFrame;
    window.requestAnimationFrame = function(cb) {
        window.__rafCallback = cb;
        return 0;  // dummy rAF ID
    };

    // Override cancelAnimationFrame as no-op (nothing to cancel)
    window.cancelAnimationFrame = function() {};

    window.__hookInstalled = true;
})();
"""

# ---------------------------------------------------------------------------
# JavaScript: advance N frames and return game state
# ---------------------------------------------------------------------------
# Each call to __dinoStep(n):
# 1. Sets the action (jump/duck/noop) via key simulation on Runner
# 2. Advances the fake clock by n * frameMs
# 3. Calls the captured rAF callback n times (each with 1-frame delta)
# 4. Returns the full game state as JSON
STEP_AND_READ_JS = """(function(nFrames, actionCode) {
    var r = Runner.getInstance();

    // Apply action BEFORE stepping
    // actionCode: 0=noop, 1=jump, 2=duck
    if (actionCode === 1 && !r.tRex.jumping) {
        // Simulate spacebar press event
        r.tRex.startJump(r.currentSpeed);
    } else if (actionCode === 2) {
        if (r.tRex.jumping) {
            // Speed drop (fast fall)
            r.tRex.setSpeedDrop();
        } else if (!r.tRex.ducking) {
            r.tRex.setDuck(true);
        }
    } else if (actionCode === 0) {
        // Release duck if ducking on ground
        if (r.tRex.ducking && !r.tRex.jumping) {
            r.tRex.setDuck(false);
        }
        // Release speed drop
        if (r.tRex.speedDrop) {
            r.tRex.speedDrop = false;
        }
    }

    // Step the game nFrames times
    for (var i = 0; i < nFrames; i++) {
        if (r.crashed) break;
        window.__fakeClock += window.__frameMs;
        if (window.__rafCallback) {
            var cb = window.__rafCallback;
            window.__rafCallback = null;
            cb(window.__fakeClock);
        }
    }

    // Read state
    var tRex = r.tRex;
    var obstacles = r.horizon ? r.horizon.obstacles : [];
    var obs = [];
    for (var i = 0; i < Math.min(obstacles.length, 3); i++) {
        var o = obstacles[i];
        obs.push({
            x: o.xPos,
            y: o.yPos,
            w: o.width,
            h: o.typeConfig.height,
            type: o.typeConfig.type
        });
    }
    return JSON.stringify({
        playing: r.playing,
        crashed: r.crashed,
        speed: r.currentSpeed,
        distance: r.distanceRan,
        tRex: {
            y: tRex.yPos,
            jumping: tRex.jumping,
            ducking: tRex.ducking
        },
        groundY: tRex.groundYPos,
        obstacles: obs
    });
})"""

# JavaScript to start/restart and immediately pause the auto-loop
START_GAME_JS = """(function() {
    var r = Runner.getInstance();
    if (r.crashed) {
        r.restart();
    } else if (!r.playing) {
        r.playIntro();
    }
    // Let one frame execute to initialize, then our hooks take over
    return r.playing;
})();
"""


def game_state_to_obs(state: dict, ground_y: float) -> np.ndarray:
    """Convert browser game state to 20-dim observation matching DinoEnv."""
    obs = np.zeros(20, dtype=np.float32)
    obs[0] = state["speed"] / MAX_SPEED

    trex = state["tRex"]
    trex_y_bottomup = max(0, ground_y - trex["y"])
    obs[1] = trex_y_bottomup / 100.0
    # velocity will be estimated from position delta
    obs[2] = 0.0
    obs[3] = 1.0 if trex["jumping"] else 0.0
    obs[4] = 1.0 if trex["ducking"] else 0.0

    ground_line = ground_y + TREX_HEIGHT
    browser_obs = sorted(state["obstacles"], key=lambda o: o["x"])
    browser_obs = [o for o in browser_obs if o["x"] + o["w"] > TREX_START_X - 20]

    for i in range(3):
        base = 5 + i * 5
        if i < len(browser_obs):
            o = browser_obs[i]
            obs[base + 0] = (o["x"] - TREX_START_X) / CANVAS_WIDTH
            obstacle_y_bottomup = max(0, ground_line - o["y"] - o["h"])
            obs[base + 1] = obstacle_y_bottomup / 100.0
            obs[base + 2] = o["w"] / 100.0
            obs[base + 3] = o["h"] / 100.0
            type_map = {"cactusSmall": 0.33, "cactusLarge": 0.66, "pterodactyl": 1.0}
            obs[base + 4] = type_map.get(o["type"], 0.0)
        else:
            obs[base + 0] = 1.0
    return obs


def main():
    parser = argparse.ArgumentParser(
        description="Frame-stepped browser validation for Chrome Dino PPO")
    parser.add_argument("--model", required=True, help="Path to model zip")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--frame-skip", type=int, default=2,
                        help="Game frames per policy step (must match training)")
    parser.add_argument("--action-delay", type=int, default=1,
                        help="Action delay buffer (must match training)")
    parser.add_argument("--debug", action="store_true",
                        help="Print per-step diagnostic data")
    args = parser.parse_args()

    model = PPO.load(args.model, device="cpu")

    # Connect to ChromeDriver
    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=800,400")
    chrome_options.add_argument("--no-sandbox")

    if not shutil.which("google-chrome"):
        driver = webdriver.Remote(
            command_executor="http://localhost:9515",
            options=chrome_options,
        )
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Navigate to dino game
        try:
            driver.get("chrome://dino")
        except Exception:
            pass

        time.sleep(2)

        # Verify Runner exists
        check = driver.execute_script(
            "return typeof Runner !== 'undefined' ? 'found' : 'not_found';")
        if check != "found":
            body = driver.find_element("tag name", "body")
            body.send_keys(Keys.SPACE)
            time.sleep(1)
            check = driver.execute_script(
                "return typeof Runner !== 'undefined' ? 'found' : 'not_found';")
        print(f"Runner: {check}")
        if check != "found":
            print("ERROR: Runner not found. Is chrome://dino loaded?")
            return

        scores = []
        for ep in range(args.episodes):
            print(f"\nEpisode {ep + 1}/{args.episodes}")

            # Install frame-stepping hooks
            driver.execute_script(INSTALL_HOOKS_JS)
            hooked = driver.execute_script("return window.__hookInstalled === true;")
            if not hooked:
                print("  ERROR: hooks not installed")
                continue

            # Start/restart the game
            body = driver.find_element("tag name", "body")
            body.send_keys(Keys.SPACE)
            time.sleep(0.3)
            driver.execute_script(START_GAME_JS)
            time.sleep(0.3)

            # Step a few frames to let the game fully initialize
            for _ in range(5):
                driver.execute_script(
                    f"return {STEP_AND_READ_JS}(1, 0)")

            # Verify playing
            playing = driver.execute_script(
                "return Runner.getInstance().playing;")
            print(f"  Playing: {playing}")
            if not playing:
                # Try pressing space and stepping again
                body.send_keys(Keys.SPACE)
                for _ in range(10):
                    driver.execute_script(
                        f"return {STEP_AND_READ_JS}(1, 0)")
                playing = driver.execute_script(
                    "return Runner.getInstance().playing;")
                print(f"  Playing (retry): {playing}")
                if not playing:
                    print("  ERROR: Could not start game")
                    continue

            steps = 0
            prev_trex_y = 0.0
            max_steps = 10000
            action_buffer = deque([0] * args.action_delay)

            while steps < max_steps:
                # Get action from model using previous state
                # (first step uses initial zero obs)
                if steps == 0:
                    # Read initial state
                    result = driver.execute_script(
                        f"return {STEP_AND_READ_JS}(0, 0)")
                    if result is None:
                        print("  WARN: null initial state")
                        break
                    state = json.loads(result)
                    obs = game_state_to_obs(state, state["groundY"])
                    trex_y_bottomup = max(0, state["groundY"] - state["tRex"]["y"])
                    prev_trex_y = trex_y_bottomup

                # Get model action
                action, _ = model.predict(obs, deterministic=True)
                action = int(action)

                # Action delay buffer
                action_buffer.append(action)
                effective_action = action_buffer.popleft()

                # Step the game with the effective action
                result = driver.execute_script(
                    f"return {STEP_AND_READ_JS}({args.frame_skip}, {effective_action})")

                if result is None:
                    print(f"  WARN: null state at step {steps}")
                    break

                state = json.loads(result)

                if state["crashed"]:
                    score = state["distance"] / 10.0
                    scores.append(score)
                    print(f"  Score: {score:.0f} ({steps} steps)")
                    break

                if not state["playing"]:
                    # Game stopped for some other reason
                    print(f"  Game stopped at step {steps}")
                    break

                # Build observation
                obs = game_state_to_obs(state, state["groundY"])
                trex_y_bottomup = max(0, state["groundY"] - state["tRex"]["y"])
                obs[2] = np.clip(
                    (trex_y_bottomup - prev_trex_y) / (VEL_NORM * args.frame_skip),
                    -1.0, 1.0,
                )
                prev_trex_y = trex_y_bottomup

                if args.debug and state["obstacles"] and steps < 300:
                    o = state["obstacles"][0]
                    dx_norm = obs[5]
                    print(
                        f"  [dbg] step={steps} act={action} eff={effective_action} "
                        f"speed={state['speed']:.2f} "
                        f"trex_y={trex_y_bottomup:.0f} "
                        f"obs_x={o['x']:.0f} obs_h={o['h']:.0f} "
                        f"obs_type={o['type']} "
                        f"dx_norm={dx_norm:.3f}")

                steps += 1
                if steps % 500 == 0:
                    print(f"  step {steps}, speed={state['speed']:.1f}, "
                          f"score={state['distance']/10:.0f}")
            else:
                scores.append(state.get("distance", 0) / 10.0)
                print(f"  Max steps reached, score={scores[-1]:.0f}")

            time.sleep(0.5)

        # Print results
        if scores:
            scores_arr = np.array(scores)
            print(f"\n{'='*50}")
            print(f"Frame-Stepped Browser Validation ({len(scores_arr)} episodes)")
            print(f"{'='*50}")
            print(f"Score: mean={scores_arr.mean():.0f}, "
                  f"max={scores_arr.max():.0f}, min={scores_arr.min():.0f}")
            if len(scores_arr) > 1:
                print(f"Std: {scores_arr.std():.0f}, "
                      f"Median: {np.median(scores_arr):.0f}")
            print(f"\nTarget: mean > 555 (2023 DQN baseline)")
            print(f"Real-time browser (v3): mean=256")
            print(f"Headless eval (v3): mean=2365")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
