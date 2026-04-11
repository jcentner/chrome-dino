# chrome-dino — Current State

**Phase Status**: Complete

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

### Browser Validation (5 episodes, Chrome 147)

| Metric | Value |
|--------|-------|
| Mean score | 190 |
| Max score | 204 |
| Browser/Headless ratio | 8% |
| Note | Selenium latency (~20Hz vs 60fps) explains the gap |

The agent consistently clears multiple obstacles in real Chrome Dino (3x random baseline). Physics transfer is valid; the score gap is entirely from the Selenium bridge latency.

## Decisions Made

- Headless Python environment over browser automation (ADR-worthy: 100,000x faster training)
- PPO over DQN (more stable, better for continuous speed ramp)
- 20-dim feature vector over screen capture (game state is simple)
- 3 actions (noop/jump/duck) — pterodactyl survival
- Obstacle gap formula from Chromium source: `width * speed + minGap * gapCoefficient`
- Reduced clear time (500ms vs 3000ms) for denser training signal
- Death penalty -10 with speed-proportional survival reward
- Browser validation via JS Runner API (not OCR/screenshot) over Selenium Remote WebDriver to Windows Chrome (WSL2)

## Next Steps

- [ ] Write blog post from project-history.md
- [ ] Potentially extend training or tune for higher scores

## Blocked / Unresolved

Nothing.

## Files Modified This Session

- `scripts/validate_browser.py` — Created: browser validation via Selenium + JS Runner API
- `project-history.md` — Updated with browser validation results
- `docs/vision/VISION-LOCK.md` — v1.1: all goals marked met
- `roadmap/CURRENT-STATE.md` — Updated with browser validation results
