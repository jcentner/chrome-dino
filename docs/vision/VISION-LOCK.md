# chrome-dino — Vision Lock

> **Version**: 2.0
> **Updated**: 2026-04-11
> **Status**: Active
> **Rules**: Single versioned document, updated in place. Minor versions (2.1) for within-scope updates; major versions (3.0) for scope changes requiring human approval. Completed visions are archived to `docs/vision/archive/` before replacement.

## Problem Statement

Chrome Dino is a well-understood game with simple mechanics but emergent complexity from speed scaling. This project explores multiple approaches to playing it autonomously — heuristic, headless RL, and browser-native RL — each built by an autonomous AI agent. The narrative is about how autonomous development changes the cost of experimentation: when an agent can implement, test, and iterate approaches in minutes, the developer's role shifts to strategic thinking (which approach? what tradeoffs?) rather than implementation details. The cost of failure is low and experimentation is rewarded.

## Target User

The author (Jacob Centner) — this is a personal project and blog post subject. Secondary audience: readers of the resulting blog post who want to understand AI game-playing through a concrete, relatable example spanning multiple approaches.

## Core Concept

Multiple approaches to Chrome Dino, all under unified 2026 iteration, built autonomously:

1. **Headless PPO** (complete) — Headless physics clone + Stable-Baselines3 PPO. Fast training, sim-to-real gap solved via JS frame-stepping.
2. **Heuristic agent** — Hand-tuned reactive rules. No ML, just speed-adaptive jump/duck timing. Baseline for what pure engineering can achieve.
3. **Browser-native PPO** — Train PPO directly in Chrome via frame-stepping JS hooks. Zero sim-to-real gap by definition — the training env IS the real game.

## Success Criteria

| Criterion | Measure | Status |
|-----------|---------|--------|
| Headless PPO browser competence | Mean browser score > 555 (beats 2023 DQN) | **MET**: frame-stepped mean=1757 |
| Heuristic agent | Functional heuristic with browser score measured | Not started |
| Browser-native PPO | Train and evaluate in real Chrome | Not started |
| Approach comparison | All approaches compared on same metric (browser score) | Not started |
| Narrative completeness | project-history.md covers all approaches with strategic insights | In progress |

## Where We're Going

1. ~~Headless PPO: train, debug sim-to-real, validate via frame-stepping~~ **Done: mean=1757**
2. Heuristic agent: implement and measure in browser
3. Browser-native PPO: frame-stepped Chrome as Gymnasium env, train and evaluate
4. Compare all approaches on browser score, document strategic insights
5. Complete narrative with the "multiple approaches via autonomous dev" story

## Explicit Non-Goals

- Pixel-perfect visual clone of Chrome Dino
- Beating world-record scores  
- Multi-agent or competitive play
- Mobile/touch controls

## Out of Scope

- Night mode / day-night cycle effects on gameplay
- Sound effects
- Score display / HUD rendering

## Product Constraints

- Must run entirely on local hardware (no cloud training)
- Must produce a narrative suitable for blog post adaptation
- All 2026 approaches grouped under a single iteration reflecting autonomous dev capabilities

## Technical Constraints

- **Language**: Python 3.12
- **RL Framework**: Stable-Baselines3 + Gymnasium
- **Hardware**: i7-12700K, 32GB RAM, RTX 3070 Ti (CUDA 13.0)
- **Browser control**: Selenium + ChromeDriver (WSL2 → Windows)
- **Training**: Must converge in reasonable time (~30 min max per approach)

## Architecture Invariants

- Environment physics constants must be traceable to Chromium source
- Training and evaluation must be reproducible (seeded environments)
- Archived implementations (2018, 2023) must not be modified
- All 2026 approaches share the same browser validation infrastructure

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Headless env timing mismatch | **Resolved** | High | JS frame-stepping (ADR-002) |
| Browser-native training too slow | Medium | Medium | Frame-stepping gives ~10-50 FPS; may need patience or parallel Chrome instances |
| Heuristic trivially outperforms RL | Medium | Low | This is an interesting finding, not a failure — document why |
| Frame-stepping hooks break on Chrome update | Low | Medium | Pin Chrome version; hooks target stable Runner API |

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-04-10 | Initial vision: PPO agent for Chrome Dino with headless environment |
| 1.1 | 2026-04-10 | All goals met: agent trained (mean=2247), browser validated (mean=190), project-history.md complete |
| 1.2 | 2026-04-10 | **Honest reassessment**: browser score 190 is terrible. Redefined success criteria around browser score. |
| 1.3 | 2026-04-11 | **Browser competence achieved**: JS frame-stepping mean=1757. All v1 goals done. |
| 2.0 | 2026-04-11 | **Scope expansion**: Multiple approaches (heuristic, browser-native PPO) under unified 2026 iteration. Narrative reframed around autonomous dev enabling rapid experimentation across approaches. v1.3 archived. |
