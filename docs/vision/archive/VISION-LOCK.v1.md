# chrome-dino — Vision Lock

> **Version**: 1.3
> **Updated**: 2026-04-11
> **Status**: Active
> **Rules**: Single versioned document, updated in place. Minor versions (1.1) for within-scope updates; major versions (2.0) for scope changes requiring human approval. Completed visions are archived to `docs/vision/archive/` before replacement.

## Problem Statement

Chrome Dino is a well-understood game with simple mechanics but emergent complexity from speed scaling. Building an RL agent to play it well demonstrates core RL competence and provides a compelling narrative: the same problem solved three different ways over eight years (2018 supervised → 2023 DQN → 2026 PPO), each reflecting the state of AI tooling at the time.

## Target User

The author (Jacob Centner) — this is a personal project and blog post subject. Secondary audience: readers of the resulting blog post who want to understand RL concepts through a concrete, relatable example.

## Core Concept

A headless Python recreation of Chrome Dino's physics (sourced from Chromium TypeScript) paired with PPO training via Stable-Baselines3. No browser automation, no screen capture, no OCR — just pure game logic running at thousands of steps per second. The agent learns from a compact feature vector, not pixels.

## Success Criteria

| Criterion | Measure | Status |
|-----------|---------|--------|
| **Browser competence** | Mean browser score > 555 (beats 2023 DQN) | **MET**: frame-stepped mean=1757 |
| Browser stretch | Mean browser score > 1000 | **MET**: frame-stepped mean=1757 |
| Training efficiency | Converges within 4M timesteps on RTX 3070 Ti | Met (best model at ~875K of 2M steps) |
| Environment fidelity | Headless score predicts browser score within 2x | **MET**: 2365 headless vs 1757 frame-stepped (1.3x) |
| Narrative completeness | project-history.md ready for blog adaptation | **MET**: Full arc through frame-stepping breakthrough |

## Where We're Going

1. ~~Train a PPO agent in a headless clone~~ **Done (v1 — but transfers poorly)**
2. ~~Fix sim-to-real gap: action delay, speed-dependent jump, observation mapping~~ **Done (v2/v3)**
3. ~~Retrain with corrected environment (v2)~~ **Done (v3 with endJump cap)**
4. ~~Achieve browser mean score > 555 (beat 2023 DQN)~~ **Done: frame-stepped mean=1757**
5. ~~Complete project-history.md with the full iteration story~~ **Done: full arc through frame-stepping**

## Explicit Non-Goals

- Pixel-perfect visual clone of Chrome Dino
- Real-time browser automation for training
- Beating world-record scores
- Multi-agent or competitive play

## Out of Scope

- Mobile/touch controls
- Night mode / day-night cycle effects on gameplay
- Sound effects
- Score display / HUD rendering

## Product Constraints

- Must run entirely on local hardware (no cloud training)
- Must produce a narrative suitable for blog post adaptation

## Technical Constraints

- **Language**: Python 3.12
- **RL Framework**: Stable-Baselines3 + Gymnasium
- **Hardware**: i7-12700K, 32GB RAM, RTX 3070 Ti (CUDA 13.0)
- **Training**: Must converge in reasonable time (~30 min max)

## Architecture Invariants

- Environment physics constants must be traceable to Chromium source
- Training and evaluation must be reproducible (seeded environments)
- Archived implementations (2018, 2023) must not be modified

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Headless env diverges from real game | **Resolved** | High | Root cause was timing (Chrome ~51fps vs 60fps), not physics. Frame-stepping eliminates the gap. See ADR-002. |
| PPO plateaus below target score | Low | Medium | Tune hyperparameters; try different reward shaping |
| CUDA compatibility issues | Low | Low | MLP policy works on CPU too |
| Action latency in deployment | **Resolved** | High | Frame-stepping eliminates timing mismatch; action_delay+frame_skip handle training-time latency modeling |

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-04-10 | Initial vision: PPO agent for Chrome Dino with headless environment |
| 1.1 | 2026-04-10 | All goals met: agent trained (mean=2247), browser validated (mean=190), project-history.md complete |
| 1.2 | 2026-04-10 | **Honest reassessment**: browser score 190 is terrible (worse than 2023 DQN at 555). Redefined success criteria around browser score. Added sim-to-real gap fixes as goals. |
| 1.3 | 2026-04-11 | **Browser competence achieved**: JS frame-stepping validated mean=1757 (3.2x target). Environment fidelity within 1.3x. Goals 2-4 marked done. Risks resolved. |
