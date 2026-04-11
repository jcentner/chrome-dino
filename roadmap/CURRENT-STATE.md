# chrome-dino — Current State

**Phase Status**: Blocked: v2 retraining scheduled for next session — human approved plan, no code changes remaining this session

## What Exists

- `src/env.py` — Headless Dino game environment (Gymnasium), physics from Chromium source
- `scripts/train.py` — PPO training pipeline with parallel envs, eval callbacks
- `scripts/evaluate.py` — Model evaluation with score statistics
- `scripts/validate_browser.py` — Browser validation via Selenium + JS game state extraction
- `models/ppo_dino_v1/` — Trained PPO model (best + final checkpoints)
- `logs/ppo_dino_v1/` — TensorBoard training logs
- `2018-implementation/` — Archived: supervised CNN (TensorFlow)
- `2023-implementation/` — Archived: DQN + Selenium + OCR
- `project-history.md` — Development narrative for blog post adaptation
- `.github/` — Copilot agents, prompts, hooks, instructions
- `docs/` — Vision lock, architecture, reference docs

## Results

### Headless Evaluation (100 episodes)

| Metric | Value |
|--------|-------|
| Mean score | 2,247 |
| Max score | 4,729 |
| Training time | ~40 minutes (2M steps) |
| Random baseline | ~70 score |
| Improvement | 13x over random |

### Browser Validation v1 (5 episodes, Chrome 147) — FAILED

| Metric | Value |
|--------|-------|
| Mean score | 190 |
| Max score | 204 |
| Browser/Headless ratio | **8%** |
| Verdict | **Worse than both prior implementations (2018: ~200, 2023: ~555)** |

The headless score is meaningless. The browser score of 190 is the real metric. See `docs/reference/sim-to-real-analysis.md` for full root cause analysis.

## What Went Wrong

The headless environment trained a policy that doesn't transfer to the real Chrome Dino game. Root causes identified (see analysis doc):

1. **Action latency** — Trained at frame-perfect execution, deployed with 1-2 frame delay via Selenium
2. **Missing speed-dependent jump** — Chrome's jump gets 12-28% higher as speed increases; our env jumps constant height
3. **Observation mapping bug** — Pterodactyl Y coordinates mapped wrong in validate_browser.py
4. **clearTime mismatch** — Trained with 500ms, Chrome uses 3000ms

## Plan: v2 Retraining

Priority-ordered fixes to close the sim-to-real gap:

1. **Add action delay to env** — Buffer actions by 1-2 frames to simulate Selenium latency
2. **Add frame skip** — Each env.step() advances 2-3 game frames, matching browser polling rate
3. **Speed-dependent jump velocity** — `jump_velocity = initial - speed/10` (from Chromium source)
4. **Fix observation mapping** — Use `ground_line = groundYPos + TREX_HEIGHT` for obstacle Y conversion
5. **Match clearTime** — Use Chrome's 3000ms (or make configurable)
6. **Retrain** — 2-4M timesteps with corrected env
7. **Revalidate in browser** — Target: mean > 555 (beats 2023 DQN)

## Success Target

**Browser mean score > 555** — must beat the 2023 DQN implementation that was trained directly in the browser. This is the minimum bar. A good result would be mean > 1000.

## Decisions Made

- Headless Python environment over browser automation (100,000x faster training)
- PPO over DQN (more stable, better for continuous speed ramp)
- 20-dim feature vector over screen capture
- **Browser score is the primary metric**, not headless score
- Headless score only matters insofar as it predicts browser performance

## Blocked / Unresolved

Nothing — all fixes are implementable.

## Files Modified This Session

- `docs/reference/sim-to-real-analysis.md` — Created: root cause analysis
- `docs/vision/VISION-LOCK.md` — v1.2: browser score as primary metric
- `roadmap/CURRENT-STATE.md` — Revised: phase not complete
- `project-history.md` — Updated honestly
- `docs/reference/tech-debt.md` — Added env fidelity items
- `docs/reference/open-questions.md` — Added approach questions
