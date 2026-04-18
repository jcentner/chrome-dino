# Phase 1 Implementation Critique — Round 2

**Reviewing**: [phase-1-implementation.md](phase-1-implementation.md) (revised after R1) + planner's `## Round 1 Response`
**R1 critique**: [phase-1-critique-implementation-R1.md](phase-1-critique-implementation-R1.md)
**Approved design**: [phase-1-design.md](phase-1-design.md)
**Anchors**: [vision lock v1.1.0](../../docs/vision/VISION-LOCK.md), [post-mortem](../../project-history.md#post-mortem-how-the-2026-run-went-off-the-rails)
**Stage**: implementation-critique, round 2 of max 3.

## Summary

| # | R1 Topic | R1 Verdict | R2 Disposition |
|---|----------|------------|----------------|
| 1 | DQN choice + MLP capacity | PASS | RESOLVED (n/a) |
| 1a | Cited 2023 baseline number (870 → 555) | CONCERN | **RESOLVED** |
| 2 | CDP locked before slice-1 measurement | PASS | RESOLVED (n/a) |
| 3a | 2-obstacle window justification | CONCERN | **PARTIAL** (see below) |
| 3b | Sentinel encoding | PASS | RESOLVED (n/a) |
| 3c | Observation dim count vs encoding | **BLOCKER** | **RESOLVED** |
| 4 | Reward magnitude audit-trail | PASS | RESOLVED |
| 5 | JUMP fails to release held DUCK | CONCERN | **RESOLVED** for JUMP; new gap on `reset()` (see NEW-A) |
| 6 | `src/browser.py` and AC-SINGLETON | PASS | RESOLVED (deferral acceptable) |
| 7 | 14-day budget routing | PASS | RESOLVED (n/a) |
| 8 | Subprocess vs in-process eval cadence | PASS-with-note | **RESOLVED** |
| 9 | Fixture-capture spec | PASS | RESOLVED |
| 10 | Step-pacing decision missing | CONCERN | **RESOLVED** structurally; residual DQN-specific concern (see NEW-B) |
| 11 | Open-question deferrals | PASS | RESOLVED |
| 12 | Post-mortem cross-check | PASS | RESOLVED (n/a) |
| **NEW** | New issues introduced or surfaced by R2 pressure-test | — | NEW-A CONCERN, NEW-B PASS-with-note, NEW-C **CONCERN**, NEW-D PASS-with-note |

**Overall verdict: revise.** All R1 blockers landed correctly. Two genuine new spec gaps surfaced under pressure-test: NEW-A (action-mapping invariant doesn't extend to `reset_episode()` while ArrowDown is held — same class of bug as R1#5, fixed for JUMP but not reset/terminal) and NEW-C (slice 3 has no `--total-steps` floor; "at least one periodic eval cycle" at default `--eval-every=50000` ≈ 28 min of training is grossly insufficient for DQN to clear the beat-baseline gate, which risks a false-negative gate fire that costs the phase its slice-3 → slice-4 → slice-5 trajectory). NEW-B and NEW-D are documentation-only acknowledgements. Both NEW-A and NEW-C are bounded one-paragraph spec patches; R3 should be lightweight verification.

---

## Per-item disposition (R1 findings 1–12)

### 1. DQN choice + MLP capacity — RESOLVED (n/a)

R1 was PASS; planner did nothing. Correct.

### 1a. Citation 870 → 555 — RESOLVED

§3.1 now reads "mean ~555 per [`project-history.md`](../../project-history.md) § Attempt 2 and design plan §0." Cross-checked: `project-history.md` line 85 / 103 / 133 / 278 / 286 / 296 / 370 are unanimous on 555; design plan §0 line 8 says "landed at mean ~555". (Note for the human: design plan §0 line 18 *also* says "~870" — the design plan itself is internally inconsistent on this number. The planner picked the source-of-truth value; that's the right call. The design plan's own 870/555 inconsistency is not in the implementation plan's lane to fix and should be flagged separately to the design author if it matters.) Argument is unchanged and works at 555. RESOLVED.

### 2. CDP locked before slice-1 measurement — RESOLVED (n/a)

R1 was PASS. No change needed. Correct.

### 3a. 2-obstacle window justification — PARTIAL

§3.4 now contains the "Obstacle window width = 2 (justification)" paragraph citing the spawning formula. Two issues remain:

1. **The cited formula is not independently verified.** The string `gap = obstacle.width * speed + minGap * gapCoefficient` is lifted from [`project-history.md`](../../project-history.md) line 65 (post-mortem bug #1), where it's described as "Chromium's" formula — but the post-mortem itself is a secondary source. There is no `2018-implementation/**/*.js` file in this repo and no link to a primary Chromium source. The planner's "the Chromium dino game's `Obstacle` spawning logic enforces ..." is **a confident-sounding citation of a formula they didn't independently verify**. The user's pressure-test question 2.4 was right to flag this.
2. **The arithmetic isn't done.** The argument is "at MET-relevant speeds the third obstacle is reliably off-screen-right." But: the formula's units are not stated (px? game-units? canvas-fractions?), and no plug-in-MAX_SPEED-and-compute is shown. The conclusion is plausible but not demonstrated. "Plausible but undemonstrated" is exactly the v1 anti-pattern the post-mortem warns about.

**Why this is PARTIAL and not BLOCKER**: the cost of being wrong is bounded — ADR-003 amendment widens to 3 obstacles (5 mostly-sentinel dims, trivial MLP-capacity cost) if slice 3/4 evidence shows policy fails on dense clusters. The *operational* path is sound; only the *justification text* is over-confident. This is acceptable for an implementation plan; it would not be acceptable for an ADR.

- **Recommendation (optional, for executing-stage ADR-003 author)**: when ADR-003 is written in slice 2, either (a) cite a primary Chromium source for the gap formula (a URL into `chromium.googlesource.com/.../offline.js` would do), (b) actually compute the gap at `MAX_SPEED` and show the third obstacle is `> canvas_width` away, or (c) drop the formula citation and just record "we picked 2 because 3 adds 5 mostly-sentinel dims and we can amend if evidence demands it." Any of the three is honest; the current text is the only one that isn't.

### 3b. Sentinel encoding — RESOLVED (n/a)

R1 PASS. The scalar resolution in 3c makes `type_id = -1` work cleanly as the planner described.

### 3c. Observation dim BLOCKER — RESOLVED

§3.4 now explicitly says **scalar `type_id` ∈ {-1, 0, 1, 2}**, "scalar; not one-hot," with a 4-bucket-doesn't-need-one-hot justification paragraph. 14-dim total now matches: 4 dino fields + 5 fields × 2 obstacles = 14. ✓. Sentinel description is consistent. Tester-isolation chain (slice 2 tester reads §3.4 + ADR-003) is now unambiguous. RESOLVED.

(Brief check on the user's pressure-test question 2.3 — "does scalar bake in a false ordering the network has to unlearn?": with `[64, 64]` ReLU MLP and ~millions of real-time samples, the cost of unlearning the implicit ordering is negligible. Hidden units in layer 1 can implement indicator-style decompositions of a 4-valued scalar. The planner's justification is correct. The trade is 14 dims vs ~18-20 dims, and the smaller representation buys a marginal capacity advantage at zero practical cost. PASS.)

### 4. Reward magnitudes — RESOLVED

§3.3 now ends with: "Any magnitude change is recorded in the slice wrap that introduces it (slice-N wrap states the old value, the new value, the reason, and the slice-N-evidence that motivated the change), so the audit trail is complete even without an ADR." Closes the audit-trail nit. Also added the early-vs-late training credit-assignment framing from the R1 critique. RESOLVED.

### 5. JUMP fails to release held DUCK — RESOLVED for JUMP, but see NEW-A

§3.5 now opens with the **Invariant** "any non-`DUCK` action releases a held `ArrowDown` *before* dispatching its own keys." The JUMP row is rewritten correctly. The NOOP row is rewritten correctly. Slice-1 task 7 test list now requires a `DUCK → JUMP → DUCK` state-machine test asserting the intermediate JUMP releases ArrowDown and the second DUCK re-presses it. The original R1 finding is RESOLVED.

**However**, the user's pressure-test question 2.2 surfaced a related edge case the planner did not address — see **NEW-A** below.

### 6. `src/browser.py` and AC-SINGLETON — RESOLVED (deferral acceptable)

Planner deferred the optional ADR-006-wording suggestion to ADR-006 authorship in slice 1. Acceptable — that ADR doesn't exist yet, and adding the wording in implementation-plan prose would duplicate text the ADR will own. RESOLVED.

### 7. 14-day budget routing — RESOLVED (n/a)

R1 PASS, no change needed. Correct.

### 8. Subprocess vs in-process eval cadence — RESOLVED

§6 slice 3 task 4 now sets `--eval-every = 50000` env-steps as default, computes the wall-clock arithmetic ("~5–10% of slice-3 wall-clock at this cadence"), and requires the slice-3 wrap to record both the cadence used and its share of slice-3 wall-clock. Slices 4/5 inherit. Closes the "unrecorded knob" failure mode. RESOLVED.

### 9. Fixture-capture spec — RESOLVED

PASS in R1, gated only on #3c being resolved (now is). Tester-isolation chain is now unambiguous. RESOLVED.

### 10. Step-pacing decision missing — RESOLVED structurally; see NEW-B

New §3.7 "Env step pacing: free-run, paced by the page's own clock" added between §3.6 and §4. Locks free-run with vision-lock alignment, jitter robustness, cost transparency, and explicit acknowledgement of the cost (agent samples roughly every other 60fps frame at ~30 steps/sec). ADR-003 scope expanded in §5 to include pacing. Open-questions §9 item 8 records the resolution for traceability. The original R1 finding (decision wasn't recorded anywhere) is RESOLVED.

The user's pressure-test question 2.1 surfaces a residual DQN-specific concern — see **NEW-B** below.

### 11. Open-question deferrals — RESOLVED

Item 8 added for step-pacing traceability; otherwise unchanged from R1's PASS. RESOLVED.

### 12. Post-mortem cross-check — RESOLVED (n/a)

R1 PASS. No change needed. Correct.

---

## New issues surfaced in R2

### NEW-A. Action-mapping invariant doesn't cover `reset_episode()` or the terminal step — CONCERN

The Invariant "any non-`DUCK` action releases a held `ArrowDown` first" covers `JUMP` and `NOOP`. It does **not** cover:

1. **`reset_episode()` while DUCK is held.** Concrete sequence: `DUCK → DUCK → DUCK → terminal`. After terminal detection, the episode-reset path dispatches `Space` (per §6 slice 1 task 2: "`reset_episode()` (dispatch Space, wait for `Runner.instance_.playing` to flip true)"). But the adapter's internal `ArrowDown is held` flag is still true, and `ArrowDown` is still physically held in the page's keyboard state. The new episode begins with the dino in a ducking pose. First action of the new episode (typically NOOP from the agent's `reset → step` handoff) would release it — but until then, the dino starts the run ducking. This is the same class of state-machine corner case that R1#5 caught for JUMP. The planner fixed JUMP and stopped.

2. **Terminal step while DUCK is held.** §6 slice 2 task 4 says "Action ignored if game is already in the terminal state — env does not crash, surfaces a no-op terminal step." That's correct for the *agent-action ignore* case, but it doesn't address whether a held ArrowDown is *released* on terminal detection. If the game crashed *while* ArrowDown was held, the held flag in the adapter is still true going into reset. (Same root cause as #1.)

**Type**: Edge Case / specification defect
**Severity**: Major (latent functional bug; the new episode's first ~step or two of state will be observed-from-ducking, which silently distorts the early-state-distribution the policy learns to map; same anti-pattern the post-mortem's "every file had a local justification" warning is about).
**Affects**: §3.5 (Invariant scope), §6 slice 1 task 2 (`reset_episode()` spec), §6 slice 1 task 7 test list (no test for reset-with-held-DUCK).
**Recommendation**: extend the Invariant in §3.5 to "any non-`DUCK` action **and `reset_episode()`** releases a held `ArrowDown` first." Update §6 slice 1 task 2 to specify: "`reset_episode()`: if the adapter's `ArrowDown is held` flag is true, dispatch `keyUp ArrowDown` and clear the flag; then dispatch `Space`; then wait for `Runner.instance_.playing` to flip true." Add a slice-1 task-7 test: `DUCK → terminate-the-episode → reset → assert no ArrowDown held in the new episode`.

### NEW-B. Free-run pacing under DQN — variable Δt rewards/transitions — PASS-with-note

The user's pressure-test question 2.1 asked whether free-run is internally consistent with DQN's discrete-step transition framing. The planner's §3.7 justification covers the right *vision-lock* and *robustness* axes but skips the DQN-specific concern:

- DQN's stored transition tuple `(s, a, r, s')` does not include Δt as a feature. The reward `+1.0` per step represents a varying amount of *game-time survived* (small at fast ticks, large at slow ticks). The displacement `s → s'` similarly varies. The policy must learn a mapping `(observation → action)` that conditions only on absolute state (xPos_rel, current_speed_norm) and is invariant to Δt.
- This is achievable *because* the hand-engineered features (xPos_rel encodes absolute distance, current_speed_norm encodes absolute speed) make Δt observable through the state delta, not through the time field. A pixel-input DQN under free-run would have a much harder problem.
- Net: the design choice is sound for *this* feature set under *this* algorithm. But the §3.7 justification doesn't explicitly connect "free-run is OK because the obs vector encodes absolute state, not relative-frame state" — a future reader (or the ADR-003 author in slice 2) would have to re-derive this.

**Type**: Assumption (under-articulated, not wrong)
**Severity**: Minor
**Affects**: §3.7, ADR-003 authorship in slice 2.
**Recommendation (optional, for slice-2 ADR-003)**: add one sentence to §3.7 or to ADR-003 noting that free-run is consistent with DQN's transition framing *because* the observation vector encodes absolute state (xPos_rel, current_speed_norm) rather than per-frame deltas, so the policy can be Δt-invariant by construction. Not a revise-grade finding on its own.

### NEW-C. Slice 3 lacks a training-budget floor — CONCERN

§6 slice 3 task 5 says: "Run training to **at least one full periodic eval cycle**. Commit the latest periodic eval as `logs/slice3/learned_eval.json`." With the `--eval-every = 50000` default pinned in task 4 and a measured throughput around the slice-1-target ~30 steps/sec, "one full periodic eval cycle" = ~50000 / 30 ≈ **28 minutes of training**. (At pessimistic 5 steps/sec, ~3 hours; at optimistic 100 steps/sec, ~8 minutes. Order-of-magnitude: tens of minutes to a few hours.)

**This is grossly insufficient for SB3 DQN to clear a hand-coded heuristic baseline.** Reference points:

- 2023 DQN trained for ~2 days of clock time to reach mean ~555 (per `project-history.md` § Attempt 2 / design plan §0 line 241).
- SB3 DQN's Atari benchmarks need ~1M–10M env-steps to converge; small-MLP-on-small-feature-vector tasks can be faster but ~50k steps is solidly in "noise" territory for any non-trivial control task.

The slice-3 wrap is required to record the slice-3 → slice-1-heuristic comparison as the **beat-baseline gate** (§6 slice 3 exit branches). With a 28-minute training run, the gate will almost-certainly fire ("slice-3 eval-mean ≤ heuristic"), and the phase will exit to `awaiting-human-decision` — **not because the algorithmic approach failed, but because slice 3 didn't train long enough for any algorithm to converge.** That's a false-negative gate fire that wastes the gate's signal and burns a session-end / human approval cycle.

The §3.6 budget ("7 days per RL iteration (slices 4 and 5), 14 days combined") names slices 4 and 5 explicitly. **Slice 3's wall-clock budget is not stated anywhere in the plan.** Is slice 3 part of the 14-day combined? Is it a third 7-day slot? Is it open-ended? The plan doesn't say.

**Type**: Acceptance Gap / Testing Gap (the beat-baseline gate at slice 3 is the plan's first AC-STOP-GATE check, and its evidence is under-specified)
**Severity**: Major (a false-negative gate fire here truncates the phase before slices 4 and 5 ever run)
**Affects**: §3.6 (budget table), §6 slice 3 task 5 (training duration), §6 slice 3 exit branches (beat-baseline gate semantics).
**Recommendation**: pin a slice-3 training-budget floor. Two acceptable shapes:
1. **Wall-clock floor** — "Slice 3 trains for at least 24 hours of wall-clock OR 500k env-steps, whichever comes first; only then is the beat-baseline gate evaluated." Aligns with the §3.6 multi-day-iteration framing.
2. **Step-count floor** — "Slice 3 trains for at least 200k env-steps before the slice-3 eval is taken to be the slice's representative number." Less wall-clock-coupled.
Either way, the slice-3 wrap should also record per-checkpoint eval-means *during* training (the periodic-eval CSV from task 4) so that "training was still rising when slice ended" is distinguishable from "training plateaued below baseline." The latter trips the gate; the former extends the budget.

The current §3.6 is implicit: "7 days per iteration" suggests slice 3 *is* an iteration, but task 5 says "at least one periodic eval cycle," which is two orders of magnitude shorter. These are inconsistent. Pick one.

### NEW-D. 2-obstacle window: arithmetic still not shown — PASS-with-note (folded into 3a)

Already captured under 3a-PARTIAL. Listed here for the summary table only.

---

## Final overall sanity check (per user prompt §3)

Stepping back: does this implementation plan plausibly produce a DQN agent that beats the slice-1 heuristic by slice 3 and trends toward MET by slice 5?

**Honest answer: probably not, but the plan knows it.** The design plan §0 line 241 and §7 framing both say the most-plausible terminal state is AC-STOP-GATE firing, not slice 6 producing MET. The implementation plan inherits this framing in §0 / §1 / §6 slice 5/6 exit branches. So the plan is *not* claiming "two iterations from cold start clear MET"; it's claiming "two iterations from cold start either move the metric meaningfully OR trip a gate that produces a real-time-measured trajectory and a strategic re-plan." That's a defensible deliverable shape and is consistent with the post-mortem's lessons.

**The post-mortem's "this whole line of work won't work" critique was specifically about sim-trained agents.** This plan trains in real Chrome from step 1 — there is no sim-to-real transfer to fail. The 2023 DQN at mean ~555 *did* work (in the sense of "produced a real-time agent that survives non-trivially") with image input and ~1 effective FPS. This plan has a stronger observation (hand-engineered features) and ~30× the throughput target. So "DQN beats heuristic eventually" is plausible.

**But "by slice 3" specifically is the load-bearing claim**, and NEW-C is the reason that claim is currently weak. With a 28-minute training budget at slice 3, the beat-baseline gate at slice 3 is set up to be falsely-tripped. Fixing NEW-C (pinning a slice-3 step or wall-clock floor) is the difference between "the gate measures algorithmic capability" and "the gate measures whether the operator gave training enough time." The gate machinery is correct; the slice-3 budget that feeds it is not.

Trends-toward-MET-by-slice-5: with a credible slice-3 baseline (NEW-C fixed) and two bounded iterations (slices 4, 5), reaching mean ~1500 is plausible-but-not-likely. Reaching MET (mean ~2000) by slice 5 is *unlikely*, which the plan correctly acknowledges by making slice 6 conditional on slice-5 reaching ~1500. The framing is honest. The execution risk is concentrated in slice 3.

---

## Verdict

**Verdict: revise.**

R2 round count: 2 of 3 used. Reason: NEW-A and NEW-C are bounded one-paragraph spec patches, both substantive. NEW-A is the same class of state-machine bug as the original R1#5 finding (the planner fixed JUMP but stopped before checking reset/terminal). NEW-C is a real spec gap that materially affects the slice-3 beat-baseline gate's signal-vs-noise — without a training-budget floor, the gate will fire on operator under-training rather than algorithmic incapability, costing the phase a session-end and a human approval cycle. Both fixes are scoped and lightweight; R3 should be a verification round, not a re-rebuild round. The core implementation approach (browser-native online DQN, hand-engineered 14-dim features with scalar `type_id`, CDP key dispatch, free-run pacing, single Chrome instance, AC-STOP-GATE active from slice 3, conditional MET evaluation at slice 6) is sound and consistent with the approved design plan and the post-mortem's lessons.

The 3a-PARTIAL (over-confident formula citation) and NEW-B (DQN-Δt acknowledgement) are deferrable to ADR-003 authorship in slice 2 and do not require a plan revision on their own. NEW-D is folded into 3a.
