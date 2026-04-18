# Phase 1 Implementation Critique — Round 3 (final)

**Reviewing**: [phase-1-implementation.md](phase-1-implementation.md) (twice-revised) + planner's `## Round 1 Response` and `## Round 2 Response`.
**R2 critique**: [phase-1-critique-implementation-R2.md](phase-1-critique-implementation-R2.md) (verdict: revise).
**Approved design**: [phase-1-design.md](phase-1-design.md).
**Anchors**: [vision lock v1.1.0](../../docs/vision/VISION-LOCK.md), [post-mortem](../../project-history.md#post-mortem-how-the-2026-run-went-off-the-rails).
**Stage**: implementation-critique, round 3 of max 3 — terminal round. A non-`approved` verdict here escalates to a human via `Stage: blocked, Blocked Kind: awaiting-human-decision`.

This round is scoped to verifying R2's three substantive items closed. No new investigation threads opened. No nit-picking to manufacture another round.

## Per-item verification of R2 findings

### NEW-A — Action-mapping invariant didn't cover `reset_episode()` / terminal / teardown — **RESOLVED**

§3.5 invariant is rewritten as a single sentence that names every transition in scope: "any state transition that ends an episode (terminal step, `reset_episode()`, env teardown, exception in `step()`/`reset()`) AND any non-`DUCK` action MUST release every held key … *before* the transition completes or the new keys are dispatched." The required behaviors are made concrete in the same paragraph (terminal step releases before returning the terminal tuple; `reset_episode()` releases before dispatching `Space`; teardown / exception paths release in a `finally` block). §6 slice 1 task 2 spec for `reset_episode()` and the new `close()` / `__exit__` surface match the invariant verbatim. §6 slice 1 task 7 test list adds the two missing tests called out in R2: `DUCK → terminal → reset_episode() → JUMP` (asserts terminal release, no `Space` dispatch while held, clean post-reset JUMP) and a context-manager exit while `ArrowDown` is held (asserts `keyUp ArrowDown` in the `finally`/`__exit__` path before `driver.quit()`). The same class of state-machine bug R1 #5 caught for JUMP is now systematically closed across every transition that can leave a key held. No gaps remaining.

### NEW-C — Slice-3 training-budget floor missing — **RESOLVED**

§3.6 split into two sub-budgets. Slice 3 has a **3-day wall-clock cap with both a ≥ 500k env-step floor AND a ≥ 3-eval-cycle floor**, and the AC-STOP-GATE beat-baseline sub-gate is explicitly *not* evaluated until both floors clear. The 500k figure is justified inline against SB3 internals (replay-buffer fill, target-network sync count) and against the §3.2 throughput target. §6 slice 3 task 5 implements the floor-gating; the under-floor path exits via `awaiting-human-decision` *without* firing the beat-baseline gate, and the gate itself now requires the trajectory characterization to be `plateaued` or `declining` to fire (still-rising → extend, do not fire). Task 6 expands the slice-3 wrap to include per-floor pass/fail and the full eval-mean trajectory with explicit characterization. The exit-branches block makes the budget-floor exit precede the gate evaluation in source order. The false-negative-gate-fire risk R2 flagged — "the gate measures operator under-training rather than algorithmic incapability" — is closed by both the floor pre-gate and the trajectory-characterization condition on the gate itself. The planner's deviation from R2's two-option suggestion (combining both floors plus the 3-eval-cycles addition) is reasoned, not arbitrary, and produces a strictly tighter spec than either of R2's individual options.

### R1 #3a / NEW-D — 2-obstacle window justification's unverified Chromium formula citation — **RESOLVED**

The over-confident formula citation is gone. §3.4's "Obstacle window width = 2" paragraph is rewritten to (a) explicitly disclaim independent verification of the page's per-spawn gap formula and trace the post-mortem's reference back to its secondary-source status, (b) keep only the two reasons that don't depend on the formula (5 mostly-sentinel dims for the 3rd slot in the common case; v1's narrowing failure was on sim density, not policy-input width), and (c) defer the actual width lock to **ADR-003 amendment-on-first-use during slice 2**, with the slice-2 fixture-capture exercise (§6 slice 1 task 5 captures (e) and (f)) and the slice-2 random-policy `@pytest.mark.browser` integration test as named evidence sources. Concrete branching is specified: if slice 2 observes ≥ 3 simultaneous obstacles in the planning horizon at game speeds, the window widens to 3 with the observation dim recomputed to 19 and an ADR-003 amendment landed in the same slice; if the observed maximum is consistently ≤ 2 at MET-relevant speeds, ADR-003 records width=2 with fixture evidence as its citation. The widen-to-3 escape hatch from slices 3/4 evidence is also preserved. The false-confidence prose is gone and replaced with an evidence-driven decision pinned to a specific slice. This is the right shape — implementation plans don't need formal proofs; they need defensible decisions or explicit deferrals to evidence-bearing slices.

(NEW-B was explicitly PASS-with-note in R2 and not revise-grade. The planner's choice to defer the one-sentence Δt-invariance acknowledgement to ADR-003 authorship in slice 2 is sound — that ADR will own the pacing contract end-to-end and is the natural home for the note. No verification needed; this is a documentation-placement choice, not an unaddressed finding.)

## Residual risk and the approval question

What's left in the plan after R3 verification:

1. **MET in two bounded iterations is unlikely.** The plan inherits this honestly from the design plan (§0 line 241; §6 slice 5 / 6 exit branches). The most-plausible terminal state is AC-STOP-GATE firing (or the slice-5 `< ~1500` gate blocking slice 6), not slice 6 producing MET. The plan does not claim otherwise. The post-mortem's "AC-STOP-GATE producing a real-time-measured trajectory and a strategic re-plan" is an explicitly-defensible deliverable shape. ADR-able: no — this is a phase-shape decision the design plan already locked. Not a critic concern at R3.

2. **500k env-steps may still be too few for SB3 DQN to clear the heuristic on a 14-dim observation.** R2's central concern was a 28-minute budget; the revised plan has a ~4.6-hour minimum + 3-day cap with a trajectory-characterization gate that distinguishes "still rising" from "plateaued / declining." If the agent is still rising at 3 days, the exit is `awaiting-human-decision`, not a false-negative gate fire. If it plateaus below baseline, that *is* the signal the gate is meant to catch. The worst residual case is "we burn 3 days to learn the algorithm needs more steps than the cap allows," which is recoverable by extending the cap with a human-in-the-loop decision — the artifact set (per-checkpoint eval-means, training-reward CSV, throughput-vs-time log) makes that decision well-evidenced. ADR-able during execution: yes, via the existing exit-branch artifact contract.

3. **Open questions §9 items 1, 2, 3, 4, 6, 7** all have explicit deferrals to ADRs landed during the slice that introduces the surface, with named owners and named slices. None are load-bearing on slice 1 or slice 2 starting cleanly. Item 5 (heuristic threshold formula) is correctly scoped as non-ADR. Item 8 is resolved in §3.7 and listed for traceability. ADR-able: yes, all of them.

4. **The 2-obstacle window is now a deferred decision rather than a fixed lock.** The slice-2 evidence path is concrete enough that the slice-2 ADR-003 author can write a defensible decision either way. ADR-able by design: yes.

**The approval question** — is the residual risk ADR-able during execution, or is it load-bearing enough that approval would be irresponsible?

Honest answer: it is ADR-able. The slice gates (slice-1 throughput / latency / heuristic-stronger exits, slice-3 budget-floor exit, slice-3 beat-baseline gate with trajectory characterization, slice-5 AC-STOP-GATE end-to-end check, slice-6 AC-MET) form a sieve that catches every concrete failure mode the post-mortem and the R1 / R2 critiques surfaced. None of those gates rely on a number that the plan got wrong — the 500k floor is a reasonable lower bound whose only failure mode (under-training masquerading as algorithmic incapability) is the exact failure the trajectory-characterization condition is designed to rule out.

The post-mortem's central reviewer-failure was approving a plan whose internal contradictions and over-confident citations were visible to the reviewer. The R1 BLOCKER (observation-dim mismatch), R1 #5 (action-mapping bug), R2 NEW-A (same bug at episode boundaries), R2 NEW-C (training-budget false-negative gate), and R2 NEW-D (formula citation) were all caught and all closed. R1 / R2 were rigorous, the planner addressed every substantive item with the recommended shape (and in NEW-C went *tighter* than R2 asked), and the remaining concerns are within ADR scope for the slice that owns each surface. Withholding approval on residuals that the executing-stage hooks-and-gates are designed to catch would be process-overreach.

**Yes, the residual risk is ADR-able during execution.**

## Verdict

**Verdict: approve.**

R2's three substantive items (NEW-A, NEW-C, R1 #3a / NEW-D) are all RESOLVED with the recommended shapes — NEW-C is strictly tighter than either of R2's two suggested options. NEW-B's deferral to ADR-003 authorship is sound. The implementation plan is internally consistent, traceable to the approved design plan and the vision lock, addresses every post-mortem-anchored failure mode it can address at plan time (and explicitly defers the rest to slice-owned ADRs), and exits to slice 1 with a concrete first-week task list and a measurement-driven set of slice-1 exit branches that gate everything downstream. The 3 / 2 critique-rounds budget across design and implementation has surfaced and closed every load-bearing concern the post-mortem warned about. Approval is the right call.

Per-stage state update made via `_state_io.update_state_field`: `Implementation Status = approved`, `Implementation Critique Rounds = 3`.
