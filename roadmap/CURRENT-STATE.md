# chrome-dino — Current State

**Phase Status**: Blocked: Strategy pivot needed — incremental physics fixes not converging, requires human decision on approach

## What Exists

- `src/env.py` — Headless Dino game environment (Gymnasium), v3 with action_delay, frame_skip, speed-dependent jump, endJump velocity cap
- `scripts/train.py` — PPO training pipeline with v2 env params via CLI
- `scripts/evaluate.py` — Model evaluation with v2 env params via CLI
- `scripts/validate_browser.py` — Browser validation with adaptive sleep, action delay buffer, debug output
- `models/ppo_dino_v3/` — v3 model (best at ~875K steps, training continuing to 2M)
- `models/ppo_dino_v2/` — Archived v2 model (headless mean=2340, browser mean=210)
- `models/ppo_dino_v1/` — Archived v1 model (headless mean=2247, browser mean=190)
- `logs/ppo_dino_v3/` — TensorBoard training logs
- `tests/test_env_v2.py` — 37 tests for v2/v3 env features (all pass)
- `2018-implementation/` — Archived: supervised CNN (TensorFlow)
- `2023-implementation/` — Archived: DQN + Selenium + OCR
- `project-history.md` — Development narrative / debugging journal
- `.github/` — Copilot agents, prompts, hooks, instructions
- `docs/` — Vision lock, architecture, ADRs, reference docs

## Results

### v3 Headless (50 episodes, action_delay=1, frame_skip=2, endJump cap)

| Metric | Value |
|--------|-------|
| Mean score | 2,365 |
| Max score | 4,479 |
| Min score | 1,869 |
| Note | Best model at ~875K steps; more robust than v2 (min 1869 vs 733) |

### v3 Browser Validation (10 episodes) — FAILED

| Metric | Value |
|--------|-------|
| Mean score | 256 |
| Max score | 423 |
| Min score | 190 |
| Transfer | **10.8%** |
| Verdict | **Marginal improvement over v2. Approach not converging.** |

### Transfer Ratio Trend (not converging)

| Version | Physics Fix | Headless Mean | Browser Mean | Transfer |
|---------|-------------|---------------|--------------|----------|
| v1 | None | 2,247 | 190 | 8.5% |
| v2 | action_delay, frame_skip, speed-dep jump | 2,340 | 210 | 9.0% |
| v3 | + endJump velocity cap | 2,365 | 256 | 10.8% |
| **Target** | | | **>555** | **>23.5%** |

### v3 Training Progress (still running, PID 186111)

| Metric | Value |
|--------|-------|
| Progress | ~1.3M / 2M steps (66%) |
| Eval mean (5ep) | ~1,750 (plateau since ~800K) |
| Best model | ~875K steps (mean_eval=1,943) |

## Critical Finding — Timing Mismatch is the Real Gap

The endJump velocity cap was NOT the primary bottleneck. After implementing it and validating in browser, the root cause is a **systematic timing mismatch**:

- **Trained**: frame_skip=2 → model expects 2.0 game frames per step (33.3ms at 60fps)
- **Browser**: Chrome under Selenium runs at ~51fps → only **1.70 game frames per step** (28.3ms)
- **15% systematic temporal error** — not fixable by physics constant tuning
- Over a 16-step jump arc, the obstacle is **33px behind** where the model expects
- The dino lands on obstacles that haven't passed underneath yet

Evidence:
- Measured obstacle Δx per step: **11.7px** (expected: 13.7px at 2 frames × speed 6.86)
- Effective frames/step: **1.70** (target: 2.00)
- This explains ALL three failure versions — the timing, not physics constants, dominates

The 2023 DQN scored 555 because it trained directly in the browser, learning actual Chrome timing.

## Strategy Pivot — Human Decision Needed

Three options, in order of recommended leverage:

### Option 1: JS Frame-Stepping (OQ-002) — recommended first
Inject JS to pause Chrome's `requestAnimationFrame` loop and step the game frame-by-frame from Python. Makes browser timing identical to headless. Current v3 model should work with zero retraining. **Definitive diagnostic**: proves whether physics are correct or reveals remaining bugs.
- Tradeoff: Game runs in slow-motion (not real-time)
- Effort: ~1 session to implement

### Option 2: Train with Measured Browser Timing
Measure Chrome's actual frame interval distribution, set frame_skip or add fractional frame_skip to match. Retrain with realistic timing parameters.
- Tradeoff: Another training cycle. Timing may vary across machines.

### Option 3: Domain Randomization on Frame Timing
Train with frame_skip sampled from [1, 3] each step. Produces policy robust to timing variance.
- Tradeoff: Slower convergence, may compromise peak headless performance.

## What Was Done This Session

### Slice 1: v2 Browser Validation & Timing Debugging
1. Started ChromeDriver, ran v2 model in browser → mean=210 (no improvement over v1)
2. Added `--debug` flag, discovered agent ducking when it should jump
3. Measured step timing: ~1.8 game frames per poll vs target 2
4. Added adaptive sleep timing, action delay FIFO buffer, `--step-pad-ms` CLI arg
5. Improved to mean=259, but still consistently jumping too early

### Slice 2: Full Observation Comparison
6. Dumped full 20-dim obs vectors in both environments
7. Found observations were near-identical — same obs → same decisions
8. But Chrome trex_y peaked at 64 vs headless 99 — dino 35% lower in browser

### Slice 3: Chrome Jump Physics Deep Dive & endJump Cap
9. Injected JS to capture Chrome's actual frame-by-frame jump data
10. Discovered endJump velocity cap in `trex.ts:483-520`
11. Implemented cap in env.py, added 7 new tests (37 total, all pass)
12. Fixed `--action-delay` default in validate_browser.py (1→0, Selenium adds ~1 frame)

### Slice 4: Documentation & Review
13. Updated ADR-001 with endJump cap section
14. Added endJump cap to glossary
15. Added journal narrative to project-history.md
16. Addressed all reviewer findings (Math.round comment, pytest.approx, speed_drop test)

### Slice 5: v3 Training & Evaluation
17. Started v3 training: 2M steps, same params, with endJump cap active
18. Headless eval of best model (50ep): mean=2365, max=4479, min=1869

### Slice 6: v3 Browser Validation — FAILED
19. Browser validation (10ep): mean=256, max=423 — only marginal improvement
20. Obstacle movement analysis: 1.70 frames/step vs expected 2.00 (Chrome ~51fps)
21. Concluded: timing mismatch dominates, not physics constants

### Slice 7: Strategic Analysis
22. Quantified non-convergence: 8% → 9% → 11% transfer across three iterations
23. Identified root cause: deterministic fixed-timestep sim vs stochastic variable-timestep browser
24. Proposed three strategy pivots (JS frame-stepping, measured timing, domain randomization)
25. **Set status to Blocked — human decision needed on strategy pivot**

## Success Target

**Browser mean score > 555** — must beat the 2023 DQN implementation.

## Decisions Made This Session

- ADR-001: action_delay=1, frame_skip=2, speed-dependent jump for v2
- endJump velocity cap: MIN_JUMP_HEIGHT=30, MAX_JUMP_HEIGHT=63 (from Chromium source)
- validate_browser.py --action-delay default 0 (Selenium already adds ~1 frame of latency)
- Resolved OQ-001: use both action delay and frame skip together
- Training defaults: action_delay=1, frame_skip=2, clear_time_ms=500
- **Strategic: incremental physics fixes not converging → need strategy pivot**

## Blocked / Unresolved

- **BLOCKING**: Strategy pivot decision — which approach to take (see options above)
- v3 training still running (PID 186111, ~1.3M/2M) but results may not matter if strategy changes
- OQ-002: JS frame-stepping — now the recommended next step
- OQ-003: Domain randomization — an alternative approach

## Files Modified This Session

- `src/env.py` — endJump velocity cap (MIN_JUMP_HEIGHT, MAX_JUMP_HEIGHT, reached_min_height), Math.round comment, parenthesized condition
- `scripts/validate_browser.py` — action delay buffer, adaptive sleep, step-pad-ms, debug output, action-delay default fix
- `tests/test_env_v2.py` — 7 new endJump cap tests (37 total), pytest.approx fix, speed_drop interaction test
- `docs/architecture/decisions/001-env-v2-sim-to-real-fixes.md` — endJump cap section
- `docs/architecture/overview.md` — v3 endJump cap note
- `docs/reference/glossary.md` — endJump cap definition
- `project-history.md` — Journal narrative of debugging session
- `docs/reference/glossary.md` — endJump cap definition
- `project-history.md` — Journal narrative of debugging session
