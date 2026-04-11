# chrome-dino — Current State

**Phase Status**: In Progress — v3 training running (endJump cap fix), browser validation pending

## What Exists

- `src/env.py` — Headless Dino game environment (Gymnasium), v3 with action_delay, frame_skip, speed-dependent jump, endJump velocity cap
- `scripts/train.py` — PPO training pipeline with v2 env params via CLI
- `scripts/evaluate.py` — Model evaluation with v2 env params via CLI
- `scripts/validate_browser.py` — Browser validation with adaptive sleep, action delay buffer, debug output
- `models/ppo_dino_v3/` — Training in progress (~875K/2M steps)
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

### v3 Training In Progress (action_delay=1, frame_skip=2, endJump cap)

| Metric | Value |
|--------|-------|
| Training progress | ~875K / 2M steps (43.7%) |
| Mean score (latest) | 1,943 |
| Max score (latest) | 3,004 |
| Min score (latest) | 1,429 |
| Trend | Steadily climbing |

### v2 Results (archived)

| Metric | Headless | Browser |
|--------|----------|---------|
| Mean score | 2,340 | 210 |
| Max score | 5,673 | 241 |
| Transfer | — | 9% |
| Verdict | **Similar to v1 in browser — endJump cap was missing** |

### v1 Results (archived)

| Metric | Headless | Browser |
|--------|----------|---------|
| Mean score | 2,247 | 190 |
| Transfer | — | 8% |

## Root Cause Found — endJump Velocity Cap

**The breakthrough**: Chrome's `trex.ts:483-520` caps upward velocity to `DROP_VELOCITY` (5.0) once the dino passes `maxJumpHeight`. This limits jump peak from ~101 (raw ballistic) to ~87 (with cap + Math.round). Our env had no such cap, so the model trained to rely on heights Chrome never allows.

**Discovery method**: Injected JS to capture Chrome's actual frame-by-frame jump data. Compared full 20-dim observation vectors between headless and browser — observations were near-identical, but Chrome trex_y peaked at 64-67 (polling) vs our 99-101 (no cap).

**Fix**: Added `MIN_JUMP_HEIGHT=30`, `MAX_JUMP_HEIGHT=63`, `reached_min_height` state variable. When `trex_y >= MAX_JUMP_HEIGHT` and `reached_min_height`, cap `trex_vy` to `DROP_VELOCITY=5.0`. Env peak now ~83 at speed 7.6 (Chrome ~87, ~4px difference from Math.round).

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

### Slice 5: v3 Training (in progress)
17. Started v3 training: 2M steps, same params, with endJump cap active
18. Training at ~875K steps, mean=1,943 and climbing

## Success Target

**Browser mean score > 555** — must beat the 2023 DQN implementation.

## What's Next

1. **Wait for v3 training** to complete (2M steps)
2. **Headless evaluation** of v3 best model (100 episodes)
3. **Browser validation** — `python scripts/validate_browser.py --model models/ppo_dino_v3/best/best_model.zip --episodes 10 --debug`
   - ChromeDriver: `/mnt/c/Temp/chromedriver.exe --port=9515`
4. **If browser > 555**: Phase 1 complete, enter vision expansion mode
5. **If still insufficient**: Consider domain randomization (OQ-003), JS frame-stepping (OQ-002)

## Decisions Made This Session

- ADR-001: action_delay=1, frame_skip=2, speed-dependent jump for v2
- endJump velocity cap: MIN_JUMP_HEIGHT=30, MAX_JUMP_HEIGHT=63 (from Chromium source)
- validate_browser.py --action-delay default 0 (Selenium already adds ~1 frame of latency)
- Resolved OQ-001: use both action delay and frame skip together
- Training defaults: action_delay=1, frame_skip=2, clear_time_ms=500

## Blocked / Unresolved

- v3 training in progress (PID 186111, ~875K/2M)
- OQ-002: JS frame-stepping — deferred pending v3 browser validation
- OQ-003: Domain randomization — deferred pending v3 browser validation

## Files Modified This Session

- `src/env.py` — endJump velocity cap (MIN_JUMP_HEIGHT, MAX_JUMP_HEIGHT, reached_min_height), Math.round comment
- `scripts/validate_browser.py` — action delay buffer, adaptive sleep, step-pad-ms, debug output, action-delay default fix
- `tests/test_env_v2.py` — 7 new endJump cap tests (37 total), pytest.approx fix
- `docs/architecture/decisions/001-env-v2-sim-to-real-fixes.md` — endJump cap section
- `docs/reference/glossary.md` — endJump cap definition
- `project-history.md` — Journal narrative of debugging session
