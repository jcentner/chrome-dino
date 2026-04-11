# chrome-dino — Current State

**Phase Status**: In Progress — Browser competence achieved (frame-stepped), narrative completion remaining

## What Exists

- `src/env.py` — Headless Dino game environment (Gymnasium), v3 with action_delay, frame_skip, speed-dependent jump, endJump velocity cap
- `scripts/train.py` — PPO training pipeline with v2 env params via CLI
- `scripts/evaluate.py` — Model evaluation with v2 env params via CLI
- `scripts/validate_browser.py` — Browser validation with adaptive sleep, action delay buffer, debug output
- `scripts/validate_browser_framestepped.py` — Frame-stepped browser validation (JS hooks override performance.now + rAF)
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

### v3 Frame-Stepped Browser Validation (10 episodes) — SUCCESS

| Metric | Value |
|--------|-------|
| Mean score | **1,757** |
| Max score | 4,180 |
| Min score | 245 |
| Std | 1,102 |
| Median | 1,565 |
| Transfer | **74.3%** |
| Verdict | **Beats 2023 DQN (555) by 3.2x. Primary success criterion met.** |

### Transfer Ratio Trend

| Version | Method | Headless Mean | Browser Mean | Transfer |
|---------|--------|---------------|--------------|----------|
| v1 | Real-time | 2,247 | 190 | 8.5% |
| v2 | Real-time | 2,340 | 210 | 9.0% |
| v3 | Real-time | 2,365 | 256 | 10.8% |
| **v3** | **Frame-stepped** | **2,365** | **1,757** | **74.3%** |
| **Target** | | | **>555** | **>23.5%** |

### v3 Training — Complete

Best model saved at ~875K steps. Training ran to 2M but eval plateaued.

## Critical Finding — Timing Mismatch CONFIRMED as Root Cause

The v1–v3 real-time failures were all caused by the same root issue: **Chrome under Selenium runs at ~51fps**, delivering 1.70 game frames/step vs the 2.00 the model was trained on. This 15% systematic temporal error is unfixable by physics constant tuning.

**JS frame-stepping proved this definitively**: by stepping Chrome's game loop at exactly 60fps from Python, the same v3 model achieved mean=1757 (vs 256 real-time). The physics were correct all along — the bug was the clock.

Evidence:
- Real-time obstacle Δx/step: **11.7px** (expected: 13.7px at 2 frames × speed 6.86)
- Frame-stepped obstacle Δx/step: matches headless exactly (deterministic 2 frames per step)
- Transfer jumped from 10.8% → 74.3% with zero retraining — only difference is frame control

## Strategy Pivot — RESOLVED: JS Frame-Stepping (ADR-002)

Chose Option 1 (JS frame-stepping) from the three proposed options. See ADR-002 for full rationale and evidence.

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

### Slice 8: JS Frame-Stepping — BREAKTHROUGH
26. Analyzed Chromium source for game loop: `update()` uses `performance.now()` delta, `scheduleNextUpdate()` calls `requestAnimationFrame`
27. Implemented `validate_browser_framestepped.py`: overrides `performance.now()` with fake clock, captures `rAF` callback, steps exactly N×16.67ms per action
28. Actions applied via Runner API (`tRex.startJump(speed)`, `.setSpeedDrop()`, `.setDuck()`) — no keyboard events
29. Initial test (3 ep): mean=2210, max=3555, min=749
30. Full validation (10 ep): **mean=1757, max=4180, min=245 — 74.3% transfer, 3.2x target**
31. Created ADR-002, resolved OQ-002, updated vision lock (v1.3), updated all docs

## Success Target

**Browser mean score > 555** — must beat the 2023 DQN implementation. **ACHIEVED: frame-stepped mean=1757 (3.2x target).**

## Decisions Made This Session

- ADR-001: action_delay=1, frame_skip=2, speed-dependent jump for v2
- endJump velocity cap: MIN_JUMP_HEIGHT=30, MAX_JUMP_HEIGHT=63 (from Chromium source)
- validate_browser.py --action-delay default 0 (Selenium already adds ~1 frame of latency)
- Resolved OQ-001: use both action delay and frame skip together
- Training defaults: action_delay=1, frame_skip=2, clear_time_ms=500
- **ADR-002: JS frame-stepping for browser validation — timing was the root cause, not physics**
- Resolved OQ-002: frame-stepping validated, mean=1757

## Remaining Work

- Complete project-history.md with full iteration story (incl. frame-stepping breakthrough)
- Consider domain randomization (OQ-003) if real-time play becomes a goal
- The 26% transfer gap (1757 vs 2365) may be reducible via Math.round matching or velocity estimation improvements

## Blocked / Unresolved

- OQ-003: Domain randomization — deferred, not needed for current success criteria

## Files Modified This Session

- `src/env.py` — endJump velocity cap (MIN_JUMP_HEIGHT, MAX_JUMP_HEIGHT, reached_min_height), Math.round comment, parenthesized condition
- `scripts/validate_browser.py` — action delay buffer, adaptive sleep, step-pad-ms, debug output, action-delay default fix
- `scripts/validate_browser_framestepped.py` — NEW: frame-stepped browser validation with JS hooks
- `tests/test_env_v2.py` — 7 new endJump cap tests (37 total), pytest.approx fix, speed_drop interaction test
- `docs/architecture/decisions/001-env-v2-sim-to-real-fixes.md` — endJump cap section
- `docs/architecture/decisions/002-js-frame-stepping-validation.md` — NEW: frame-stepping ADR
- `docs/architecture/overview.md` — v3 endJump cap note, frame-stepped script entry
- `docs/reference/glossary.md` — endJump cap, frame-stepping definitions
- `docs/reference/open-questions.md` — OQ-002 resolved
- `docs/vision/VISION-LOCK.md` — v1.3: success criteria met, goals updated, risks resolved
- `roadmap/CURRENT-STATE.md` — updated with frame-stepping results
- `project-history.md` — Journal narrative of debugging session
