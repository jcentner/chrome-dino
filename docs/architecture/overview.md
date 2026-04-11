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
| `DinoEnv` | `src/env.py` | Gymnasium environment: Chrome Dino physics, collision detection, obstacle spawning. v2 adds `action_delay`, `frame_skip`, `clear_time_ms`, speed-dependent jump. v3 adds endJump velocity cap matching Chromium `trex.ts:483-520`. |
| Training script | `scripts/train.py` | PPO setup, parallel envs (SubprocVecEnv), checkpointing, eval callbacks |
| Evaluation script | `scripts/evaluate.py` | Load model, run episodes, report statistics |
| Browser validation | `scripts/validate_browser.py` | Real-time validation against Chrome Dino via Selenium + JS Runner API |
| Frame-stepped validation | `scripts/validate_browser_framestepped.py` | Deterministic frame-by-frame validation via JS hooks (overrides `performance.now()` + `requestAnimationFrame`). See ADR-002. |

## Data Flow

1. **Observation**: 20-dim float vector → speed, T-Rex state (y, vy, jumping, ducking), 3 nearest obstacles (dx, y, w, h, type)
2. **Action**: Discrete(3) → 0=noop, 1=jump, 2=duck. With `action_delay=N`, actions take effect N frames later. With `frame_skip=K`, each step runs K internal frames.
3. **Reward**: speed/MAX_SPEED per internal frame (accumulated across frame skip), -10 on death
4. **Episode**: Resets on collision. Speed ramps from 6→13 over time. Jump height increases with speed (Chromium formula).

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
