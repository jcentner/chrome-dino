# Phase 1 Design Critique — Round 2

**Reviewing**: [`roadmap/phases/phase-1-design.md`](phase-1-design.md) (revised post-R1)
**Round-1 critique**: [`roadmap/phases/phase-1-critique-design-R1.md`](phase-1-critique-design-R1.md)
**Stage**: design-critique, round 2 of max 3
**Anchors**: [vision lock v1.0.0](../../docs/vision/VISION-LOCK.md), [post-mortem](../../project-history.md#post-mortem-how-the-2026-run-went-off-the-rails), [`CURRENT-STATE.md` Proposed Vision Updates](../CURRENT-STATE.md#proposed-vision-updates)

## Summary

| # | R1 item | R2 status |
|---|---------|-----------|
| 1 | Approach C rejection is weak evidence | RESOLVED |
| 2 | Two-iteration path to MET from cold start (BLOCKER) | RESOLVED |
| 3 | Stop-gate threshold direction (BLOCKER, vision-level) | RESOLVED |
| 4 | Real-time throughput as implicit phase-blocker | RESOLVED |
| 5 | AC-HARNESS ±5% on integer-vs-integer | RESOLVED (minor wording wrinkle) |
| 6 | Singleton rule vs `src/heuristic.py` | RESOLVED |
| 7 | Slice 1 introduces env before slice 2 locks contract | RESOLVED |
| 8 | Selenium vs CDP | PASS (unchanged) |
| 9 | User stories add ceremony, not information | RESOLVED |
| 10 | Post-mortem lesson 4 — "beat the heuristic" gate | RESOLVED (minor "what counts as beat" gap) |
| — | **New issues introduced by the revision** | 1 CONCERN, 0 BLOCKERs |

**Overall verdict: approve.** Both R1 blockers are RESOLVED, all seven R1 concerns are RESOLVED, no new BLOCKERs were introduced. One minor CONCERN (AC-MET wording does not textually enumerate the honest-stop exit) plus two micro-wording gaps inside RESOLVED items (#5, #10) remain — none warrant another design-critique round; they are absorbable into implementation planning or a clarifying patch and pushing to R3 for them would itself be the over-iteration the post-mortem warned against.

---

## Per-item findings

### 1. Approach C rejection — RESOLVED

The candidate-set table's option-C cell now reads "MET = 2000 sits ~3.6× above the only frame-stepped heuristic measurement we have (v1's mean 559); we have no measurement of any heuristic's real-time mean," explicitly notes that the real-time vs frame-stepped direction "could go either way for a heuristic," and adds a §7 slice 1 revisit trigger ("if slice 1's measured real-time heuristic mean lands ≥ ~1500, this rejection is reopened via strategic re-plan before slice 2 begins"). This is the evidence-grounded framing R1 asked for. Option D's deferral wording is unchanged but was acceptable in R1 ("acceptable as a deferral, weak as a refutation") and remains so.

### 2. Two-iteration over-promise — RESOLVED

The phase title is now "Real-time browser-native agent to MET (or honest stop)". The new §0 paragraph states explicitly: "the stop-gate-fires-and-we-replan exit is the most plausible terminal state of this phase, not the slice-6-MET-met exit." The "Framing for slices 3–6 (read this first)" block at the top of §7 repeats this and walks the post-mortem evidence (2023 DQN ~555 mean, v1 PPO 64 real-time) that supports it. Slice 6 is now explicitly **conditional** on (a) AC-STOP-GATE not firing through slice 5 AND (b) slice-5 eval-mean ≥ ~1500. The R1 ask was either expand the iteration budget *or* own the strategic-replan-likely outcome; the planner chose the latter and recorded the rationale in the "Items where I deviated from the critic's recommendation" block (iteration budget is vision-level, not design-level — correct on authority order). Honest framing now matches the realistic prior.

### 3. Stop-gate threshold direction — RESOLVED

`CURRENT-STATE.md` now contains a `## Proposed Vision Updates` entry (2026-04-17) that proposes amending binding constraint 2 from "whichever is smaller" to "whichever is larger," cites the v1 walk-through (48 → 53 → 64; deltas 5 and 11) directly, includes a behaviour table across the score range, and is clearly marked "Awaiting human decision." The vision lock itself was correctly **not** edited (binding constraint 4). The design plan's AC-STOP-GATE and §7 slices 4/5 use the intended ("both must clear" / max-of) interpretation immediately, with footnote `[^stop-gate-threshold]` explaining the gap. This is the two-edit pattern R1 prescribed. Adequate handling pending human decision.

### 4. Throughput as implicit phase-blocker — RESOLVED

§7 slice 1 now has a concrete "Throughput exit" branch with a numeric soft cap (14 wall-clock days for slices 4 + 5 combined), explicitly routed to `Stage: blocked, Blocked Kind: awaiting-human-decision` *before slice 2 begins*, and explicitly **not** routed through AC-STOP-GATE. §4b's first-row mitigation was rewritten to match. The "constraint-2 used as throughput escape hatch" misuse R1 flagged is gone. The 14-day number is called out as a soft cap revisable at the block point — appropriate disposition for a number that doesn't belong in the vision lock.

### 5. AC-HARNESS ±5% — RESOLVED (minor wording wrinkle, non-blocking)

The ±5% tolerance is gone. AC-HARNESS now requires **exact match** between the harness's reported per-episode score and the page's displayed final score. The "≤ one score-tick" allowance is unidirectional (only the harness undershooting the displayed value is allowed) and bounded at ~1 point. The "any larger or systematic gap fails" clause explicitly catches the failure mode R1 named (a constant +1 across all episodes). Pressure-tested:

- Constant systematic +1 bias: the wording "any larger or systematic gap" rejects this. (Slight ambiguity — "systematic" could parse as modifying "gap" or as a separate failure condition — but operationally tight enough; the planner's intent in the Round 1 Response is unambiguous.)
- One legitimate sample-timing gap on one episode: allowed, ≤ 1 tick. Won't mask a real bug.

This does **not** reintroduce the original ±5% loophole. The 5% window was symmetric, unbounded per episode in absolute terms (5% of mean 2000 = 100 points), and could absorb a constant bias indefinitely. The new rule is asymmetric, capped at 1 point, and explicitly fails on systematic recurrence.

Minor wording wrinkle: it would be cleaner to write "the same gap appearing across all 5 episodes is a systematic gap and fails AC-HARNESS regardless of magnitude." Implementation planning can absorb the clarification.

### 6. Singleton rule vs `src/heuristic.py` — RESOLVED

AC-SINGLETON is extended to "exactly one learned-policy module, and exactly one fixed-policy (heuristic) module; both policy modules are invoked through the single eval script." This is option (a) from R1. Pressure-test on R2's specific question ("does it bound future drift, or has it just legitimized the next file under a new bucket?"): a hypothetical `src/heuristic_v2.py` or a return of `scripts/heuristic_agent.py` now violates AC-SINGLETON's explicit "exactly one fixed-policy module" clause and requires an ADR. The two named buckets (learned-policy, fixed-policy) are exhaustive for this phase's policy taxonomy; a future "ensemble-policy" or similar would still need ADR justification under the spirit of the rule (one of *each kind*, not "one per arbitrary new kind"). Drift bound, not relegitimized. The planner's reason for picking (a) over (b) (deleting `src/heuristic.py` after slice 1) is sound: the new beat-baseline sub-gate added per item 10 needs the heuristic re-runnable through the phase.

### 7. Slice 1 introduces env before slice 2 locks contract — RESOLVED

The "thin browser-interface adapter" reading was picked. §7 slice 1's "Files (hints)" line now says `src/browser.py` (DOM read, key send, game-over detection — explicitly *no* Gymnasium-style observation/action/reward contract) and explicitly states "`src/env.py` does **not** exist at end of slice 1." Slice 2 introduces `src/env.py` and the Gym contract. The fixture-capture utility now captures DOM-state snapshots rather than env observations, so slice 2's tests are unit-testable against fixtures whose schema is independent of the observation contract being designed in the same slice. Slice 1's AC-HARNESS-verified baseline number stays valid because it ran the heuristic against `src/browser.py` directly, not against an env contract that later changes. Cleanly separated; the contract question is not deferred but is properly placed in the slice that locks it.

### 8. Selenium vs CDP — PASS (unchanged)

No revision needed; the original PASS stands.

### 9. User stories — RESOLVED

§1 is now a single paragraph stating phase 1 has no end-user beyond the operator and that ACs in §2 govern, with the original story-form draft preserved inside a collapsed `<details>` block as an audit trail. Verified directly against the file: no duplicate `## User Stories` heading remains; no standalone `## Scope Notes` block remains; the surviving paragraph is clean and references R1 item 9 as the rationale. The audit-trail preservation in `<details>` is a cosmetic deviation from R1's "strip" recommendation but is not a substance change — the stories are no longer load-bearing on phase advancement, which was the point.

### 10. "Beat the heuristic" gate — RESOLVED (minor "what counts as beat" gap, non-blocking)

AC-STOP-GATE now has two sub-gates: **movement** (R1 item 3's intended threshold) and **beat-baseline** (slice's learned-policy real-time eval-mean ≤ slice-1 heuristic real-time eval-mean → gate fires). The beat-baseline sub-gate fires from slice 3 onward; §7 slice 3 has an explicit "beat-baseline gate fires here for the first time" subsection that exits the phase to strategic re-plan before slice 4 if the learned policy hasn't beaten the frozen baseline. Post-mortem lesson 4 is codified at the design level without re-promoting it to vision-binding. Folding into AC-STOP-GATE rather than creating an AC-BEAT-BASELINE keeps the wrap reporting against a single conceptual gate — defensible.

R2-specific question — "what is the threshold for 'beat'? exact equality? +1? statistical sig?" The wording is `learned ≤ heuristic ⇒ fire`. So `learned = heuristic` fires (good), but `learned = heuristic + 1` passes (questionable — a 1-point edge over a frozen rule-based policy is not "beating" it in any meaningful sense). At slice 3 only the beat-baseline gate is in effect (no prior learned eval-mean exists for the movement gate to compare against), so a learned policy at heuristic+1 would survive slice 3. From slice 4 onward, the movement gate provides a second filter (the learned policy has to *also* clear +10% rel/+50 abs over slice 3's eval-mean), so the practical loophole window is one slice wide. This is a real but small gap — implementation planning could tighten "beat" to e.g. "≥ heuristic + max(50, 10% of heuristic)" to mirror the movement-gate shape, or leave it and accept that slice 4 catches it. Not a blocker; flagging for implementation planning.

---

## New issues introduced by the revision

### N1. AC-MET wording does not enumerate the honest-stop exit — CONCERN

The §0 framing, slice 6's preconditions, and the phase title ("Real-time browser-native agent to MET (or honest stop)") all make the dual-outcome explicit at the narrative level. AC-MET in §2 still reads as a single-outcome requirement: *"A documented evaluation run produces mean score ≥ 2000…"* — there is no `OR phase ended at the gate per §7 with the wrap documenting the firing` clause. The story-form draft inside the `<details>` block does have this OR clause (Story 6 AC: "≥ 2000 (AC-MET) **or** the phase ends with `Stage: blocked, Blocked Kind: awaiting-human-decision`"), but the story block is no longer load-bearing.

In practice the gap closes: §7's slice 6 preconditions and §0's framing govern phase advancement, so a phase ending at the gate is not a violation of AC-MET — AC-MET is simply not asserted in that branch. But a future reader scanning §2 alone could read AC-MET as "the phase pass condition," which contradicts the §0 / §7 framing.

**Recommendation (non-blocking, can land in implementation planning):** add one sentence to AC-MET — "AC-MET applies only when slice 6 executes per §7 preconditions; if AC-STOP-GATE fires earlier and the phase ends at the gate, the wrap documents that exit and AC-MET is not asserted." This is a wording patch, not a structural change, and does not warrant another design-critique round.

### N2. Proposed Vision Updates entry — PASS

Walked through R2's specific questions:

- **Well-scoped?** Yes. Focused only on the threshold-direction wording in binding constraint 2, with no scope creep into other vision elements.
- **Accurately citing v1 evidence?** Yes. The 48 → 53 → 64 walk-through is mathematically correct under "whichever is smaller" (at prior=48, smaller of 4.8 and 50 is 4.8, delta 5 passes; at prior=53, smaller of 5.3 and 50 is 5.3, delta 11 passes). The behaviour table for the proposed amendment is also correct.
- **Clearly marked as awaiting human decision?** Yes — the section header explicitly says "Awaiting human decision" and the entry ends with "Decision required from: human reviewer of vision lock."
- **Does the design plan's footnote-based use of the intended interpretation hold up if the human rejects the amendment?** Conditionally yes. If rejected, the design plan reverts to the literal vision wording, at which point a substantive question reopens: the gate as literally written does not fire on the v1 failure case. The planner has correctly surfaced this rather than silently shipping the broken interpretation; whatever the human decides, the decision is informed. The footnote `[^stop-gate-threshold]` makes the dependency visible, so a future reader cannot miss that AC-STOP-GATE is operating under a *proposed* interpretation, not a ratified one. Adequate.

---

## Holistic check (post-mortem central failure)

The R1 verdict made the central post-mortem warning explicit: reviewers must keep asking *whether the plan, as a whole, plausibly hits MET — not whether each item is technically addressed.*

Re-asking that question of the revised plan:

- Does the revised plan plausibly hit MET? **Maybe — and the plan now openly says "maybe."** §0 names "stop-gate-fires-and-we-replan" as the most plausible terminal state. Slice 6 is conditional. The phase title, the §7 framing block, and AC-STOP-GATE's two sub-gates are all aligned around making either outcome (MET or honest stop) a clean handoff.
- Does the plan defend against the v1 failure pattern? **Yes — under the proposed vision amendment.** The movement gate plus the beat-baseline gate plus the no-headless-sim non-goal plus AC-SINGLETON's policy-module bound together cover the four named v1 failure axes (sim-transfer chase, scaffolding bloat, vision drift, metric drift away from deliverable).
- Does the plan over-promise anywhere else? **No.** The framing now explicitly demotes slice 6 from "expected outcome" to "executes only if preconditions met." The 14-day throughput exit prevents the "iterate until something works" trap on the wall-clock side.

The plan is approvable.

---

## Verdict

**Verdict: approve.**
