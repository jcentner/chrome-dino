# Phase 1 — Slice 5 Plan (DRAFT)

> **Status: DRAFT, pre-evidence.** This plan is being staged while the
> slice-4 canonical 4h training run executes (`dqn-202604261…` TBD). If
> the slice-4 final wrap evidence contradicts the assumptions below, this
> plan is replaced. Anchors:
> [phase-1-design.md](phase-1-design.md) (slice 5 story),
> [phase-1-implementation.md](phase-1-implementation.md) §6 slice 5,
> [ADR-003](../../docs/architecture/decisions/ADR-003-observation-space.md),
> [TD-011](../../docs/reference/tech-debt.md) (broken ε plumbing).

## Context (slice-4 evidence as of partial run, to be confirmed by canonical 4h run)

Slice-4 partial run `dqn-20260426T195443Z` (cancelled at ~225k steps,
~37 wall-min, NOT canonical):

- Eval trajectory at 50k/100k/150k/200k checkpoints: 54.5 / 48.1 / 62.8 / 56.3.
  Eval-200k max=122 (vs slice-3's flat 48–51 across all 15 checkpoints,
  max never exceeding 51).
- Training `ep_reward_mean` ≈ 80 reward / ≈ 820 env-steps per episode
  from 25k onward; flat through 225k. Slice-3 random-baseline was ~110
  env-steps/episode.
- Conclusion: **reward reshape unblocked the slice-3 Q-collapse** (training
  episodes 7× longer than random play, eval distribution lifted off the
  noise floor with credible max=122). **A new plateau formed at training
  ~80 reward / eval ~56 score** with high variance — same disease in
  miniature: variance + plateau means the policy learned *something* but
  cannot adapt past a fixed-threshold rule.

Diagnosis (best current hypothesis, to be confirmed by slice-4 final
trajectory and per-episode score distribution):

The policy's argmax over learned Q approximates a fixed-threshold rule:
"jump when `xPos_rel < K` for some K." This works at the speed range
seen most often during training (`speed_norm ≈ 0.46–0.55`), but the dino
game ramps speed every ~100 score points and the threshold becomes wrong
as speed increases — collisions cluster around the first speedup boundary.
**The policy lacks the ability to compute time-to-collision** because the
14-dim observation gives `xPos_rel` and `speed_norm` separately and asks
the MLP to learn the division `xPos_rel / speed_norm`. A 2-layer
MLP[64,64] *can* learn divisions over a bounded range, but only with
many gradient updates against varied speed regimes — and the chunked-ε
schedule (TD-011) means the policy is exploiting almost from the start
and rarely sees high-speed states cleanly enough to update on them.

Two candidate bounded changes are competing for slice 5. Pick **one**.

## Candidate A — closing-time feature (RECOMMENDED)

**One bounded change**: add one derived scalar per obstacle slot to the
observation: `closing_time = xPos_rel / max(speed_norm, ε)` with
`ε = 0.05` (just below the lowest realistic `speed_norm ≈ 0.46`, so the
clamp only triggers when `speed_norm` is genuinely zero — which only
happens during the first frame after reset, before the game starts
moving). Observation grows from 14-dim → 16-dim.

**Rationale (evidence-anchored):**

- Directly addresses the diagnosis. The network no longer has to learn
  the division — it gets the time-to-collision feature precomputed.
- Cheap: 2 dims, no new ADR, just an ADR-003 amendment (window stays
  at 2; obstacle slot layout grows from 5 fields to 6).
- Highest-leverage of the candidates flagged in the slice-4 critique
  (`closing_time`, one-hot `type_id`, `obstacle.speedOffset`,
  `jumpVelocity`). The other three help less or are not bottleneck-
  shaped under current evidence.

**Risks:**

- Restarts training from scratch (observation shape changed → cannot
  warm-start from slice-4 checkpoint). 4h budget burned for re-validation.
- If the diagnosis is wrong and the plateau is actually exploration-driven
  (TD-011), `closing_time` won't move the metric and we've sunk 4h.
  Mitigation: the slice-4 final per-episode score distribution will
  partly disambiguate (clustered crashes near 100/200/300 score = speedup
  hypothesis confirmed; uniform-over-low-scores = exploration hypothesis).

**Files modified (slice 5 source half):**

- [src/env.py](../../src/env.py): add `closing_time_norm` to
  `_obstacle_block` return tuple; bump `OBS_DIM` to 16; update
  `_observation_from_state` to flatten the new field; update
  `observation_space` to `Box(shape=(16,))`.
- [tests/test_env.py](../../tests/test_env.py): index map updated for
  16-dim layout; new test pinning closing-time computation against a
  fixture with known `xPos_rel` and `speed_norm`; sentinel test extended
  to pin closing-time = `+1.0 / ε ≈ 20.0` for the no-obstacle slot
  (or, alternatively, an explicit sentinel value — see open question
  below).
- [docs/architecture/decisions/ADR-003-observation-space.md](../../docs/architecture/decisions/ADR-003-observation-space.md):
  amendment recording the new field, the clamp value, and the rationale
  (see proposed amendment text below).

**No changes** to `scripts/train.py`, `scripts/eval.py`, hyperparameters,
algorithm, or reward magnitudes. Train/eval pipeline divergence (slice-4
finding 3b) is **not** addressed here — it's a measurement-tooling concern,
distinct experimental variable, queued for slice 6 or a later cleanup.

**Acceptance criteria:**

- All slice-1, slice-2, slice-3, slice-4 tests still pass.
- New unit test pins closing-time computation against a hand-computed
  fixture value within 1e-6.
- `OBS_DIM == 16` and `observation_space.shape == (16,)`.
- `_SENTINEL` (or its equivalent) extended to include the
  no-obstacle closing-time value.
- ADR-003 amendment block appended (NOT a new ADR — magnitude/feature-
  refinement amendments to an existing accepted ADR follow the same
  amendment-record pattern already used for the window=2 working
  assumption and the slice-2 normalization-mechanism table).
- 4h training run launched after source merge + reviewer pass; eval
  trajectory recorded; slice-3 → slice-4 → slice-5 eval-mean delta
  computed in the slice-5 wrap; AC-STOP-GATE end-to-end evaluation
  per impl plan §6 slice 5 task 3.

**Open questions for the planner critic:**

1. **No-obstacle sentinel for closing-time**: should it be the natural
   `+1.0 / ε ≈ 20.0` (i.e. propagated from the existing sentinel) or an
   explicit out-of-distribution value (e.g. `+10.0` or `-1.0`)? Argument
   for natural: the no-obstacle case naturally has "very long time to
   collide" semantics, propagation is honest. Argument for explicit:
   `20.0` is far enough from real values (~1.0–4.0) that it might cause
   activation saturation in the first MLP layer. Recommendation:
   propagate naturally; clamp `closing_time` to `[0, 5.0]` in
   `_obstacle_block` to bound the input range.
2. **Re-train from scratch vs warm-start**: SB3 `DQN.load` can accept a
   model whose observation space differs from the new env if we manually
   reinitialize the input projection layer. Worth the complexity? Recommend
   no — clean re-train is the only honest experiment.
3. **`ε` clamp value**: `0.05` is below the lowest expected real `speed_norm`
   but above the reset-frame zero. Sensitive to the speed normalization
   denominator (`MAX_SPEED=13.0`); if Chrome's `Runner.config.MAX_SPEED`
   ever drifts, this value drifts too. Acceptable per ADR-003 pinning
   rationale.

## Candidate B — fix TD-011 (ε schedule under chunked `model.learn`)

**One bounded change**: replace the chunked `model.learn` loop in
`scripts/train.py` with a single `model.learn(total_timesteps=total_steps,
callback=combined_callback)` call where the callback handles checkpoint,
periodic eval subprocess invocation, and CSV cadence. This makes
`exploration_fraction` actually decay over `exploration_fraction × total_steps`
as the documentation promises, instead of being reset per chunk.

**Rationale**: TD-011 is a known correctness bug. If the slice-4 plateau
is exploration-driven (policy stuck in local optimum because ε pinned
at 0.05 from chunk 2 onward), this is the higher-leverage fix.

**Why NOT recommended as slice 5:**

- The slice-4 evidence pattern (high-variance plateau with credible max,
  not near-zero variance with floor min) is more consistent with the
  observation-gap hypothesis than the exploration-collapse hypothesis.
  Exploration collapse usually shows uniform low scores; observation gap
  usually shows variable scores with a clear ceiling.
- It's a refactor, not a feature. Refactors should be separate from
  experimental variables — if both ε scheduling AND `closing_time` were
  changed at once and the metric moved, attribution is impossible.

**Suggested ordering**: A first (slice 5) → if metric moves significantly,
B becomes slice 6 (with cleaner-sloped ε providing stable gradient
conditions for further iteration). If A doesn't move the metric, B becomes
slice 6 anyway (likely the next-most-load-bearing fix).

## Proposed ADR-003 amendment (pre-staged, applies if Candidate A is approved)

To be appended to [ADR-003](../../docs/architecture/decisions/ADR-003-observation-space.md)
under a new section after "Obstacle ordering":

> ### Slice-5 amendment (closing-time feature)
>
> **Date**: 2026-04-DD (TBD on slice-5 source merge)
> **Trigger**: slice-4 evidence — reward reshape lifted training episodes
> 7× past random baseline but eval-mean plateaued at ~56 with max=122,
> consistent with policy learning a fixed-threshold rule it cannot adapt
> as speed ramps. Diagnosis: 14-dim observation forces the MLP to learn
> `closing_time ≈ xPos_rel / speed_norm` as a division, which is solvable
> in principle but slow and noise-sensitive.
>
> **Change**: each obstacle slot grows from 5 fields to 6, adding
> `closing_time_norm = clamp(xPos_rel / max(speed_norm, 0.05), 0.0, 5.0)`
> as the new sixth field. `OBS_DIM` becomes 16. The no-obstacle sentinel
> becomes `(xPos_rel=+1.0, yPos_norm=0, width_norm=0, height_norm=0,
> type_id=-1, closing_time_norm=5.0)` — propagated naturally from the
> existing sentinel, then clamped to the [0, 5] range to bound MLP input.
>
> **Layout** (revised, slice-5 lift applied):
>
> | Index | Field |
> |---|---|
> | 0 | `dino_y_norm` |
> | 1 | `dino_jumping` |
> | 2 | `dino_ducking` |
> | 3 | `current_speed_norm` |
> | 4 | obstacle[0] `xPos_rel` |
> | 5 | obstacle[0] `yPos_norm` |
> | 6 | obstacle[0] `width_norm` |
> | 7 | obstacle[0] `height_norm` |
> | 8 | obstacle[0] `type_id` |
> | 9 | obstacle[0] `closing_time_norm` |
> | 10–15 | obstacle[1] same 6 fields |
>
> **Re-training cost**: observation shape change requires re-train from
> scratch; slice-4 checkpoints cannot be warm-started.
>
> **Lift trigger for further refinement**: if slice-5 evidence shows the
> policy still cannot adapt across speed regimes despite the new feature,
> the next candidate is one-hot `type_id` (replaces scalar; +4 dims) or
> surfacing `obstacle.speedOffset` from `Runner` for a true closing-velocity
> signal (currently `closing_time` uses the dino's running speed as a
> proxy, which underestimates pterodactyl closing speed — `speedOffset`
> can be ≥0 for pterodactyls).

## Sequencing

1. Slice-4 canonical 4h run completes. Operator reports final eval
   trajectory + per-episode score distribution.
2. Slice-4 wrap is written: records old-vs-new reward values, slice-3
   → slice-4 eval-mean delta (absolute and relative), per-episode
   distribution shape comment, beat-baseline gate check.
3. **Decision point**: re-read this draft. If slice-4 final trajectory
   still shows the high-variance plateau with score-cluster around
   speedup boundaries, proceed with Candidate A. If the plateau is flat
   with uniformly-low scores, switch to Candidate B (exploration is the
   bottleneck, not observation). If the metric kept climbing past 200k
   and didn't plateau, no slice-5 change needed yet — extend slice-4
   training instead.
4. If A: apply the ADR-003 amendment text above; implement in `src/env.py`;
   update `_SENTINEL` and tests; reviewer pass; relaunch 4h training.
5. Slice-5 wrap evaluates AC-STOP-GATE end-to-end per impl plan §6
   slice 5 task 3.
