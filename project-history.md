# Project History — Chrome Dino AI

*Narrative context for a blog post. Three attempts at the same problem, eight years apart.*

## The Setup

Chrome Dino is the little T-Rex game that shows up when Chrome can't reach the internet. Jump cacti, duck pterodactyls, survive as the speed ramps up. Simple game, surprisingly good RL benchmark.

I've now built an AI to play it three times: 2018, 2023, and 2026. Each attempt reflects where I was technically and what tools were available. The progression tells a story about how AI development has changed.

## Attempt 1: 2018 — Supervised Learning (2 months)

**Context**: Undergrad AI class final project. Barely knew what a neural network was beyond lecture slides.

**Approach**: The most naive possible. I played the game myself while a script captured screenshots and recorded my keyboard input. Built a labeled dataset of "screen → jump/don't jump." Trained a CNN in TensorFlow to predict my button presses from screen captures.

**What happened**: It took two months. Most of that was fighting TensorFlow GPU setup on Windows, figuring out screen capture timing, and generating enough training data by hand (I played a *lot* of Chrome Dino). The model worked — barely. It learned to mimic my reaction patterns but couldn't generalize beyond the speeds I'd trained on.

**What I learned**: Supervised learning is the wrong paradigm for this. You're training the model to copy a human, not to play the game. The ceiling is your own skill level, and the floor is however badly you label the data.

## Attempt 2: 2023 — DQN + OCR + Selenium (2 days)

**Context**: Working professional, more experience with ML. Switched to reinforcement learning — the right paradigm for game-playing agents.

**Approach**: Custom Gym environment wrapping a real Chrome browser via Selenium. Screen capture with `mss`, grayscale preprocessing with OpenCV, game-over detection using Tesseract OCR on a cropped region. DQN (Deep Q-Network) from Stable-Baselines3. Two actions: jump or do nothing.

**What happened**: Got it working in a couple days. DQN trained to ~170k of a 360k target. The agent learned basic cactus avoidance. But training was painfully slow — about 1 effective FPS because every step required a browser screenshot, OCR processing, and a Selenium keyboard command. The OCR game-over detection was fragile (lighting, font rendering, threshold sensitivity). Windows-only due to `pydirectinput`. No ducking action, so pterodactyls were instant death.

**What I learned**: The environment was the bottleneck. Wrapping a real browser for RL training is like trying to learn to drive by remote-controlling a car through a webcam. Technically possible, practically miserable. Also: OCR for game state detection is a terrible idea when you could just... read the game state.

## Attempt 3: 2026 — PPO + Headless Clone (one session, built by AI)

**Context**: Senior AI Engineer. This time, I didn't write the code — GitHub Copilot did, running in autonomous mode.

**Approach**: 
- **Environment**: Headless Python recreation of Chrome Dino, with physics constants pulled directly from [Chromium source](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/neterror/resources/dino_game/). No browser, no screenshots, no OCR. Pure game logic running at ~100k+ steps/second.
- **Algorithm**: PPO (Proximal Policy Optimization) instead of DQN. Better sample efficiency, more stable training, handles the continuous speed ramp naturally.
- **Observations**: 20-dimensional feature vector (speed, trex position/velocity, up to 3 nearest obstacles with type/position/size). No CNN needed — the game state is simple enough that a small MLP works.
- **Actions**: Three (noop, jump, duck) — pterodactyls are now survivable.
- **Training**: 16 parallel environments, 2M timesteps on an RTX 3070 Ti.

**What happened**: Training took about 40 minutes total (2M timesteps at ~3,000 FPS). The learning curve told the real story:

- **0–350k steps**: Random-level performance. The agent didn't understand jumping needed timing.
- **350k–500k**: First breakthrough — the agent learned to jump when obstacles were close (reward doubled).
- **500k–1M**: Steady improvement, learning to handle different obstacle types and groupings.
- **1M–1.5M**: Crossed the 1000-score threshold, started handling pterodactyls.
- **1.5M–2M**: Converged around mean score 1700+ with peaks above 3000.

**Final evaluation (100 episodes):**

| Metric | Value |
|--------|-------|
| Mean score | 2,247 |
| Max score | 4,729 |
| Min score | 721 |
| Median | 2,149 |
| 90th percentile | 2,778 |
| Mean episode length | 2,972 steps (~50 seconds) |
| Improvement over random | 13x |

The agent learned to consistently survive for nearly a minute of game time, handling speed increases, mixed obstacle types, and the narrowing reaction windows at high speed. At its best, it scored 4,729 — well into "good human player" territory.

**Two bugs found and fixed during training:**
1. The obstacle gap formula was wrong — `minGap * gapCoefficient` instead of Chromium's `width * speed + minGap * gapCoefficient`. This made obstacles 2–3x too dense, essentially impossible to survive.
2. The observation vector used 0.0 for both "no obstacle" and "obstacle at T-Rex position." The agent couldn't distinguish between safety and imminent death. Fixed with sentinel values.

**Key decisions the agent made**:
1. Headless clone over browser automation — 100,000x faster training
2. Feature vector over screen capture — the game state is 20 numbers, not 640×480 pixels
3. PPO over DQN — more stable, better for this environment structure
4. Ducking action — the 2023 version couldn't handle pterodactyls at all
5. Constants from Chromium source — not guessed, not reverse-engineered, read from the actual TypeScript

## The Evolution

| | 2018 | 2023 | 2026 |
|---|---|---|---|
| **Time to build** | 2 months | 2 days | ~1 hour |
| **Algorithm** | Supervised CNN | DQN | PPO |
| **Environment** | Screen capture + manual labels | Selenium + OCR | Headless physics clone |
| **Training speed** | N/A (offline) | ~1 FPS | ~3,000+ FPS |
| **Actions** | Jump | Jump | Jump, Duck, Noop |
| **Best score** | ~200 (limited by my skill) | ~555 (170k/360k steps) | 4,729 (2M steps) |
| **Mean score** | Unknown | Unknown | 2,247 (headless) / 190 (browser) |
| **Who wrote it** | Me (undergrad, 2 months) | Me (professional, 2 days) | AI agent (I chose options, ~1 hour) |
| **Platform** | Windows only | Windows only | Linux (any OS) |

### Browser Validation

The headless environment is only useful if the agent's behavior transfers to the real game. Validation: Selenium opens `chrome://dino` in Windows Chrome, JavaScript reads the Runner instance's game state (position, speed, obstacles), the model predicts an action, and Selenium sends the keystroke.

Results (5 episodes, Chrome 147):

| Metric | Value |
|--------|-------|
| Mean score | 190 |
| Max score | 204 |
| Min score | 186 |
| Headless mean | 2,247 |
| Browser/Headless ratio | 8% |

The agent consistently clears multiple obstacles (~3x random baseline of ~70). The score gap is entirely explained by latency: the model was trained at frame-perfect step timing, but the Selenium→Chrome→JS→Python round-trip introduces ~3-20ms per action cycle, giving the agent ~20Hz polling instead of 60fps. At speed 7+, that delay means the agent sees obstacles jump 21px between observations instead of 7px. It still plays recognizably well — it jumps cacti, times landings, and reacts to obstacle spacing. The physics transfer is valid; the bottleneck is the bridge.

## What This Shows

The interesting story isn't "AI plays game." That's been done. The story is the progression:

1. **2018**: I didn't know enough to pick the right approach. Supervised learning for a game is like memorizing answers instead of learning math. But I learned fundamentals — data collection, model training, the gap between theory and making something work.

2. **2023**: I knew the right approach (RL) but was still fighting the environment. Screen capture, OCR, browser automation — all of it was overhead that had nothing to do with the actual learning problem. The engineering dominated the science.

3. **2026**: The AI agent made the same architectural decisions I would have — but faster, and it wrote all the code. The bottleneck moved from "can I implement this?" to "do I know what to ask for?" The value shifted entirely to judgment calls: which algorithm, what observation space, headless vs browser.

Each version is 10x faster to build and produces better results. The skill that matters changed from "can you code a neural network" to "do you know which neural network to code" to "can you evaluate whether the AI picked the right one."

## Technical Notes

### Environment Fidelity
The headless environment uses constants directly from Chromium's TypeScript source (`offline.ts`, `trex.ts`, `offline_sprite_definitions.ts`):
- Speed: 6.0 → 13.0, acceleration 0.001/frame
- Jump: velocity=10, gravity=0.6
- Obstacles: small cactus (17×35), large cactus (25×50), pterodactyl (46×40) at three heights
- Collision: AABB (simplified from Chromium's multi-box system)
- Gap coefficient: 0.6, clear time: 3000ms

### PPO Configuration
- Policy: MLP [256, 256] with ReLU
- Learning rate: 3e-4
- Batch size: 256, n_steps: 2048
- Gamma: 0.99, GAE lambda: 0.95
- Entropy coefficient: 0.02

### Hardware
- CPU: Intel i7-12700K
- GPU: NVIDIA RTX 3070 Ti (8GB)
- RAM: 32GB
- Note: MLP policy is CPU-bound; GPU mostly idle for this workload
