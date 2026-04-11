"""
Heuristic (rule-based) agent for Chrome Dino.

No ML — just speed-adaptive jump/duck timing. Reads game state via the
Runner JS API and applies reactive rules: jump when a ground obstacle is
within threshold distance, duck for pterodactyls, noop otherwise.

Supports both frame-stepped (deterministic) and real-time modes.

Usage:
    # Frame-stepped (deterministic, matches headless timing)
    python scripts/heuristic_agent.py --episodes 10

    # Real-time (actual Chrome framerate)
    python scripts/heuristic_agent.py --episodes 10 --realtime

Requires: ChromeDriver running on port 9515
    /mnt/c/Temp/chromedriver.exe --port=9515
"""

import argparse
import json
import shutil
import time

import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys

# ---------------------------------------------------------------------------
# Constants from Chromium source (matching src/env.py)
# ---------------------------------------------------------------------------
TREX_START_X = 25  # T-Rex left edge
TREX_WIDTH = 44
TREX_HEIGHT = 47
TREX_DUCK_HEIGHT = 25

# Pterodactyl Y thresholds (canvas yPos values)
# Low ptero: yPos ~75 (near ground — must duck)
# High ptero: yPos ~50 (high — can run under)
PTERO_DUCK_THRESHOLD = 65  # yPos > this → low-flying, must duck

# ---------------------------------------------------------------------------
# JavaScript: same frame-stepping hooks as validate_browser_framestepped.py
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

# Step N frames and return state (no action application — heuristic decides per-frame)
STEP_AND_READ_JS = """(function(nFrames, actionCode) {
    var r = Runner.getInstance();

    // Apply action
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
        playing: r.playing, crashed: r.crashed,
        speed: r.currentSpeed, distance: r.distanceRan,
        tRex: { y: r.tRex.yPos, jumping: r.tRex.jumping, ducking: r.tRex.ducking },
        groundY: r.tRex.groundYPos,
        obstacles: obs
    });
})"""

# Real-time state read (no stepping)
READ_STATE_JS = """return (function() {
    var r = Runner.getInstance();
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
        playing: r.playing, crashed: r.crashed,
        speed: r.currentSpeed, distance: r.distanceRan,
        tRex: { y: r.tRex.yPos, jumping: r.tRex.jumping, ducking: r.tRex.ducking },
        groundY: r.tRex.groundYPos,
        obstacles: obs
    });
})();"""


def heuristic_action(state: dict, trigger_scale: float = 1.0) -> int:
    """
    Decide action based on game state. Returns 0=noop, 1=jump, 2=duck.

    Args:
        state: Game state dict with tRex, speed, obstacles.
        trigger_scale: Multiplier for trigger distances (>1 for latency
            compensation in real-time mode).

    Strategy:
    - Find the nearest obstacle ahead of the T-Rex
    - If it's a low pterodactyl → duck
    - If it's a ground obstacle (cactus) → jump when within threshold
    - Threshold scales with speed (faster = trigger earlier)
    - If already jumping and obstacle is close, speed-drop to land faster
    """
    tRex = state["tRex"]
    speed = state["speed"]
    obstacles = state["obstacles"]

    # Filter to obstacles ahead of T-Rex
    ahead = [o for o in obstacles if o["x"] + o["w"] > TREX_START_X]
    if not ahead:
        return 0  # nothing to worry about

    # Sort by x position (nearest first)
    ahead.sort(key=lambda o: o["x"])
    nearest = ahead[0]

    # Distance from T-Rex right edge to obstacle left edge
    distance = nearest["x"] - (TREX_START_X + TREX_WIDTH)

    # Speed-adaptive trigger distance
    # At speed 6: trigger at ~120px. At speed 13: trigger at ~200px.
    # This gives roughly the same reaction time in seconds across speeds.
    jump_trigger = speed * 18 * trigger_scale
    duck_trigger = speed * 20 * trigger_scale

    is_pterodactyl = nearest["type"].lower() == "pterodactyl"
    is_low_ptero = is_pterodactyl and nearest["y"] > PTERO_DUCK_THRESHOLD
    is_high_ptero = is_pterodactyl and nearest["y"] <= PTERO_DUCK_THRESHOLD

    # High pterodactyls can be run under — ignore them
    if is_high_ptero:
        # But if there's a second obstacle right behind, consider it
        if len(ahead) > 1:
            nearest = ahead[1]
            distance = nearest["x"] - (TREX_START_X + TREX_WIDTH)
            is_pterodactyl = nearest["type"].lower() == "pterodactyl"
            is_low_ptero = is_pterodactyl and nearest["y"] > PTERO_DUCK_THRESHOLD
        else:
            return 0

    # Duck for low pterodactyls
    if is_low_ptero and distance < duck_trigger:
        return 2  # duck

    # Jump for ground obstacles (cacti and ground-level pteros we missed above)
    if not is_pterodactyl and distance < jump_trigger and distance > 0:
        if not tRex["jumping"]:
            return 1  # jump
        # If already jumping and descending near an obstacle, speed drop
        # to land faster and avoid the next one
        return 0

    # If jumping and there's a cactus ahead that we've already cleared,
    # speed drop to land and be ready for the next obstacle
    if tRex["jumping"] and distance < 0:
        return 2  # speed drop to land faster

    return 0


def connect_to_chrome():
    """Connect to ChromeDriver and navigate to dino game."""
    chrome_options = Options()
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=800,400")
    chrome_options.add_argument("--no-sandbox")

    if not shutil.which("google-chrome"):
        # WSL → Windows ChromeDriver
        driver = webdriver.Remote(
            command_executor="http://localhost:9515",
            options=chrome_options,
        )
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get("chrome://dino")
    except Exception:
        pass  # ERR_INTERNET_DISCONNECTED expected

    time.sleep(2)

    check = driver.execute_script(
        "return typeof Runner !== 'undefined' ? 'found' : 'not_found';")
    if check != "found":
        body = driver.find_element("tag name", "body")
        body.send_keys(Keys.SPACE)
        time.sleep(1)
        check = driver.execute_script(
            "return typeof Runner !== 'undefined' ? 'found' : 'not_found';")
    print(f"Runner: {check}")
    return driver


def run_framestepped(driver, episodes: int, frame_skip: int, debug: bool):
    """Run heuristic agent in frame-stepped mode."""
    scores = []
    need_full_reload = False

    for ep in range(episodes):
        print(f"\nEpisode {ep + 1}/{episodes}")

        # Full page reload if previous episode was stuck (RAF loop dead)
        if need_full_reload:
            try:
                driver.get("chrome://dino")
            except Exception:
                pass
            time.sleep(2)
            driver.execute_script(
                "return typeof Runner !== 'undefined' ? 'found' : 'not_found';")
            need_full_reload = False

        # Install hooks and start game
        driver.execute_script(INSTALL_HOOKS_JS)
        body = driver.find_element("tag name", "body")
        body.send_keys(Keys.SPACE)
        time.sleep(0.3)
        driver.execute_script(
            "var r=Runner.getInstance(); if(r.crashed) r.restart(); "
            "else if(!r.playing) r.playIntro();")
        time.sleep(0.3)

        # Warm up
        for _ in range(5):
            driver.execute_script(f"return {STEP_AND_READ_JS}(1, 0)")

        steps = 0
        max_steps = 15000
        stuck_threshold = 500  # bail if score unchanged for this many steps
        last_score = -1
        stuck_count = 0

        while steps < max_steps:
            # Read state without stepping (step 0 frames)
            result = driver.execute_script(
                f"return {STEP_AND_READ_JS}(0, 0)")
            if result is None:
                break
            state = json.loads(result)

            if state["crashed"]:
                score = round(state["distance"] * 0.025)
                scores.append(score)
                print(f"  Score: {score} ({steps} steps)")
                break

            # Stuck detection: if score hasn't changed, game loop may be dead
            current_score = state["distance"]
            if current_score == last_score:
                stuck_count += 1
                if stuck_count >= stuck_threshold:
                    print(f"  STUCK at step {steps} (score={round(current_score*0.025)} "
                          f"unchanged for {stuck_threshold} steps) — skipping")
                    need_full_reload = True
                    break
            else:
                stuck_count = 0
                last_score = current_score

            # Decide action
            action = heuristic_action(state)

            # Step with that action
            result = driver.execute_script(
                f"return {STEP_AND_READ_JS}({frame_skip}, {action})")
            if result is None:
                break
            state = json.loads(result)

            if state["crashed"]:
                score = round(state["distance"] * 0.025)
                scores.append(score)
                print(f"  Score: {score} ({steps} steps)")
                break

            if debug and state["obstacles"] and steps < 300:
                o = state["obstacles"][0]
                dx = o["x"] - (TREX_START_X + TREX_WIDTH)
                act_names = ["noop", "jump", "duck"]
                print(
                    f"  [dbg] step={steps} act={act_names[action]} "
                    f"speed={state['speed']:.2f} "
                    f"obs_type={o['type']} dx={dx:.0f} "
                    f"trex_y={state['tRex']['y']:.0f} "
                    f"jumping={state['tRex']['jumping']}")

            steps += 1
            if steps % 500 == 0:
                print(f"  step {steps}, speed={state['speed']:.1f}, "
                      f"score={round(state['distance']*0.025)}")

        time.sleep(0.5)

    return scores


def run_realtime(driver, episodes: int, debug: bool):
    """Run heuristic agent in real-time mode.

    Injects the heuristic logic directly into Chrome's game loop as JS,
    eliminating Selenium roundtrip latency entirely. The heuristic runs at
    the game's native ~60fps. Selenium only starts episodes and polls for
    completion.
    """
    scores = []

    # JS heuristic injected into Chrome's rAF loop — runs before each game
    # frame, ensuring actions take effect before collision detection.
    INJECT_HEURISTIC_JS = """(function() {
        var TREX_START_X = 25;
        var TREX_WIDTH = 44;
        var PTERO_DUCK_THRESHOLD = 65;

        // Clear previous hooks
        if (window.__heuristicActive) return;
        window.__heuristicActive = true;

        var realRAF = window.requestAnimationFrame;
        window.requestAnimationFrame = function(callback) {
            return realRAF(function(timestamp) {
                // Run heuristic BEFORE the game frame
                var r = Runner.getInstance();
                if (r && r.playing && !r.crashed) {
                    var obstacles = r.horizon ? r.horizon.obstacles : [];
                    var ahead = [];
                    for (var i = 0; i < obstacles.length; i++) {
                        if (obstacles[i].xPos + obstacles[i].width > TREX_START_X) {
                            ahead.push(obstacles[i]);
                        }
                    }

                    if (ahead.length) {
                        ahead.sort(function(a, b) { return a.xPos - b.xPos; });
                        var nearest = ahead[0];
                        var distance = nearest.xPos - (TREX_START_X + TREX_WIDTH);
                        var speed = r.currentSpeed;
                        var jump_trigger = speed * 25;
                        var duck_trigger = speed * 28;

                        var isPtero = nearest.typeConfig.type.toLowerCase() === 'pterodactyl';
                        var isLowPtero = isPtero && nearest.yPos > PTERO_DUCK_THRESHOLD;
                        var isHighPtero = isPtero && nearest.yPos <= PTERO_DUCK_THRESHOLD;

                        if (isHighPtero && ahead.length > 1) {
                            nearest = ahead[1];
                            distance = nearest.xPos - (TREX_START_X + TREX_WIDTH);
                            isPtero = nearest.typeConfig.type.toLowerCase() === 'pterodactyl';
                            isLowPtero = isPtero && nearest.yPos > PTERO_DUCK_THRESHOLD;
                            isHighPtero = false;
                        } else if (isHighPtero) {
                            // noop — clear duck state
                            if (r.tRex.ducking && !r.tRex.jumping) r.tRex.setDuck(false);
                            if (r.tRex.speedDrop) r.tRex.speedDrop = false;
                            callback(timestamp);
                            return;
                        }

                        if (isLowPtero && distance < duck_trigger) {
                            if (r.tRex.jumping) {
                                r.tRex.setSpeedDrop();
                            } else if (!r.tRex.ducking) {
                                r.tRex.setDuck(true);
                            }
                        } else if (!isPtero && distance < jump_trigger && distance > 0) {
                            if (!r.tRex.jumping) {
                                if (r.tRex.ducking) r.tRex.setDuck(false);
                                r.tRex.startJump(speed);
                            }
                        } else if (r.tRex.jumping && distance < 0) {
                            // Obstacle passed — speed drop to land faster
                            r.tRex.setSpeedDrop();
                        } else {
                            if (r.tRex.ducking && !r.tRex.jumping) r.tRex.setDuck(false);
                            if (r.tRex.speedDrop) r.tRex.speedDrop = false;
                        }
                    } else {
                        if (r.tRex.ducking && !r.tRex.jumping) r.tRex.setDuck(false);
                        if (r.tRex.speedDrop) r.tRex.speedDrop = false;
                    }
                }

                // Call original game frame
                callback(timestamp);
            });
        };
    })();"""

    for ep in range(episodes):
        print(f"\nEpisode {ep + 1}/{episodes}")

        # Full page reload for clean rAF state
        try:
            driver.get("chrome://dino")
        except Exception:
            pass
        time.sleep(2)

        # Inject heuristic into rAF loop BEFORE starting the game
        driver.execute_script(INJECT_HEURISTIC_JS)

        # Start the game
        body = driver.find_element("tag name", "body")
        body.send_keys(Keys.SPACE)
        time.sleep(0.5)

        # Poll for completion (low frequency - just checking if crashed)
        max_wait = 120  # seconds
        poll_hz = 2  # only need to check 2x/sec
        for _ in range(max_wait * poll_hz):
            time.sleep(1.0 / poll_hz)
            result = driver.execute_script(READ_STATE_JS)
            if result is None:
                break
            state = json.loads(result)
            if state["crashed"]:
                score = round(state["distance"] * 0.025)
                scores.append(score)
                print(f"  Score: {score}")
                break
            if not state["playing"]:
                break

        # Clean up — need full page reload to restore original rAF
        time.sleep(0.5)

    return scores


def main():
    parser = argparse.ArgumentParser(
        description="Heuristic agent for Chrome Dino")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--frame-skip", type=int, default=2,
                        help="Game frames per decision step (frame-stepped mode)")
    parser.add_argument("--realtime", action="store_true",
                        help="Run in real-time instead of frame-stepped")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    driver = connect_to_chrome()
    mode = "real-time" if args.realtime else "frame-stepped"

    try:
        if args.realtime:
            scores = run_realtime(driver, args.episodes, args.debug)
        else:
            scores = run_framestepped(
                driver, args.episodes, args.frame_skip, args.debug)
    finally:
        driver.quit()

    if scores:
        scores_arr = np.array(scores)
        print(f"\n{'='*50}")
        print(f"Heuristic Agent — {mode} ({len(scores_arr)} episodes)")
        print(f"{'='*50}")
        print(f"Score: mean={scores_arr.mean():.0f}, "
              f"max={scores_arr.max():.0f}, min={scores_arr.min():.0f}")
        if len(scores_arr) > 1:
            print(f"Std: {scores_arr.std():.0f}, "
                  f"Median: {np.median(scores_arr):.0f}")
        print(f"\nComparison:")
        print(f"  2018 supervised CNN: best=1810")
        print(f"  2023 DQN: mean=~555")
        print(f"  2026 PPO headless: mean=591")
        print(f"  2026 PPO frame-stepped: mean=439")
        print(f"  2026 PPO real-time: mean=64")


if __name__ == "__main__":
    main()
