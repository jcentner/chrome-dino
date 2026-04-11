# chrome-dino — Architecture Overview

## Overview

PPO agent that plays Chrome Dino via a headless Python environment. Two components: the game simulation and the RL training pipeline.

## High-Level Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ DinoEnv     │────▶│ PPO (SB3)        │────▶│ Trained Model│
│ (Gymnasium) │◀────│ 16 parallel envs │     │ (.zip)       │
└─────────────┘     └──────────────────┘     └──────────────┘
     │                     │
     │ obs (20-dim)        │ TensorBoard
     │ reward, done        │ logs
     │ action (0/1/2)      │
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `DinoEnv` | `src/env.py` | Gymnasium environment: Chrome Dino physics, collision detection, obstacle spawning |
| Training script | `scripts/train.py` | PPO setup, parallel envs (SubprocVecEnv), checkpointing, eval callbacks |
| Evaluation script | `scripts/evaluate.py` | Load model, run episodes, report statistics |
| Browser validation | `scripts/validate_browser.py` | Validate model against real Chrome Dino via Selenium + JS Runner API |

## Data Flow

1. **Observation**: 20-dim float vector → speed, T-Rex state (y, vy, jumping, ducking), 3 nearest obstacles (dx, y, w, h, type)
2. **Action**: Discrete(3) → 0=noop, 1=jump, 2=duck
3. **Reward**: speed/MAX_SPEED per frame (survival), -10 on death
4. **Episode**: Resets on collision. Speed ramps from 6→13 over time.

## Technology Choices

- **Language**: Python 3.12
- **RL Framework**: Stable-Baselines3 (PPO, MlpPolicy)
- **Env Framework**: Gymnasium
- **Deep Learning**: PyTorch (CUDA 13.0)
- **Physics source**: Chromium `dino_game/` TypeScript

## Constraints

- MLP policy is CPU-bound (GPU underutilized for this workload)
- Environment runs headless — no display required for training
- Obstacle gap and physics constants must match Chromium source

## Related Docs

- [ADRs](decisions/)
- [Vision Lock](../vision/VISION-LOCK.md)
- [Open Questions](../reference/open-questions.md)
