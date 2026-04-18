# Phase 1 Design Critique — Round 1

**Reviewing**: [`roadmap/phases/phase-1-design.md`](phase-1-design.md)
**Stage**: design-critique, round 1 of max 3
**Anchors**: [vision lock v1.0.0](../../docs/vision/VISION-LOCK.md), [post-mortem](../../project-history.md#post-mortem-how-the-2026-run-went-off-the-rails)

## Summary

| # | Item | Finding |
|---|------|---------|
| 1 | Approach A vs C vs D rejection | CONCERN |
| 2 | Two-iteration path to MET from cold start | **BLOCKER** |
| 3 | Stop-gate threshold direction ("whichever is smaller") | **BLOCKER** (vision-level escalation) |
| 4 | Real-time throughput as implicit phase-blocker | CONCERN |
| 5 | AC-HARNESS ±5% on 5 episodes | CONCERN |
| 6 | Singleton rule vs `src/heuristic.py` | CONCERN |
| 7 | Slice 1 introduces env before slice 2 locks contract | CONCERN |
| 8 | Selenium-vs-CDP as a possible vision-level decision | PASS |
| 9 | User stories add ceremony, not information | CONCERN |
| 10 | Post-mortem lesson coverage — "beat the heuristic" gate missing | CONCERN |

**Overall verdict: revise.** Two blockers, both fixable in-plan without rethinking the approach. The committed approach (browser-native online RL) is sound under the post-mortem; the plan's failure mode is over-promising on what two iterations can deliver and parroting a vision-lock threshold that mathematically *permits* the very sunk-cost pattern it claims to prevent.

---

## 1. Approach A vs C vs D — CONCERN

The rejection of C (heuristic-only) is reasoned as: "2018 reported a *max*, not a mean over 20" and "v1's heuristic hit mean 559 frame-stepped — meaning real-time mean is likely well below MET." That is not evidence; it is a guess presented as evidence.

- **Direction of the frame-stepped vs real-time gap is not obvious for a heuristic.** The 559 frame-stepped number for the v1 heuristic comes from a deterministic rules engine. Real-time vs frame-stepped should not change a rule-based agent's *decisions*; it changes the *latency window* in which they execute. For a heuristic with no learned timing assumptions, real-time could be lower (latency eats reaction budget) *or* roughly equal. The plan asserts "likely well below MET" without citing any measurement.
- **MET = 2000 is the real reason C is dismissible**, not "real-time will be lower than 559." 2000 is ~3.6× the 559 baseline and below the 2018 max of 2645. The honest framing is: "no evidence any heuristic, real-time or otherwise, has produced mean ≥ 2000; we are not betting the phase on it." Use that.
- **D (BC warm-start) rejection is half-hand-waved.** "Adds a second data pipeline … against binding constraint 3" is fair on its face. "No evidence from prior runs that BC warm-start matters at this scale" is absence-of-evidence, not evidence-of-absence. Acceptable as a deferral, weak as a refutation.

**Recommendation.** Rewrite the C rejection cell as evidence-grounded ("we have no measurement of any heuristic's real-time mean; MET sits 3.6× above the only frame-stepped number we have"). Slice 1 produces the real-time heuristic number anyway — if it lands above ~1500, the C-rejection should be revisited via strategic re-plan, and the plan should say so.

## 2. Six-slice plan to MET in two iterations — BLOCKER

This is the central over-promise. The plan commits to:

- Slice 3: first learned-policy real-time eval-mean (cold start).
- Slices 4 & 5: two bounded iterations.
- Slice 6: MET evaluation, expected to clear mean ≥ 2000.

The evidence base for "two iterations from cold start gets to mean ≥ 2000":

- The only previously-shipped real-time browser-trained agent is the **2023 DQN at mean ~555** (per post-mortem `## The Setup`/`### v3 Results`; the user's prompt cites ~870, the post-mortem text cites 555 — either way, well below 2000). That run took **two days** of clock time and produced mean 555.
- The 2026 v1 PPO with a *fast headless sim* hit mean 591 in headless and mean 64 real-time after multi-week iteration.
- No prior run, in any configuration, has produced mean ≥ 2000 on the real game. The 2018 *max* of 2645 is a single-episode outlier from a supervised model, not a mean.

So the design plan's slice list assumes the cold-start learned policy at slice 3 lands somewhere within striking distance of 2000, and that two bounded changes (slices 4 + 5) close any remaining gap. Nothing in the post-mortem, the vision lock, or prior runs supports this. Real-time sample throughput at ~1 episode per 10–60s implies a 2M-timestep PPO run is on the order of **weeks of wall-clock per iteration**. Two iterations is plausibly a multi-month phase, not a sprint.

The post-mortem's central failure was reviewers not saying "this whole line of work won't hit the criterion." The same failure is sitting in this plan: §7 Slice 6 is written as if MET is the expected outcome, with the stop-gate as a decorative escape hatch. The realistic prior is that the stop-gate fires after slice 5 with eval-mean somewhere in the 100s–low 1000s, and the phase ends in `awaiting-human-decision`, not in MET-met.

This is recoverable — the plan does *have* the stop-gate machinery — but the framing is dishonest about which exit is the most likely.

**Recommendation (revise, not rethink).** Rewrite §7 to make the most-likely path explicit: "Slices 3–5 establish a learned-policy trajectory and exercise the stop gate. The gate firing and routing to strategic re-plan is not a failure of this phase; it is the phase's primary deliverable in the most plausible outcome. Slice 6 (MET evaluation) executes only if the gate does not fire and the slice 5 eval-mean is within plausible reach of MET (e.g., ≥ ~1500)." Either expand the iteration budget (slices 4–5 → "≥ 2 iterations until gate fires"), or accept that this phase is more likely to terminate at the strategic re-plan than at MET, and own that in the plan's status framing.

## 3. Stop-gate threshold "whichever is smaller" — BLOCKER (vision-level)

Walk the math. Vision-lock binding constraint 2 says metric movement is "meaningful" iff it clears **+10% relative or +50 absolute, whichever is smaller**. Movement below that smaller threshold ⇒ replan.

| Prior eval-mean | 10% relative | 50 absolute | Smaller (= required movement) | What this means |
|---|---|---|---|---|
| 100 | 10 | 50 | **10** | Need only +10 to keep going. Trivially clearable by noise. |
| 500 | 50 | 50 | 50 | Reasonable. |
| 1500 | 150 | 50 | **50** | Need only +50 (~3% relative) to keep going. Trivially clearable. |
| 48 (v1 actual) | 4.8 | 50 | **4.8** | v1's 48→53→64 movement (5, 11) clears the gate at every step. The post-mortem's named failure pattern *passes* this gate. |

**The "whichever is smaller" rule mathematically permits the exact sunk-cost spiral the post-mortem said constraint 2 must prevent.** The post-mortem's narrative is unambiguous: 8% → 9% → 11% should have stopped after iteration two. Under this threshold, it doesn't.

The intended rule is almost certainly **"whichever is larger"**: require *both* a meaningful relative move (low scores can't be flat-lined) *and* a meaningful absolute move (high scores can't grind out trivial gains). At 48 → max(4.8, 50) = 50; movement of 5 fails ⇒ gate fires. At 1500 → max(150, 50) = 150; movement of 50 fails ⇒ gate fires. Behaves correctly across the range.

This is a vision-lock spec problem, not a design-plan problem — but the design plan parrots the wrong threshold verbatim into §7 and AC-STOP-GATE without noticing. The planner is the first reader who could have caught it.

**Recommendation (revise).** Add a `## Proposed Vision Updates` entry to [`roadmap/CURRENT-STATE.md`](../../roadmap/CURRENT-STATE.md) proposing the threshold be amended from "whichever is smaller" to "whichever is larger" (or equivalent: "both thresholds must be cleared"), citing the v1 walk-through above. Until that is human-resolved, the design plan should explicitly use the *intended* (larger / both) interpretation for AC-STOP-GATE and §7, with a footnote that the vision-lock wording is under proposed amendment. Do not simply ship a plan whose stop-gate provably fails to fire on the historical failure case it was written to prevent.

## 4. Real-time throughput as implicit phase-blocker — CONCERN

§4b acknowledges this risk and §7 slice 1 includes the measurement. Good. But §7 then lists slices 2–6 as if the measurement is a formality. The branch where slice 1 reports e.g. "1 episode per 45s ⇒ ~10 hours per 1000 episodes ⇒ a single PPO iteration is multi-week wall-clock" is not enumerated as an outcome.

The plan says (§4b): *"If throughput-per-hour × expected-sample-budget exceeds the project's wall-clock tolerance, the constraint-2 stop gate fires immediately and we strategic-replan."* Constraint 2 is about *metric movement*, not throughput. Using it as a throughput escape hatch stretches its definition. There is no codified "project wall-clock tolerance" anywhere in the vision or design.

**Recommendation.** Add an explicit slice-1-exit branch to §7: "If slice 1 throughput measurement implies that two PPO iterations exceed [N] wall-clock days, the phase exits to `Stage: blocked, Blocked Kind: awaiting-human-decision` *before* slice 2 begins, with the throughput measurement and projected iteration time as the artifact." Pick N. Don't smuggle this into constraint 2.

## 5. AC-HARNESS ±5% manual spot-check — CONCERN

The page's score is a deterministic integer readable directly from the DOM. There is no measurement noise to budget for. A ±5% tolerance bakes in room for a *systematic* bias — exactly the failure mode the user named:

- Harness over-counts by a constant +3% (e.g., reads `Math.floor(distanceRan / 40)` while page displays `Math.floor(distanceRan / 40)` minus a UI offset, or counts a partial frame at game-over).
- 5-episode spot-check: 0/5 episodes diverge by >5%; AC-HARNESS passes.
- Every later number reads 3% high. A reported "mean 2010" is true mean ~1951. MET claim is wrong by 59 points but no mechanism in this phase catches it.

**Recommendation.** Replace ±5% with **exact match** (per-episode score reported by the harness equals the page's displayed final score). If exact match is infeasible because the harness samples score during play and game-over preempts the last sample, define the allowed gap operationally (e.g., "reported ≤ displayed by at most one score-tick"). Five episodes is then sufficient because each episode is a binary pass/fail. ±5% has no engineering justification when both numbers are integers from the same source.

## 6. Singleton rule vs `src/heuristic.py` — CONCERN

AC-SINGLETON literally says "one env / one train / one eval." `src/heuristic.py` is none of those — it's a policy. Defensible on a strict read.

But the post-mortem's named failure was *every duplicate had a local justification*. `scripts/heuristic_agent.py` (523 lines) is in the post-mortem's bloat list. The redux is reintroducing the same file under a slightly different name and a "frozen baseline" rationale. The pattern is identical to v1's pattern; only the size and the stated intent differ.

**Recommendation.** Pick one of:
- **(a)** Extend AC-SINGLETON to cover policies/agents: "exactly one learned-policy module and exactly one fixed-policy module; both invoked through the single eval script." That codifies the heuristic's status and bounds future drift.
- **(b)** Commit in §7 to deleting `src/heuristic.py` after slice 1, once AC-HARNESS has been verified. The harness, once trusted, doesn't need the heuristic to keep existing.

The current plan does neither and so re-creates the v1 ambiguity that "this one file is fine, locally."

## 7. Slice 1 introduces env before slice 2 locks contract — CONCERN

Slice 1 lists `src/env.py` as a delivered file. Slice 2 locks observation space (ADR-003), action space (ADR-004), and reward signal *and* writes `tests/test_env.py` against fixtures captured by slice 1. So slice 1's `src/env.py` exists *before* its observation/action/reward shape is decided.

Two readings:

- **Slice 1's env is just a browser-interface adapter** (DOM read, key send, game-over detection) without a Gymnasium-style observation/action/reward contract. The heuristic in slice 1 then operates on raw DOM reads, not on a feature vector. Slice 2 layers the Gym contract on top.
- **Slice 1's env is already Gym-shaped** with a tentative observation/action/reward, which slice 2 then formalizes (or quietly changes).

The plan does not say which. Story 1's AC ("Exactly one env module … exists") implies the second reading; §7 slice 2's "lock the observation feature vector" implies the first. If slice 2 changes the observation shape, slice 1's "harness pass" is on a different env than the one used downstream.

**Recommendation.** Pick a reading and write it down. The cleanest split is the first: slice 1 ships a thin browser-interface module (`src/browser.py` or similar) and the heuristic, with `src/env.py` deferred to slice 2 along with its contract. Then slice 2's fixtures captured-from-slice-1 are DOM-state snapshots, not env-observation snapshots, which is what they need to be anyway to test observation extraction. Alternative: merge slices 1 and 2.

## 8. Implementation-planning deferrals as possible vision decisions — PASS

- **Algorithm choice (DQN vs. PPO).** Defensibly ADR-level. Vision is approach-agnostic.
- **Reward shaping.** ADR-level. The non-goal "no shaping that references game-internal physics constants" already bounds it appropriately.
- **Selenium vs. CDP `Input.dispatchKeyEvent`.** Worth checking against vision: "unmodified Chrome … No custom builds, no patched assets, no injected JavaScript that mutates game state. Read-only DOM/JS observation is permitted." CDP `Input.dispatchKeyEvent` injects synthetic input events; it does not mutate game state and it does not modify Chrome. The vision permits it. So this is ADR territory, not vision territory. The plan's framing is correct.

No finding here.

## 9. User stories — CONCERN

User stories 1–6 are 1:1 with slices 1–6 and consist of the slice's AC list rephrased into As-a/I-want form. The "Scope Notes" section under §1 explicitly says: *"Stories 1–6 are deliberately 1:1 with slices 1–6 and do not introduce work outside the §7 slice list."* And: *"flagging here so the critic can confirm the stories add no scope the slices haven't already taken on."* The product-owner acknowledged the stories add no information.

They are ceremony. No new acceptance criterion, no new edge case, no new not-in-scope item appears in the user-stories block that isn't already in §2 or §7.

This is not necessarily a defect — process-wise, the product-owner step ran and produced an artifact. But the prompt asked for an honest call. The honest call is: this section is process compliance, not design content. If the workflow values the product-owner step as a *check* (does the design make sense from a user-of-the-output standpoint?), then a check that uniformly produces "yes, restated" provides little signal.

**Recommendation.** Either:
- **(a)** Accept the stories as ceremony and shorten them to one-liners that link to the corresponding §7 slice and §2 AC, removing the appearance of redundant content.
- **(b)** If the stories are meant to surface anything new, the product-owner should re-run with an explicit instruction to find AC gaps, not to mirror them. Story 6's "Edge Case: mean is 1999" is the one place a story added a useful edge case (and it's a good one); the rest are mirrors.

This finding is not a blocker on phase advancement; it is a workflow signal worth recording.

## 10. Post-mortem lesson coverage — CONCERN

Walking the post-mortem's "What the redux has to do differently" list:

| Post-mortem lesson | Addressed by design? |
|---|---|
| 1. Real-time browser score is the only success metric | **Yes** — AC-MET, AC-DEPLOYABILITY, vision binding constraint 1. |
| 2. Stopping is a first-class action | **Partially** — AC-STOP-GATE exists, but threshold direction (item 3) breaks it on the historical failure case. |
| 3. One env / one train / one eval | **Mostly** — AC-SINGLETON covers the three named artifacts; doesn't cover policies (item 6). |
| 4. **The heuristic is the baseline to beat, not a trophy** | **Not addressed.** Vision lock explicitly demoted this from a binding constraint, citing MET = 2000 sitting above the 559 baseline. The design follows suit. But the *spirit* of the lesson — "if RL doesn't beat the heuristic, RL didn't do anything" — is not codified anywhere. Slice 3's stop-gate fires on "not moving"; it does not fire on "below the frozen baseline you measured in slice 1." The post-mortem's scenario where PPO underperforms a 559-mean heuristic is not blocked by this design. |
| 5. Vision lock written once and defended | **Yes** — binding constraint 4, `awaiting-vision-update` mechanism. |

**Recommendation.** Add an AC-BEAT-BASELINE (or extend AC-STOP-GATE): "if any learned-policy eval-mean from slices 3–5 is ≤ slice-1 heuristic eval-mean × 1.0, the gate fires regardless of slice-to-slice movement." Closes the lesson-4 gap without re-promoting the constraint to vision-binding. The user dropping post-mortem #4 from binding constraints is defensible at the vision level (MET dominates); demoting it to *nothing* at the design level is not.

---

## Verdict

**Verdict: revise.**

Two blockers (item 2: two-iteration over-promise; item 3: stop-gate threshold mathematically permits the v1 sunk-cost spiral) plus seven concerns. None of these require rethinking the committed approach (browser-native online RL on a feature-vector observation) — that approach is the one the post-mortem actually supports. The plan needs to (a) be honest about which exit slice 6 most plausibly takes, (b) flag the vision-lock threshold-direction issue via Proposed Vision Updates and use the intended interpretation in the meantime, and (c) close the smaller gaps in items 1, 4–7, 9, 10. Round 2 critique should focus on whether the revised plan owns the realistic outcome distribution rather than presenting MET-met as the expected case.
