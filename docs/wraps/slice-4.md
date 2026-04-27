# Slice 4 — Reward magnitude reshape

- **Run dir**: `logs/train/dqn-20260426T204842Z`
- **Source commit**: `879e5178`
- **Implementation plan**: [phase-1-implementation.md §6 slice 4](../../roadmap/phases/phase-1-implementation.md)
- **Source half**: 2026-04-26 (reviewer R2 pass / 0 critical / 0 major; 50 tests pass)
- **Evidence half**: 2026-04-26 4h training run, 750k env-steps, exit by step-budget at 2h11m wall

## The one bounded change

| Constant         | Slice 3 value  | Slice 4 value | Ratio (step:terminal) |
|------------------|----------------|---------------|-----------------------|
| `REWARD_STEP`    | `+1.0`         | `+0.1`        | 1 : 100 → **1 : 10**  |
| `REWARD_TERMINAL`| `−100.0`       | `−1.0`        | (sign preserved)      |

Side-effect (telemetry, not learning): `ep_reward_mean` source switched from
`model.logger.name_to_value` (cleared per SB3 dump cycle, returned `None` for
nearly every periodic-eval row in slice 3) to `model.ep_info_buffer` (deque
populated by SB3's auto-`Monitor` wrapper).

Reviewer R1 had blocked an attempted multi-variable change
(`learning_starts: 1k→10k`, `exploration_fraction: 0.1→0.2`); both were
reverted. The `exploration_fraction` change is a no-op anyway under
chunked `model.learn(reset_num_timesteps=False)` because SB3 resets
`_total_timesteps` per chunk, pinning ε at `final_eps=0.05` from chunk 2
onward. Logged as **TD-011** (High); becomes the primary slice-5 candidate
on this evidence.

## Rationale (slice-3 evidence)

Slice-3 diagnosis (from `dqn-20260425T233838Z` post-mortem, recorded in
`/memories/repo/training-observations.md`): the Q-network learned state
**value** (37 → 96 across input ranges) but no action-conditional
**advantage** signal. With `+1/−100` the terminal cost dominated TD targets
by ~100× any single step's contribution, and the gradient driving
action-discrimination became noise relative to the state-value signal.
Hypothesis: shrink the magnitude gap (1 : 10) so step-level advantage is
large enough to differentiate actions while still penalising crashes.

## Eval trajectory

```text
step    eval_mean
 50000     48.95
100000     69.25
150000     48.60
200000     48.10
250000     48.95
300000     48.10
350000     87.00   ← peak
400000     58.85
450000     64.55
500000     48.10
550000     48.05
600000     48.20
650000     49.80
700000     48.65
750000     50.50   ← final
```

Slice-3 reference (`dqn-20260425T233838Z`):

```text
step    eval_mean   (range 48.05 – 53.25 across all 15 checkpoints)
 50000     53.25
...        48.10–51.70
750000     48.10
```

## Slice-3 → slice-4 deltas

| Metric                     | Slice 3 | Slice 4 | Δ abs   | Δ rel   |
|----------------------------|---------|---------|---------|---------|
| Final-checkpoint eval-mean | 48.10   | 50.50   | +2.40   | +5.0 %  |
| Mean of 15 eval-checkpoints| 48.97   | 54.32   | +5.35   | +10.9 % |
| Peak eval-mean             | 53.25   | 87.00   | +33.75  | +63.4 % |
| Peak occurs at             | 50k     | 350k    | —       | —       |

Slice-1 heuristic baseline (n=20): **mean = 48.3**, max = 52, min = 48.

## Per-episode distribution comment

**350k checkpoint (slice-4 peak, eval-mean 87)**: high variance, scores
58–108, the policy was credibly *playing* — multiple cacti cleared per
episode. The 14-dim feature set is demonstrably sufficient to reach this
level.

**750k checkpoint (slice-4 final, eval-mean 50.5)**: scores cluster tightly
at 48 with occasional 50 / 63 / 64 — first-cactus death pattern. The greedy
policy degraded from the 350k peak.

**500k checkpoint** (eval-mean 48.1): nearly every episode scored exactly
48 — full collapse to noise floor.

Meanwhile, training behavior-policy `ep_reward_mean` rose 74 → 92 (peak at
425k) and held 82–92 through the rest of the run. **Train↔eval gap widened
from ~0 at 350k (87 train vs 87 eval) to ~+37 at 750k (87 train vs 50
eval).** The 5 % ε-noise behavior policy stayed productive while the
ε=0 greedy policy collapsed — a peak-and-collapse pattern, not a plateau.

## Beat-baseline gate (per impl plan §3.6 / §6 slice 4 task 5)

| Threshold (per VISION-LOCK v1.1.0 BC-2)                   | Value  | Slice-4 result | Pass? |
|-----------------------------------------------------------|--------|----------------|-------|
| Final eval-mean > heuristic baseline (48.3)               | 48.3   | 50.5           | ✓     |
| Final eval-mean > heuristic baseline + 50 absolute (98.3) | 98.3   | 50.5           | ✗     |
| Final eval-mean > heuristic baseline × 1.10 relative      | 53.13  | 50.5           | ✗     |

**Both thresholds (BC-2) must be cleared. Slice 4 does not clear them.**
The 350k *peak* (87.0) was close to the +50 absolute gate (98.3) but the
final checkpoint regressed.

Movement gate is *not* evaluated alone after slice 4 (per impl plan §6
slice-4 task 5 footnote). Forewarning to slice 5: slice-3 → slice-4
deltas are positive but small at the final checkpoint; the mid-run peak
shows the reward reshape unblocked Q-learning, but **training stability
is now the binding constraint**.

## Slice-5 selection

Per the decision tree in the prior `Blocked Reason`:

- *high-variance plateau with speedup-boundary clusters at 100/200/300* → A (closing-time)
- *flat plateau with uniformly low scores* → B (TD-011 ε-schedule fix)
- *still climbing past 200k* → extend training

Observed pattern matches **none cleanly** but is closest to "flat-with-low-
scores at the final checkpoint". Closing-time (Candidate A) targets
plateau-at-speedup-boundary, which we never reached (peak max=108, well
below the 200/300 boundaries). The 350k peak is direct evidence the 14-dim
feature set is *not* the binding constraint. Conversely, the
peak-and-collapse pattern with widening train↔eval gap is the textbook
signature of the broken ε-schedule under chunked `learn`: behavior
policy stays okay (ε=0.05 noise), greedy collapses, replay buffer drift
without exploration to recover.

**Decision (resume 2026-04-26)**: select **Candidate B (TD-011 fix)** for
slice 5. Stage advanced to `planning` for the planner to re-draft
`phase-1-slice-5-plan-DRAFT.md` against the new diagnosis. The
closing-time feature is not abandoned — it is deferred to slice 6 (or
later) on the rationale that representation upgrades should ride on a
training loop that is known to be stable.

## Tech debt status

- **TD-011** (High, queued for slice 5): broken ε schedule under chunked
  `model.learn(reset_num_timesteps=False)`.
- **TD-009 / TD-010** (slice 3, deferred): unchanged.
- No new tech debt opened in slice 4.

## Wall-clock accounting

- Slice 3 run: 2h14m / 750k steps.
- Slice 4 run: 2h11m / 750k steps.
- Combined slice-3 + slice-4 wall-clock: ~4h25m. Impl plan §6 caps
  combined slices 3+4+5 at 14 days; well under budget.
