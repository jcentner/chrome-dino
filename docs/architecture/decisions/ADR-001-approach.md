# ADR-001 — Browser-native online RL as the phase-1 approach

**Date**: 2026-04-17
**Status**: Accepted
**Phase**: 1 (introduced in slice 1)
**Anchors**: [vision lock](../../vision/VISION-LOCK.md), [phase-1 design plan](../../../roadmap/phases/phase-1-design.md), [project history § post-mortem](../../../project-history.md)

## Context

Phase 1 must hit MET (mean ≥ 2000 across 20 consecutive real-time episodes in
unmodified Chrome on Windows-native). Four approaches were considered:

| Option | Why plausible | Why not chosen |
|---|---|---|
| **A. Browser-native online RL** | Trains on the deployment distribution. Sim → real transfer collapse — the dominant v1 failure — is structurally impossible. The only previously-shipped real-time agent (2023 DQN, mean ~555) used this shape. | Sample throughput is bounded by real time. Chosen anyway. |
| B. Headless-sim RL | Fast sample collection. | Exactly what v1 did. v1's transfer ratios moved 8% → 9% → 11% across three iterations of physics fixes. The simulator was the wrong abstraction layer entirely. |
| C. Heuristic-only | 2018 reportedly hit max 2645. Lowest implementation risk. | MET = 2000 sits ~3.6× above the only frame-stepped heuristic measurement (mean 559). No measurement of any heuristic's *real-time* mean exists. Retained as the slice-1 sanity baseline. |
| D. BC + RL fine-tune | Could warm-start RL past the early-game floor. | Adds a second data pipeline + a second optimizer phase, against AC-SINGLETON. Available as a strategic-replan target if approach A stalls under AC-STOP-GATE. |

## Decision

**Phase 1 commits to approach A — browser-native online RL on a hand-engineered
feature-vector observation, single Chrome instance, no headless simulator at any
point in the pipeline.**

Approach A is the only candidate whose dominant failure mode is "too slow to
train" (recoverable via strategic re-plan) rather than "trains the wrong thing"
(which is what v1's headless-sim RL did, three times in a row).

## Consequences

- The phase is bounded by real-time sample throughput. Slice 1 measures it; if
  two RL iterations exceed 14 days of wall-clock, the phase exits to
  `awaiting-human-decision`.
- The heuristic from option C is implemented in slice 1 as a frozen sanity
  baseline to verify the validation harness, not as the deliverable.
- Approaches B and D are explicitly out of scope for this phase.
