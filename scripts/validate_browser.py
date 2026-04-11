"""
Validate the trained PPO model against the real Chrome Dino game in browser.

Uses Selenium to open chrome://dino, injects JavaScript to read game state
directly from the Runner instance (no OCR, no screen capture), and feeds
the model's actions as keyboard events.

Usage:
    python scripts/validate_browser.py --model models/ppo_dino_v1/best/best_model.zip [--episodes 5]

Requires: Google Chrome, Selenium, webdriver-manager
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from stable_baselines3 import PPO
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.env import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    INITIAL_JUMP_VELOCITY,
    MAX_SPEED,
    TREX_HEIGHT,
    TREX_START_X,
)

# JavaScript to extract game state from the Runner singleton.
# The Chromium dino game (2024+ refactor) uses a module-scoped Runner class.
# We access it via the global `Runner.instance_` or window.__runner__.
EXTRACT_STATE_JS = """(function() {
    var r = Runner.getInstance();
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
})();
"""

# JavaScript to start/restart the game
START_GAME_JS = """
(function() {
    var r = Runner.getInstance();
    if (r.crashed) {
        r.restart();
    } else if (!r.playing) {
        // Initial start — simulate spacebar to begin
        r.playIntro();
    }
})();
"""


def game_state_to_obs(state: dict, ground_y: float) -> np.ndarray:
    """Convert browser game state to our 20-dim observation format."""
    obs = np.zeros(20, dtype=np.float32)

    obs[0] = state["speed"] / MAX_SPEED

    # Convert canvas Y (top-down, ground_y = ground position) to our bottom-up
    # ground_line = groundYPos + TREX_HEIGHT (93 + 47 = 140 in Chrome)
    ground_line = ground_y + TREX_HEIGHT
    trex = state["tRex"]
    trex_y_bottomup = max(0, ground_y - trex["y"])
    obs[1] = trex_y_bottomup / 100.0
    # Estimate velocity from position (we don't have direct access)
    obs[2] = 0.0  # Will be noisy but acceptable
    obs[3] = 1.0 if trex["jumping"] else 0.0
    obs[4] = 1.0 if trex["ducking"] else 0.0

    # Obstacles — sort by x position (closest first)
    browser_obs = sorted(state["obstacles"], key=lambda o: o["x"])
    # Filter to only obstacles ahead of or at the T-Rex
    browser_obs = [o for o in browser_obs if o["x"] + o["w"] > TREX_START_X - 20]

    for i in range(3):
        base = 5 + i * 5
        if i < len(browser_obs):
            o = browser_obs[i]
            obs[base + 0] = (o["x"] - TREX_START_X) / CANVAS_WIDTH
            # Convert obstacle Y to bottom-up using ground_line
            obstacle_y_bottomup = max(0, ground_line - o["y"] - o["h"])
            obs[base + 1] = obstacle_y_bottomup / 100.0
            obs[base + 2] = o["w"] / 100.0
            obs[base + 3] = o["h"] / 100.0
            type_map = {
                "cactusSmall": 0.33,
                "cactusLarge": 0.66,
                "pterodactyl": 1.0,
            }
            obs[base + 4] = type_map.get(o["type"], 0.33)
        else:
            obs[base + 0] = 1.0  # sentinel: no obstacle
            obs[base + 1] = 0.0
            obs[base + 2] = 0.0
            obs[base + 3] = 0.0
            obs[base + 4] = 0.0

    return obs


def main():
    parser = argparse.ArgumentParser(description="Validate model on real Chrome Dino")
    parser.add_argument("--model", type=str, required=True, help="Path to model zip")
    parser.add_argument("--episodes", type=int, default=5, help="Number of games to play")
    parser.add_argument("--slow", action="store_true", help="Add delay between actions for visibility")
    args = parser.parse_args()

    model = PPO.load(args.model, device="cpu")

    # Set up Chrome
    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=800,400")
    # --no-sandbox: required for WSL2/CI, only runs trusted chrome://dino
    chrome_options.add_argument("--no-sandbox")

    # WSL2: connect to a running Windows ChromeDriver server
    # Start it first: /mnt/c/Temp/chromedriver.exe --port=9515
    if not shutil.which("google-chrome"):
        chromedriver_url = "http://localhost:9515"
        driver = webdriver.Remote(
            command_executor=chromedriver_url,
            options=chrome_options,
        )
    else:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Navigate to the dino game
        # chrome://dino triggers ERR_INTERNET_DISCONNECTED which shows the game
        # We navigate to any non-existent URL to trigger the offline page
        try:
            driver.get("chrome://dino")
        except Exception:
            pass  # Expected: net::ERR_INTERNET_DISCONNECTED
        time.sleep(2)

        # The game should be loaded — verify by checking for Runner
        check = driver.execute_script("""
            return typeof Runner !== 'undefined' ? 'found' : 'not_found';
        """)
        if check != "found":
            # Try to activate it by pressing space
            body = driver.find_element("tag name", "body")
            body.send_keys(Keys.SPACE)
            time.sleep(1)
            check = driver.execute_script("""
                return typeof Runner !== 'undefined' ? 'found' : 'not_found';
            """)
        print(f"Runner: {check}")

        scores = []
        for ep in range(args.episodes):
            print(f"\nEpisode {ep + 1}/{args.episodes}", flush=True)

            try:
                # Start the game — press SPACE for initial start, restart() for re-play
                body = driver.find_element("tag name", "body")
                body.send_keys(Keys.SPACE)
                time.sleep(0.5)
                driver.execute_script(START_GAME_JS)
                time.sleep(0.5)

                # Verify game is playing
                for _ in range(10):
                    check = driver.execute_script("return Runner.getInstance().playing")
                    if check:
                        break
                    body.send_keys(Keys.SPACE)
                    time.sleep(0.3)

                print(f"  Game playing: {check}", flush=True)

                steps = 0
                prev_trex_y = 0.0
                max_steps = 10000  # safety limit
                state = {"distance": 0}
                ducking = False
                actions = ActionChains(driver)

                while steps < max_steps:
                    try:
                        # Read game state
                        result = driver.execute_script(f"return {EXTRACT_STATE_JS}")
                        if result is None:
                            print(f"  [warn] null result at step {steps}", flush=True)
                            time.sleep(0.1)
                            steps += 1
                            continue
                        state = json.loads(result)
                    except Exception as e:
                        print(f"  [warn] state read error: {e}", flush=True)
                        time.sleep(0.1)
                        continue

                    if state["crashed"]:
                        score = state["distance"] / 10.0
                        scores.append(score)
                        print(f"  Score: {score:.0f} ({steps} steps)", flush=True)
                        time.sleep(1)
                        break

                    if not state["playing"]:
                        time.sleep(0.1)
                        continue

                    # Convert to observation
                    obs = game_state_to_obs(state, state["groundY"])

                    # Estimate velocity from position change
                    trex = state["tRex"]
                    trex_y_bottomup = max(0, state["groundY"] - trex["y"])
                    obs[2] = (trex_y_bottomup - prev_trex_y) / INITIAL_JUMP_VELOCITY
                    prev_trex_y = trex_y_bottomup

                    # Get action from model
                    action, _ = model.predict(obs, deterministic=True)
                    action = int(action)

                    # Execute action — duck requires holding the key
                    if action == 2 and not ducking:
                        ActionChains(driver).key_down(Keys.ARROW_DOWN).perform()
                        ducking = True
                    elif action != 2 and ducking:
                        ActionChains(driver).key_up(Keys.ARROW_DOWN).perform()
                        ducking = False
                    if action == 1:  # Jump
                        body.send_keys(Keys.ARROW_UP)

                    steps += 1
                    if steps % 100 == 0:
                        print(f"  step {steps}, speed={state['speed']:.1f}, obs={len(state['obstacles'])}", flush=True)
                    if args.slow:
                        time.sleep(0.05)
                    else:
                        time.sleep(1 / 60)  # ~60fps polling
                else:
                    print(f"  Episode hit max steps ({max_steps})", flush=True)
                    scores.append(state.get("distance", 0) / 10.0)

            except Exception as e:
                print(f"  [ERROR] Episode failed: {e}", flush=True)
                import traceback
                traceback.print_exc()

        # Print results
        if scores:
            scores = np.array(scores)
            print(f"\n{'='*50}")
            print(f"Browser Validation ({len(scores)} episodes)")
            print(f"{'='*50}")
            print(f"Score: mean={scores.mean():.0f}, max={scores.max():.0f}, min={scores.min():.0f}")
            print(f"\nHeadless eval for comparison: mean=2247, max=4729")
            ratio = scores.mean() / 2247 * 100
            print(f"Browser/Headless ratio: {ratio:.0f}%")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
