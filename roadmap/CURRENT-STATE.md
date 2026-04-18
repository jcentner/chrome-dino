# chrome-dino — Narrative State

> **Machine-readable workflow state lives in [state.md](state.md).** Hooks
> parse that file. This file holds narrative context that humans read and
> agents append to.
>
> **Per-session activity logs live in [sessions/](sessions/).**

## Active Session

- **Log**: sessions/dc9d28b9-0b42-4a53-b287-6a1425376b79.md

## Waivers

(Human-approved exceptions to the normal flow. None yet.)

## Proposed Vision Updates

*Awaiting human decision. The builder does not edit `docs/vision/VISION-LOCK.md`
directly per binding constraint 4.*

(None open. Most recent: 2026-04-17 binding-constraint-2 threshold direction
amendment — approved and applied as vision lock v1.1.0.)

## Proposed Workflow Improvements

(Builder writes improvement suggestions here. Humans review and apply manually
between phases — the builder does not self-modify hooks, agents, or prompts.)

## Context

The builder appends a short narrative summary here at significant transitions
(stage advances, phase completion, blocked reasons). Per-tool-call logging
goes to `sessions/<id>.md` automatically.

- 2026-04-17 bootstrap: greenfield-redux. Human-led deep interview pinned the
  scope: real-time agent in unmodified Chrome on Windows-native, MET = mean
  >= 2000 over 20 consecutive episodes (max 2645 is informational stretch).
  Vision lock v1.0.0 written at [docs/vision/VISION-LOCK.md](../docs/vision/VISION-LOCK.md)
  with four binding constraints derived from `project-history.md`
  § "Post-Mortem: How the 2026 Run Went Off the Rails" (real-time-only
  metric, two-iteration stop gate, single-implementation rule, vision is
  defended). Phase 1 design plan drafted at
  [phases/phase-1-design.md](phases/phase-1-design.md); approach committed:
  browser-native online RL on a hand-engineered feature-vector observation,
  single Chrome instance, no headless simulator at any point. Tech stack
  is Python on Windows-native, hardware-capped to one RTX 3070 Ti.
  Catalog activated: deep-interview (skill), anti-slop (skill), clarify
  (prompt), commit-trailers (pattern). v1-era `src/` and `scripts/` are
  out of scope for reuse; old code is reference only. Stage advanced to
  `design-critique` for the next session.
- 2026-04-17 design-critique: product-owner populated user stories
  (subsequently stripped to a one-paragraph statement on revise — phase 1
  has no end-user beyond the operator; user flagged the format as
  ceremony, critic concurred). Critic R1 returned `revise` with 2
  blockers: (a) §7 over-promised MET in two iterations from cold start
  with no supporting prior-run evidence; (b) vision-lock binding-constraint-2
  threshold "whichever is smaller" mathematically permits the v1
  48→53→64 sunk-cost spiral the constraint exists to prevent. Planner
  R1-response: reframed §0/§7 to make stop-gate-fires-and-replan the
  most plausible exit and slice 6 conditional on eval-mean ≥ ~1500;
  AC-HARNESS tightened to exact match (≤ one score-tick allowance);
  AC-SINGLETON extended to cover policy modules; slice 1/2 split into
  `src/browser.py` then `src/env.py`; beat-baseline gate folded into
  AC-STOP-GATE; throughput-budget exit (14-day) added to slice 1;
  threshold bug surfaced via `## Proposed Vision Updates` entry below
  with intended interpretation footnoted in plan pending human decision
  (vision-lock untouched per binding constraint 4). Critic R2 returned
  `approve` (1 minor concern around AC-MET wording, deferred). Stage
  advanced to `blocked / awaiting-design-approval` — single hard human
  gate. Critique artifacts:
  [phase-1-critique-design-R1.md](phases/phase-1-critique-design-R1.md),
  [phase-1-critique-design-R2.md](phases/phase-1-critique-design-R2.md).
- 2026-04-17 resume: human approved both the design plan and the proposed
  vision-lock amendment. Vision lock bumped to v1.1.0 (binding constraint
  2 threshold reworded to "both thresholds must be cleared"). Design plan
  footnote and pending-amendment language stripped now that the wording
  is reconciled. Stage advanced to `implementation-planning`.
- 2026-04-17 implementation-planning → critique → approved: planner wrote
  [phase-1-implementation.md](phases/phase-1-implementation.md) locking
  the design-deferred decisions (SB3 DQN double+dueling MLP[64,64], CDP
  `Input.dispatchKeyEvent`, 14-dim scalar-`type_id` observation, free-run
  step pacing, baseline reward `+1/step −100 terminal`, 14-day combined
  wall-clock cap for slices 4+5, separate 3-day cap for slice 3 with
  500k-step / 3-eval-cycle floors before beat-baseline gate). Three
  critic rounds: R1 revise (1 blocker observation-dim inconsistency, 2
  major concerns action-mapping bug + missing step-pacing), R2 revise
  (no blockers, 2 new concerns reset-with-DUCK-held edge case + slice-3
  unbudgeted), R3 approved (residual risk ADR-able during execution).
  Two new ADRs queued: ADR-007 algorithm (slice 3), ADR-008 action
  dispatch (slice 1). Critique artifacts:
  [phase-1-critique-implementation-R{1,2,3}.md](phases/).
  Stage advanced to `executing` with Active Slice = 1 (real-time
  validation harness + frozen heuristic baseline).
- 2026-04-17 implementation-planning: planner drafted
  [phases/phase-1-implementation.md](phases/phase-1-implementation.md).
  Locked decisions: algorithm = SB3 DQN (double + dueling, MLP [64,64]) on
  off-policy/throughput grounds; action dispatch = CDP `Input.dispatchKeyEvent`
  with 16ms swap criterion; reward = baseline `+1/step, -100 terminal`,
  no shaping; 14-dim observation feature vector from `Runner.instance_`
  (dino y/jumping/ducking, current_speed, two nearest obstacles × 5
  fields, explicit no-obstacle sentinel fixing v1 bug #2) becomes ADR-003;
  action space = `Discrete(3)` {NOOP, JUMP, DUCK} becomes ADR-004;
  ADR-007 (algorithm) and ADR-008 (action dispatch) added on top of
  design-plan ADR-001/002/005/006. Module layout: `src/browser.py`
  (slice 1, no Gym contract), `src/env.py` (slice 2), `src/heuristic.py`,
  `src/policy.py`, single `scripts/eval.py`, single `scripts/train.py`,
  `scripts/capture_fixtures.py`. Six slices unchanged from design plan.
  Open questions flagged for critic: subprocess-vs-in-process eval
  re-entrancy under constraint 3, CDP-key-dispatch interpretation under
  vision lock, observation-refinement-vs-reward-shaping distinction at
  slice 4/5, score-readout formula choice, whether DQN should be locked
  at design level not implementation level, whether a slice-3 floor exit
  should pre-empt the slices 4-5 throughput burn. Stage advanced to
  `implementation-critique`.
