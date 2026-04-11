# chrome-dino — Architecture Overview

## Overview

Multiple approaches to playing Chrome Dino, all built autonomously: headless PPO, heuristic agent, and browser-native PPO. The architecture enables rapid experimentation with different strategies.

## High-Level Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ DinoEnv     │────▶│ PPO (SB3)        │────▶│ Trained Model│
│ (headless)  │◀────│ 16 parallel envs │     │ (.zip)       │
└─────────────┘     └──────────────────┘     └──────┬───────┘
                                                     │ validate
┌─────────────┐     ┌──────────────────┐     ┌──────▼───────┐
│ChromeDinoEnv│────▶│ PPO (SB3)        │     │ Chrome       │
│(frame-step) │◀────│ single env       │     │ (Selenium)   │
└─────────────┘     └──────────────────┘     └──────────────┘
                                                     ▲
┌─────────────┐                                      │
│ Heuristic   │──────────────────────────────────────┘
│ (rules)     │  frame-stepped or real-time
└─────────────┘
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `DinoEnv` | `src/env.py` | Headless Gymnasium environment: Chrome Dino physics clone. v3 with action_delay, frame_skip, speed-dependent jump, endJump velocity cap. |
| `ChromeDinoEnv` | `src/chrome_env.py` | Gymnasium wrapper around Chrome's actual game via JS frame-stepping. ~400 steps/sec. |
| Training (headless) | `scripts/train.py` | PPO with SubprocVecEnv parallelism. ~3K FPS, converges in ~40 min. |
| Training (browser) | `scripts/train_browser.py` | PPO in Chrome via ChromeDinoEnv. ~36 FPS, single env. |
| Heuristic agent | `scripts/heuristic_agent.py` | Speed-adaptive rules, no ML. Frame-stepped + real-time modes. |
| Evaluation | `scripts/evaluate.py` | Load model, run episodes, report statistics. |
| Browser validation | `scripts/validate_browser.py` | Real-time validation against Chrome via Selenium. |
| Frame-stepped validation | `scripts/validate_browser_framestepped.py` | Deterministic validation via JS hooks (overrides `performance.now()` + `requestAnimationFrame`). |

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
