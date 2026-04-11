# chrome-dino — Current State

**Phase Status**: Complete

## What Exists

- `src/env.py` — Headless Dino game environment (Gymnasium), physics from Chromium source
- `scripts/train.py` — PPO training pipeline with parallel envs, eval callbacks
- `scripts/evaluate.py` — Model evaluation with score statistics
- `models/ppo_dino_v1/` — Trained PPO model (best + final checkpoints)
- `logs/ppo_dino_v1/` — TensorBoard training logs
- `2018-implementation/` — Archived: supervised CNN (TensorFlow)
- `2023-implementation/` — Archived: DQN + Selenium + OCR
- `project-history.md` — Development narrative for blog post adaptation
- `.github/` — Copilot agents, prompts, hooks, instructions
- `docs/` — Vision lock, architecture, reference docs

## Results

| Metric | Value |
|--------|-------|
| Mean score (100 episodes) | 2,247 |
| Max score | 4,729 |
| Training time | ~40 minutes (2M steps) |
| Random baseline | ~70 score |
| Improvement | 13x over random |

## Decisions Made

- Headless Python environment over browser automation (ADR-worthy: 100,000x faster training)
- PPO over DQN (more stable, better for continuous speed ramp)
- 20-dim feature vector over screen capture (game state is simple)
- 3 actions (noop/jump/duck) — pterodactyl survival
- Obstacle gap formula from Chromium source: `width * speed + minGap * gapCoefficient`
- Reduced clear time (500ms vs 3000ms) for denser training signal
- Death penalty -10 with speed-proportional survival reward

## Next Steps

- [ ] Validate agent behavior on real Chrome Dino in browser
- [ ] Write blog post from project-history.md
- [ ] Potentially extend training or tune for higher scores

## Blocked / Unresolved

Nothing.

## Files Modified This Session

- `src/env.py` — Created and iterated (gap fix, reward fix, observation fix)
- `scripts/train.py` — Created
- `scripts/evaluate.py` — Created
- `requirements.txt` — Created
- `2023-implementation/` — Archived from root
- `README.md` — Rewritten
- `AGENTS.md` — Updated description
- `.github/copilot-instructions.md` — Rewritten with project context
- `docs/vision/VISION-LOCK.md` — Populated from template
- `roadmap/CURRENT-STATE.md` — Updated
- `project-history.md` — Created
