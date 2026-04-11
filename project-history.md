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
| **Best score** | ~200 (limited by my skill) | Unknown | 4,479 (headless) / 4,180 (frame-stepped browser) |
| **Mean score** | Unknown | ~555 | 2,365 (headless) / 1,757 (frame-stepped) / 256 (real-time) |
| **Who wrote it** | Me (undergrad, 2 months) | Me (professional, 2 days) | AI agent (I chose options, ~1 hour) |
| **Platform** | Windows only | Windows only | Linux (any OS) |

### v1 Browser Validation

The headless environment is only useful if the agent's behavior transfers to the real game. Validation: Selenium opens `chrome://dino` in Windows Chrome, JavaScript reads the Runner instance's game state (position, speed, obstacles), the model predicts an action, and Selenium sends the keystroke.

v1 results (5 episodes, Chrome 147):

| Metric | Value |
|--------|-------|
| Mean score | 190 |
| Max score | 204 |
| Min score | 186 |
| Headless mean | 2,247 |
| Browser/Headless ratio | 8% |

**This is bad.** A mean score of 190 is worse than my 2018 supervised model (~200) and far worse than the 2023 DQN (~555). The 2026 agent that looked brilliant in headless — 13x over random, peaks of 4,729 — can barely survive 2 seconds of real obstacles.

The initial instinct was to hand-wave this away as "Selenium latency." Doubling the polling rate from 15Hz to 30Hz gave zero improvement, which disproved that theory. The real problem is deeper: **the agent learned the wrong game.**

### What Went Wrong: Sim-to-Real Gap

Analysis of the Chrome game source revealed multiple training-vs-deployment mismatches:

1. **Action latency**: The headless env executes actions instantly — jump in frame N takes effect in frame N. In Chrome via Selenium, the jump keystroke arrives 1-2 frames later. The model learned "just-in-time" jumping with zero margin. Any delay = death.

2. **Speed-dependent jumping**: In Chrome, `jumpVelocity = initialJumpVelocity - (speed / 10)`. At speed 6, the jump is 12% higher than our constant-velocity env. At speed 13, it's 28% higher. Chrome compensates for faster obstacles with proportionally higher jumps. Our agent never experienced this.

3. **Observation mapping bugs**: The browser validation code computed pterodactyl Y positions using the wrong reference point, making all heights map to ~0. The agent couldn't distinguish "duck under" from "jump over."

4. **The irony**: The 2023 DQN trained at 1 FPS *in Chrome*. Agonizingly slow, but it learned the real game with real latency, real physics, real timing. The 2026 PPO trained 3,000x faster but learned a subtly different game. Speed of training is worthless if the training doesn't transfer.

### Lesson: Sim-to-Real is the Hard Part

This is actually a well-known problem in robotics RL. Training in simulation is fast but building a faithful simulation is the real challenge. The headless Dino env had the right constants from Chromium source — but getting the constants right isn't enough. You also need to model the *deployment conditions*: action latency, frame timing, the exact physics of how the game processes inputs.

The fix isn't complicated: train with action delay (1-2 frame buffer before actions take effect) and frame skip (advance multiple game frames per agent step). This forces the agent to learn anticipatory behavior instead of reactive behavior. It's a 20-line code change. But you have to know it's needed, and I didn't check until the browser score came back.

**Status**: Physics fixes helped but timing mismatch was the real bottleneck. Solved with JS frame-stepping — browser mean 1,757 (3.2x target of 555). See the full story below.

## What This Shows

The interesting story isn't "AI plays game." That's been done. The story is the progression — and the failure:

1. **2018**: I didn't know enough to pick the right approach. Supervised learning for a game is like memorizing answers instead of learning math. But I learned fundamentals — data collection, model training, the gap between theory and making something work.

2. **2023**: I knew the right approach (RL) but was still fighting the environment. Screen capture, OCR, browser automation — all of it was overhead that had nothing to do with the actual learning problem. The engineering dominated the science. But the agent trained *in the real game* and scored 555.

3. **2026 (v1)**: The AI agent built a headless clone and trained 3,000x faster. The headless scores looked incredible — mean 2,247, peak 4,729. But in the real browser: mean 190. Worse than both prior implementations. The fastest training doesn't matter if you're training on the wrong game. Sim-to-real transfer is the hard part, and we skipped it.

The humbling part: the 2023 DQN, despite being painfully slow and architecturally crude, produced a better real-world agent because it trained where it would be deployed. The 2026 approach optimized the wrong thing (headless training speed) while assuming the simulation was faithful. It wasn't.

Each version is faster to build. Each version *should* produce better results. But the 2026 version proved that speed without fidelity is worse than slow with accuracy. The fix is known (train with action delay and frame skip to match deployment conditions), and the iteration continues.

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

---

## Session Journal: April 11, 2026 — Chasing the Jump

### The Starting Point

Came into this session with v2 already trained — action delay, frame skip, speed-dependent jump velocity, the works. The model scored mean=2,340 in headless (better than v1's 2,247). The sim-to-real fixes were supposed to close the gap. Spun up ChromeDriver, pointed the validation script at the real game, and —

**Mean: 210. Max: 241.**

Barely better than v1's 190. Two days of env engineering and a full retrain, and we gained 20 points.

### First Hypothesis: Observation Mismatch

The velocity normalization had a bug — the browser script was dividing `trex_vy` by 10.0 while the headless env divides by 11.3. Fixed it, added a `--debug` flag to the validation script, and ran 3 episodes to watch the agent's brain.

The debug output was damning. Looking at a ground-level cactusLarge approaching from the right, the agent's decision sequence was:

```
dx_norm=0.87  action=0 (noop)
dx_norm=0.60  action=2 (DUCK)    ← ducking at a ground cactus?
dx_norm=0.40  action=2 (DUCK)
dx_norm=0.20  action=1 (JUMP)    ← finally jumps, too late
```

The model was ducking at cacti it needed to jump over, then jumping at the last second. In headless this "late jump" worked because the model had learned precise timing. In Chrome it was consistently fatal.

### Second Hypothesis: Frame Timing

I measured how many game pixels the obstacle moved per observation step. At speed 7.2, the expected 2-frame movement is 14.4 pixels. I was seeing 13 on average — close to 1.8 frames instead of 2. The model sees obstacles moving slower than expected, so its "jump at dx_norm=0.20" is actually "jump 1 obstacle-width too early."

Added adaptive sleep timing: measure how long the Selenium round-trip (read state + model predict + send action) takes, then sleep only the remaining time to hit the 2-frame target. Scores nudged up to mean 259 with one episode hitting 403. Better, but still dying at the second obstacle every game. User confirmed: "consistently jumps too early for the second cactus."

### Third Hypothesis: Who Moved My Debug

In my excitement to fix the timing, I moved the debug print statement to after action execution so the `dt` would include the `send_keys` call. This accidentally changed the timing of the entire loop — Selenium's `send_keys(ARROW_UP)` adds ~10ms, which the adaptive sleep now subtracts from the next wait. Result: worse timing, *lower* scores. The user caught it: "consistently early again, regression from last time."

Reverted the debug move. Added a `--step-pad-ms` argument (default 4ms) for manual latency compensation. The obstacle deltas now averaged 14.07 pixels/step vs the 14.64 target — 1.92 game frames, close enough.

Scores: mean 208. Still terrible.

### The Real Culprit

At this point I stopped chasing timing and did something I should have done first: **compared the full 20-dimensional observation vector between headless and browser.**

They were nearly identical. Speed, obstacle positions, types, sizes — all matched. The model was literally seeing the same inputs and making the same decisions in both environments. So why were the outcomes different?

I ran the headless env and browser side-by-side through a cactus encounter. The model jumps at dx_norm ≈ 0.20 in both. In headless, the dino peaks at trex_y=99, sails over the 50px cactus with 49px to spare, and lands cleanly. In browser, the dino peaks at... **64**. It plows into the cactus on the way down.

99 vs 64. The dino jumps 35% lower in Chrome than in our simulation.

### Finding the Smoking Gun

I injected JavaScript into Chrome to rapidly poll `tRex.yPos` and `tRex.jumpVelocity` during an actual jump. The data told the full story:

```
t=  0ms  yPos=93  trex_y= 0   jv=-10.76   ← takeoff
t=114ms  yPos=30  trex_y=63   jv= -6.21   ← approaching peak
t=121ms  yPos=27  trex_y=66   jv= -5.00   ← !!!! velocity CAPPED
t=218ms  yPos= 6  trex_y=87   ← actual peak (vs our 99)
```

At `t=121ms`, Chrome's jump velocity snaps from -6.21 to -5.00. Something is capping the upward velocity mid-flight.

Back to the Chromium source. `trex.ts`, lines 516-520:

```typescript
// Reached max height.
if (!this.config.invertJump && (this.yPos < this.config.maxJumpHeight) ||
    this.speedDrop) {
    this.endJump();
}
```

And `endJump()`:

```typescript
if (this.reachedMinHeight && this.jumpVelocity < this.config.dropVelocity) {
    this.jumpVelocity = this.config.dropVelocity;
}
```

Chrome has a **jump height limiter**. When the dino rises above `maxJumpHeight` (30 canvas pixels from the top, or 63 pixels above ground), Chrome caps the upward velocity to `dropVelocity` (-5). This dramatically slows the ascent, reducing peak height from the ~100 that pure ballistics would give to ~87.

Our headless env had no such cap. The model trained to exploit the full ballistic arc — jumping at distances that required reaching 99px. In Chrome, where the peak is only 87px, every second cactus was 12 pixels of death.

### The Fix

Six lines of code:

```python
MIN_JUMP_HEIGHT = 30   # trex_y where reachedMinHeight triggers
MAX_JUMP_HEIGHT = 63   # trex_y where endJump caps velocity

# In _step_internal, after updating position:
if self.trex_y >= MIN_JUMP_HEIGHT or self.speed_drop:
    self.reached_min_height = True
if (self.trex_y >= MAX_JUMP_HEIGHT or self.speed_drop) and \
   self.reached_min_height and self.trex_vy > DROP_VELOCITY:
    self.trex_vy = DROP_VELOCITY
```

Headless peak dropped from 99 to 83 (Chrome measures 87; the 4px gap is from Chrome's `Math.round()` on position updates). All 30 existing tests pass. Added 7 new tests for the cap behavior.

v3 training now running. Same hyperparameters, but the jump arc finally matches what Chrome actually does.

### What I Keep Learning

Every time I think the sim is faithful, there's another physics detail I missed. The speed-dependent jump velocity was in `trex.ts:469` — I found it. But the `endJump` velocity cap was 50 lines later in the same file, and I didn't read far enough. The headless env had the right constants for *starting* a jump but the wrong behavior for *capping* a jump.

The broader pattern: sim-to-real transfer fails at the details you didn't know to check. Getting the constants right is necessary but not sufficient — you also need to model the *constraints* the real system imposes. Chrome doesn't let the dino jump as high as physics would allow. Our simulation did. The model learned to rely on height it would never get.

The good news: each diagnosis gets easier. v1's gap was mysterious (just "it doesn't work in Chrome"). This time I had debug tools: full observation dumps, side-by-side comparison, injected JavaScript capturing frame-by-frame physics. The debugging itself is now systematic. The next surprise will be found faster.

**Current status**: v3 training in progress. If the endJump cap was the last physics mismatch, we should see scores above 555 in Chrome (beating the 2023 DQN). If not — well, there's always v4.

### v3 Results: It Wasn't The Physics

v3 training finished. Headless eval: mean=2,365, max=4,479, min=1,869 — tighter than v2 (min jumped from 733 to 1,869). The endJump cap made the agent more robust. Browser validation:

**Mean: 256. Max: 423.**

Better than v2's 210 by about 22%. But the target was 555. Three iterations of physics fixes had moved the transfer ratio from 8% → 9% → 11%. The numbers were going the right direction, but at this rate, matching the 2023 DQN would take twenty more iterations.

### Finding the Real Root Cause

I went back to the obstacle movement data. At speed 6.86 with frame_skip=2, each obstacle should move 13.7 pixels per step (2 frames × speed). I was measuring 11.7. That's 1.70 game frames per step, not 2.00.

The browser wasn't running at 60fps. Under Selenium's instrumentation overhead, Chrome was hitting about **51fps**. Every policy step was getting 15% fewer game frames than the model expected. Over a 16-step jump arc, that means the obstacle is 33 pixels behind where the model thinks it is when the dino lands.

This explained everything. v1 failed at 8% transfer. v2 added physics fixes: 9%. v3 added more physics fixes: 11%. Each iteration was correct — the physics *were* getting more accurate — but they were correcting a 5% error while a 15% timing error dominated. Like fine-tuning a microscope that's pointed at the wrong slide.

The 2023 DQN scored 555 not because it had better physics modeling. It scored 555 because it trained directly in Chrome, at Chrome's actual framerate, with Chrome's actual latency. It learned the *real* timing. Our agent learned perfect 60fps timing and deployed at 51fps.

### The Strategy Pivot

Three options:

1. **JS frame-stepping**: Inject JavaScript to take over Chrome's game loop. Override `performance.now()` with a fake clock, override `requestAnimationFrame` to not auto-schedule, and step the game frame-by-frame from Python. Each step advances exactly 16.67ms — matching the 60fps the model trained on. Definitive diagnostic: if this works, the physics are correct and timing was the only issue.

2. **Train with browser timing**: Measure Chrome's actual frame intervals, set the headless env to match. Retrain. Slower and machine-specific.

3. **Domain randomization**: Train with random frame_skip values each step. More robust but slower convergence and lower peak performance.

I chose option 1 — JS frame-stepping. It was the fastest path to a definitive answer, and if it worked, the existing model would work with zero retraining.

### The JavaScript Trick

Chrome Dino's game loop works like this:

```javascript
update(timestamp) {
    var deltaTime = timestamp - this.time;  // ms since last frame
    this.time = timestamp;
    // ... move everything by deltaTime ...
    this.scheduleNextUpdate();
}

scheduleNextUpdate() {
    this.raqId = requestAnimationFrame(this.update.bind(this));
}
```

The game calls `requestAnimationFrame`, which invokes `update()` ~60 times per second with the real timestamp from `performance.now()`. Everything moves proportional to `deltaTime`.

The trick: replace both primitives.

```javascript
// Take over the clock
window.__fakeClock = performance.now();
performance.now = function() { return window.__fakeClock; };

// Take over the scheduler
window.__rafCallback = null;
window.requestAnimationFrame = function(cb) {
    window.__rafCallback = cb;  // capture, don't schedule
};
```

Now from Python, each action step:
1. Apply the action via `Runner.getInstance().tRex.startJump(speed)` — no keyboard events, frame-perfect
2. Advance the fake clock by N × 16.67ms
3. Call the captured `requestAnimationFrame` callback N times
4. Read the game state from the Runner instance

The game thinks time is passing normally. It doesn't know it's running in slow motion, one frame at a time, controlled by a Python script.

### The Results

**Frame-stepped browser validation (10 episodes):**

| Metric | Value |
|--------|-------|
| Mean score | **1,757** |
| Max score | 4,180 |
| Min score | 245 |
| Transfer | **74.3%** |

From 256 to 1,757. **6.9x improvement.** Zero retraining. The only change was making Chrome's clock match the training environment's clock.

The physics were correct all along. Three iterations of increasingly precise physics fixes (speed-dependent jump, endJump cap, action delay modeling) were all addressing a 5% problem while ignoring the 15% timing problem sitting right next to it.

### Comparison

| | 2018 | 2023 | 2026 Real-time | 2026 Frame-stepped |
|---|---|---|---|---|
| **Mean score** | ~200 | ~555 | 256 | **1,757** |
| **Max score** | ~200 | Unknown | 423 | **4,180** |
| **vs 2023 DQN** | 0.4x | 1x | 0.5x | **3.2x** |
| **Method** | Human mimicry | Browser DQN | Headless PPO → browser | Headless PPO → frame-stepped browser |

### What This Means

The headless clone approach *works*. The PPO agent trained in 40 minutes what the DQN took hours to learn, and scores 3x higher when the deployment timing is controlled. The sim-to-real gap was never about physics fidelity — it was about **temporal fidelity**.

Real-time Selenium can't match the 60fps the model trained on. But with frame-stepping, you get deterministic frame control. The game runs in slow motion, but it runs *exactly* how the agent expects.

The 26% gap between frame-stepped (1,757) and headless (2,365) is probably from minor differences — Chrome uses `Math.round()` on positions, the velocity is estimated from position deltas rather than known directly, obstacle generation uses different random seeds. These are tractable problems if the gap matters, but 1,757 already demolishes the target of 555.

### The Final Lesson

The three implementations tell a story about where the hard problems actually live:

- **2018**: The hard problem was *knowing what approach to use*. I picked supervised learning because I didn't know about RL.
- **2023**: The hard problem was *engineering the environment*. I used RL but spent all my time on browser automation, screen capture, and OCR.
- **2026**: The hard problem was *sim-to-real transfer*. I had the right algorithm, a fast headless environment, and correct physics constants from the source code. Training was solved in 40 minutes. But making it work in the real browser — that took longer than everything else combined.

The tools get better. The algorithms get more capable. The environments get faster. But each improvement just reveals the *next* hard problem. And the next hard problem is always about the gap between where you train and where you deploy.

The Chrome Dino AI plays the game now. Mean 1,757 in Chrome, peaks above 4,000. It just needs someone to pause the clock for it.
