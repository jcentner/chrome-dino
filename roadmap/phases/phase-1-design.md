# Phase 1 — Design Plan

**Phase Title**: Real-time browser-native agent to MET (or honest stop)
**Status**: in-critique
**Vision anchor**: [`docs/vision/VISION-LOCK.md`](../../docs/vision/VISION-LOCK.md) v1.0.0
**Post-mortem anchor**: [`project-history.md`](../../project-history.md) § "Post-Mortem: How the 2026 Run Went Off the Rails"

This design is the redux's first phase. Its goal is to either hit MET — mean ≥ 2000 across 20 consecutive real-time episodes in unmodified Chrome on Windows — *or* to terminate honestly via the binding-constraint-2 stop gate with a real-time-measured trajectory and a strategic re-plan. Both outcomes are first-class deliverables. Given the post-mortem's evidence base (no prior run, in any configuration, has produced mean ≥ 2000 on the real game; the only deployable real-time agent landed at mean ~555), **the stop-gate-fires-and-we-replan exit is the most plausible terminal state of this phase**, not the slice-6-MET-met exit. The plan is structured to make that exit a clean handoff rather than a failure. Every section below is grounded in the post-mortem; where this plan disagrees with the v1 journal narrative, the post-mortem wins.

## Approach Choice (committed)

**Committed approach: Browser-native online reinforcement learning, single Chrome instance, hand-engineered feature-vector observation extracted from the live page, no headless simulator at any point in the pipeline.**

The candidate-set comparison the critic should challenge:

| Option | Why it's plausible | Post-mortem evidence against | Verdict |
|---|---|---|---|
| **A. Browser-native online RL (chosen)** | Trains directly on the deployment distribution. The class of failure that dominated v1 — sim→real transfer collapse — is structurally impossible because there is no sim. The only previously-shipped real-time agent (2023 DQN, mean ~870) used this shape. | Sample throughput is bounded by real time (≈ one episode per 10–60s). Hits the 3070 Ti's compute budget gently but the wall-clock budget hard. | **Chosen.** |
| **B. Headless-sim RL with domain randomization** | Fast sample collection; orders-of-magnitude more frames per wall-clock hour. | This is exactly what v1 did. v1's transfer ratios were 8% → 9% → 11% across three iterations of physics fixes; the post-mortem identifies the simulator as the wrong abstraction layer entirely, not as a tunable. Adopting B in v1-redux re-creates the dominant failure mode from scratch. | Rejected. |
| **C. Heuristic-only (speed-adaptive rules)** | The 2018 implementation reportedly hit max 2645 with this shape; lowest implementation risk; no training loop. | 2018 reported a *max*, not a mean over 20. **MET = 2000 sits ~3.6× above the only frame-stepped heuristic measurement we have (v1's mean 559); we have no measurement of any heuristic's real-time mean.** The 559 number is from a deterministic rules engine, so the real-time vs frame-stepped gap could go either way for a heuristic — we are not betting the phase on a guess about that gap, we are noting that no heuristic has demonstrated mean ≥ 2000 on the real game in any prior run. The post-mortem demotes the heuristic to "sanity check on the harness," consistent with the user's drop of post-mortem constraint #4. | Rejected as the primary, retained as the harness sanity-check baseline. **Revisit trigger**: if slice 1's measured real-time heuristic mean lands ≥ ~1500, this rejection is reopened via strategic re-plan before slice 2 begins. |
| **D. Behavioural cloning from heuristic + RL fine-tune** | Could warm-start RL past the early-game floor and shorten wall-clock. | Adds a second data pipeline (heuristic rollout collector) and a second optimizer phase (BC then RL), against binding constraint 3. No evidence from prior runs that BC warm-start matters at this scale. | Rejected for v1; available as a strategic-replan target if approach A stalls under the constraint-2 gate. |

**One-line justification:** browser-native online RL is the *only* candidate whose dominant failure mode is "too slow to train" (recoverable by re-plan) rather than "trains the wrong thing" (which is what v1's headless-sim RL did, three times in a row).

The heuristic from option C is still implemented in this phase — but only as a fixed, frozen sanity baseline run through the validation harness in slice 1, to prove the harness actually scores a deployable agent correctly. It is *not* the deliverable and it is *not* in the MET path.

## 1. User Stories

Phase 1 has no end-user beyond the operator running the agent and the future reader of the phase wrap. Acceptance is governed by the §2 ACs, which trace directly to MET and to the binding constraints. User stories are not produced for this phase: the product-owner round on this design surfaced no story-level acceptance criterion, edge case, or scope item that wasn't already in §2 or §7 (see R1 critique item 9). Re-stating the same ACs in As-a/I-want form added ceremony, not signal. The product-owner step is preserved as a workflow gate; its output for this phase is this paragraph.

<details>
<summary>Original story-form draft (kept as a record of the product-owner round; not load-bearing on phase advancement)</summary>

### Story 1: Real-time validation harness with a sanity baseline (Slice 1)
**As an** operator,
**I want to** run a single command that plays the frozen heuristic in unmodified Windows Chrome for 20 real-time episodes and emits raw per-episode scores plus latency/throughput measurements,
**so that** I have a trusted measuring stick before any learning code exists, and so that every later slice's number is comparable to MET out of the box.

**Acceptance Criteria** (traces to AC-HARNESS, AC-SINGLETON, AC-DEPLOYABILITY)
- [ ] A single `scripts/eval.py` invocation against the frozen heuristic produces an artifact containing 20 raw per-episode scores from real-time play in unmodified Chrome on Windows-native.
- [ ] On a 5-episode spot-check, the harness's reported per-episode score matches an independent manual count of the page's score readout within ±5% (AC-HARNESS).
- [ ] The slice 1 wrap records measured end-to-end observe-decide-act latency (ms), measured sample-per-second throughput, and measured game-over detection delay (ms), each with the raw timing log committed alongside.
- [ ] The pinned Chrome version and ChromeDriver version are written into the eval artifact's metadata; the eval script refuses to run when the live versions don't match the pinned pair.
- [ ] Exactly one env module, zero training scripts, and exactly one eval script exist in the repo at slice end (AC-SINGLETON, partial — no train script yet).

**Edge Cases**
- [ ] Chrome auto-updates between sessions → eval refuses to run and prints the version mismatch, rather than producing a number that silently can't be reproduced.
- [ ] Game-over DOM signal arrives late → harness logs both wall-clock and page-clock at game-over so the bias is visible in the artifact, not hidden.
- [ ] Manual count diverges from harness count by >5% → AC-HARNESS fails, slice 1 does not pass, no learned-model claim is permitted downstream.

**Not in Scope**
- No training code, no learned policy, no checkpoint format. The heuristic is frozen and exists only to prove the harness scores a deployable agent correctly.

---

### Story 2: Locked env contract testable without a live browser (Slice 2)
**As a** developer iterating on the training loop,
**I want** the env's observation vector, action space, reward signal, and episode-boundary logic to be unit-testable against captured DOM-state fixtures from slice 1,
**so that** I can change training code quickly without paying the real-time cost of a live Chrome on every test run, while still knowing the env behaves identically when it does drive a live page.

**Acceptance Criteria** (traces to AC-SINGLETON)
- [ ] `src/env.py` exposes a Gymnasium-style `reset()` / `step()` whose observation shape, action set, and reward computation match ADR-003 / ADR-004 and the reward decision recorded in the implementation plan.
- [ ] `tests/test_env.py` exercises observation extraction, reward computation, action encoding, and episode-boundary detection against fixtures captured by slice 1's fixture-capture utility, and runs without launching a browser.
- [ ] An integration test runs a random policy against a live `chrome://dino` for at least one full episode and asserts that the episode terminates exactly once on the page's game-over signal.
- [ ] Observation normalization lives only inside `src/env.py`; `grep` confirms no normalization constants are duplicated in `scripts/` or elsewhere in `src/`.

**Edge Cases**
- [ ] Page emits a transient state that looks like game-over but isn't → episode-boundary detection does not terminate; covered by a fixture from slice 1.
- [ ] Action sent during the page's game-over screen → env ignores the action and surfaces the terminal step rather than crashing.

**Not in Scope**
- No reward shaping beyond the baseline decision recorded in the implementation plan; any deviation requires an ADR per the §3 non-goals.
- No second env module "for testing" — fixtures replace it.

---

### Story 3: Single training script that reports MET-shaped progress (Slice 3)
**As an** operator running the first training round,
**I want** a single `scripts/train.py` that learns against the live env and periodically invokes `scripts/eval.py` to produce a real-time mean over the same 20-episode shape used by MET,
**so that** every progress number in this phase is on the same scale as the deliverable, and the training loop can never quietly drift onto a frame-stepped or otherwise non-deployable proxy.

**Acceptance Criteria** (traces to AC-MET, AC-SINGLETON, AC-STOP-GATE)
- [ ] Exactly one training script and one eval script exist in the repo at slice end (AC-SINGLETON full).
- [ ] `scripts/train.py` periodically invokes `scripts/eval.py` (does not reimplement it) to produce a real-time mean over ≥ 20 consecutive episodes against a held-out evaluation; the periodic eval result is logged alongside training-side reward.
- [ ] Slice 3 wrap reports the first real-time eval-mean produced by a learned policy, with the raw per-episode score artifact committed.
- [ ] The training script never accepts a flag that disables real-time play in the eval it invokes (AC-DEPLOYABILITY).

**Edge Cases**
- [ ] Training crashes mid-run → the most recent checkpoint and most recent eval artifact are still on disk and recoverable.
- [ ] Eval-mean is statistically indistinguishable from the heuristic baseline → recorded as a candidate for the constraint-2 stop gate to fire after slice 5.

**Not in Scope**
- No second algorithm "for comparison." Algorithm choice is locked at implementation planning.
- No multi-Chrome parallelism.

---

### Story 4: First bounded training iteration measured on the same harness (Slice 4)
**As an** operator,
**I want to** make exactly one bounded change informed by slice 3's eval-mean trajectory and re-run training to produce a new real-time eval-mean against the same harness,
**so that** "is this approach moving toward MET?" becomes an empirical question with a comparable number, not an intuition about training-side reward curves.

**Acceptance Criteria** (traces to AC-STOP-GATE, AC-SINGLETON)
- [ ] A new eval artifact (raw per-episode scores from `scripts/eval.py`) is committed after slice 4 training completes, generated by the same single eval script as slice 1 and slice 3.
- [ ] The slice 4 wrap states the slice 3 → slice 4 eval-mean delta in absolute and relative terms.
- [ ] Exactly one training script still exists; the change is a config or in-place code change, not a duplicate `train_v2.py` (any duplication requires an ADR before the duplicate file is created).

**Edge Cases**
- [ ] Slice 4 eval-mean is worse than slice 3's → recorded honestly in the wrap; the change is not silently reverted before the artifact lands.
- [ ] Slice 4 eval-mean ≥ 2000 already → MET claim still must be produced by slice 6 through the canonical eval entry point against a committed checkpoint.

**Not in Scope**
- More than one bounded change per iteration. The post-mortem identified "change several things at once" as a debugging anti-pattern.

---

### Story 5: Second iteration with the binding-constraint-2 stop gate honestly checked (Slice 5)
**As a** future reader of the phase wrap,
**I want** slice 5 to either (a) produce a third comparable eval-mean and an explicit stop-gate decision, or (b) trip the stop gate and route to strategic re-plan instead of slice 6,
**so that** I can trust the phase did not silently keep iterating on a stalled approach the way v1 did.

**Acceptance Criteria** (traces to AC-STOP-GATE)
- [ ] After slice 5, the phase wrap explicitly states the slice 3 → slice 4 and slice 4 → slice 5 eval-mean deltas and applies the §7 threshold (≥ +10% relative or +50 absolute, whichever is smaller).
- [ ] If neither slice 4 nor slice 5 met the threshold, the next state transition is `Stage: blocked` for strategic re-plan (or equivalent), **not** slice 6 (AC-STOP-GATE binding constraint 2).
- [ ] If the threshold was met, the wrap records the actual deltas and the decision to proceed to slice 6 with that evidence cited.
- [ ] Exactly one training script and one eval script still exist (AC-SINGLETON).

**Edge Cases**
- [ ] Eval-mean improved but with extremely high variance (e.g., one outlier episode carries the mean) → wrap reports per-episode distribution, not just mean, so the stop-gate decision is made on signal not noise.
- [ ] Operator wants to "just try one more thing" past the gate → not permitted without strategic re-plan; the gate is the load-bearing escape hatch from sunk-cost iteration.

**Not in Scope**
- A third training iteration tucked inside slice 5. Slice 5 is one bounded change, same shape as slice 4.

---

### Story 6: MET evaluation as the terminal artifact of the phase (Slice 6)
**As a** future reader of the phase wrap (and as the operator producing it),
**I want** the phase to terminate with a single eval artifact — 20 consecutive real-time episode scores from `scripts/eval.py` against the committed checkpoint on a fresh-ish Windows machine — that AC-MET is checked against directly,
**so that** the MET claim is a concrete file on disk that anyone with the pinned Chrome/ChromeDriver versions can re-run, not a number derived from training logs.

**Acceptance Criteria** (traces to AC-MET, AC-DEPLOYABILITY, AC-STOP-GATE, AC-SINGLETON)
- [ ] `python -m <eval-entry-point>` (the single eval script) runs end-to-end on a fresh Windows machine following the committed setup docs and produces an artifact with 20 raw per-episode real-time scores in unmodified Chrome (AC-DEPLOYABILITY).
- [ ] The committed mean over those 20 scores is ≥ 2000 (AC-MET) **or** the phase ends with `Stage: blocked, Blocked Kind: awaiting-human-decision` and the wrap explicitly states MET was not achieved — the loop does not redefine MET.
- [ ] The wrap explicitly records whether the constraint-2 stop gate fired during the phase, and if so, why slice 6 still ran (e.g., it didn't fire, or it fired-and-replanned-back-to-this-slice with cited evidence).
- [ ] The committed checkpoint, the raw per-episode score array, the Chrome/ChromeDriver versions used, and the eval script entry point are all referenced from one section of the wrap doc.

**Edge Cases**
- [ ] Mean is 1999 across 20 episodes → MET is not met. The vision lock is not amended to "≥ 1999" to fit the result (binding constraint 4).
- [ ] Eval crashes on episode 14 of 20 → the artifact is not partially counted toward MET; the run is repeated from a fresh state, or MET is not claimed.
- [ ] Operator notices a flag combination that disables real-time play would have produced a higher number → that flag combination is removed from the eval script per AC-DEPLOYABILITY, not used.

**Not in Scope**
- A second approach for comparison in this phase (deferred to phase 2 per §3 non-goals).
- Cross-platform validation. MET is Windows-native only in this phase.

</details>

## 2. Acceptance Criteria

Phase-level criteria, traceable to MET and to the binding constraints, are stated below.

- **AC-MET (binds to vision MET).** A documented evaluation run produces mean score ≥ 2000 across 20 consecutive real-time episodes in unmodified Chrome on Windows-native, executed by the single eval script defined in this phase, with raw per-episode scores committed alongside the model checkpoint.
- **AC-HARNESS.** For each of 5 spot-check episodes run against the slice-1 heuristic baseline, the harness's reported per-episode score **exactly matches** the page's displayed final score (read from the DOM at game-over). Both numbers are deterministic integers from the same source; there is no measurement noise to budget for. **Operational gap allowance**: if the harness samples score during play and the page-displayed score advances by one tick between the harness's last sample and the game-over screen render, the harness's reported score may be lower than the displayed score by **at most one score-tick** (typically 1 point). Any larger or systematic gap fails AC-HARNESS — slice 1 does not pass and no learned-model claim is permitted downstream. The ±5% tolerance from the prior draft is removed: an integer-vs-integer comparison has no engineering justification for a 5% window, and a constant systematic bias would silently corrupt every later number.
- **AC-SINGLETON.** The repo at end of phase contains exactly one Gymnasium-style environment module, exactly one training script, exactly one evaluation script, **exactly one learned-policy module, and exactly one fixed-policy (heuristic) module; both policy modules are invoked through the single eval script**. Any deviation is backed by an ADR landed before the duplicate is created. (Extension covers `src/heuristic.py` explicitly and bounds future drift toward duplicated policy files of the v1 `scripts/heuristic_agent.py` pattern.)
- **AC-STOP-GATE.** The phase plan executes the binding-constraint-2 stop gate at least once. The gate fires (and the next stage is strategic re-plan, not the next slice) if **either** of the following holds after slice 4 or slice 5:
  - **Movement gate**: the slice-to-slice eval-mean delta does not clear **both** +10% relative **and** +50 absolute (i.e., max-of, not min-of).
  - **Beat-baseline gate**: the slice's learned-policy real-time eval-mean is ≤ the slice-1 heuristic real-time eval-mean (post-mortem lesson 4: the heuristic is the baseline to beat; if the learned model has not cleared it, the learned model has no claim on phase progression). This sub-gate fires from slice 3 onward, not just after slice 4.

  If neither sub-gate fires, the phase wrap explicitly documents that fact with the deltas and the slice-1 baseline cited.
- **AC-DEPLOYABILITY.** The committed agent runs end-to-end from `python -m <eval-entry-point>` on a fresh Windows machine with documented setup steps, with no flag combinations that disable real-time play.

## 3. Non-Goals

Pulled from the vision lock's Out of Scope plus design-driven exclusions:

- No JS frame-stepping as a deliverable code path. (A diagnostic frame-stepper *may* be added later under an ADR; it is not in this phase's slice list.)
- No reuse of v1-era source code (`src/env.py`, `src/chrome_env.py`, `scripts/train.py`, `scripts/train_browser.py`, `scripts/validate_browser*.py`, `scripts/heuristic_agent.py`, v1 tests).
- No second approach in this phase — no parallel BC pipeline, no headless-sim fallback, no second RL algorithm "for comparison."
- No headless simulator. Not as a "fast pre-training" stage, not as a "physics sanity check," not as a future-work hook left in the codebase.
- No multi-Chrome-instance parallelism in v1. (Would require an ADR per constraint 3, and the post-mortem's lesson is that more knobs added before the single-instance path is proven is exactly the failure pattern.)
- No pixel-based observation. Continues the v1-era choice that the post-mortem explicitly listed under "Things that were *not* actually wrong" — feature-vector observation was a good call.
- No reward shaping that references game-internal physics constants. The agent observes what the page surfaces; reward is grounded in the page's own score and game-over signal.
- No cross-platform (Linux/macOS) support in v1. Windows-native per vision; cross-platform is a future-phase concern.
- No model architecture larger than will train comfortably on a single 3070 Ti within a single multi-day session. Concretely: a small MLP (≤ ~100k params) over the feature vector. Anything larger requires an ADR.

## 4. Risks

### 4a. Risks the post-mortem flagged that this design must answer

| Post-mortem failure mode | How this design responds |
|---|---|
| **Headline metric drifts away from deliverable** (frame-stepped score reported as the result). | MET is defined in the vision lock with operational definitions for "real-time," "unmodified Chrome," "episode," and "20 consecutive." The eval script is the *only* path to a MET claim. Frame-stepped numbers, if they exist at all in this phase, are produced by a separate clearly-labelled diagnostic tool that does not share an entry point with the eval script. |
| **Sim → real transfer chase as a sunk-cost spiral** (8% → 9% → 11% across three iterations). | No simulator exists in this phase. The class of bug is structurally absent. |
| **Scaffolding written around each local decision** (two envs, two train scripts, two eval scripts, 11-dim normalization scattered across three files). | AC-SINGLETON enforces one env / one train / one eval. Observation normalization lives in the env module exclusively; the train and eval scripts import it, never reimplement it. Any duplication requires an ADR before the second file is created — checked at slice review. |
| **Vision lock drifts to describe the code, not the goal.** | Binding constraint 4. Builder cannot accommodate scope drift; transitions to `Stage: blocked, Blocked Kind: awaiting-vision-update` and a human decides. |
| **Agent optimizes for "closing the slice" not for the outcome.** | AC-STOP-GATE — binding constraint 2 must be exercised at least once if metric movement is below threshold. The strategic-review stage and product-owner agent are the loop's "is this line of work going to hit MET?" check; this phase's slice list reaches MET evaluation as the final slice, so a strategic review fires against real MET evidence, not against intermediate proxies. |
| **Reviewer never said "this whole line of work won't hit the criterion."** | The product-owner / strategic-review verdict in the `reviewing` stage is explicitly framed against AC-MET, not against per-slice green-checkmarks. |

### 4b. New risks introduced by the chosen approach

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real-time sample throughput too low to converge in reasonable wall-clock. | Medium-High | Phase blocks on MET. | Slice 1 measures actual sample throughput before any learning code is written. If the measured throughput implies that two RL iterations (slices 4 and 5) would exceed **14 wall-clock days** combined, the phase exits to `Stage: blocked, Blocked Kind: awaiting-human-decision` *before slice 2 begins*, with the throughput measurement and projected iteration time as the artifact. This exit is **not** routed through the constraint-2 stop gate — that gate is for metric movement, not throughput. Strategic re-plan candidates the human can pick from include BC warm-start (option D), reduced sample-budget per iteration, or accepting the wall-clock cost. The 14-day number is a soft cap chosen as roughly two work-weeks; it is not pinned in the vision lock and may be revised by the human at the block point. |
| Selenium / ChromeDriver action latency is too high to act within the game's reaction window at high speeds. | Medium | Caps achievable score below MET regardless of policy quality. | Slice 1 measures end-to-end observe-decide-act latency on the harness baseline. If latency dominates over the heuristic's reaction budget at speeds where MET is reached, this is a deployability blocker — surface as `awaiting-human-decision`. Possible mitigations (CDP `Input.dispatchKeyEvent` instead of Selenium key events) are themselves ADR territory. |
| Score-readout extraction is wrong / lossy / off-by-one. | Low-Medium | Every metric in the project is wrong by a constant factor. | AC-HARNESS — independent manual score count on the heuristic baseline before any learned-model claim. |
| Game-over detection is delayed, biasing episode boundaries. | Medium | Inflates or deflates per-episode rewards in a hard-to-debug way. | Game-over is observed via the same DOM signal the page uses; harness logs the wall-clock and the page-clock at game-over for cross-check during slice 1. |
| Windows-native Chrome + Selenium environment is brittle (Chrome auto-updates break ChromeDriver, etc). | Medium | Eval is non-reproducible, MET claim is unverifiable next week. | Pin Chrome and ChromeDriver versions in setup docs; eval script logs both versions at run time and refuses to run if they don't match the pinned pair. |
| 3070 Ti VRAM is the silent bottleneck on a larger policy net. | Low (small MLP per non-goal). | n/a if non-goal is honored. | Non-goal: no architecture beyond a small MLP without ADR. |
| Reward signal from page score is noisy (score increments coarsely). | Low | Slows learning, doesn't block it. | Acceptable; reward shaping (e.g., per-frame survival bonus) is a phase-1 design decision the implementation plan picks. Anything beyond "+1 per frame survived, large penalty on game-over" requires an ADR (post-mortem: reward shaping based on internals was a v1 over-engineering vector). |
| The committed approach (A) is wrong. | Medium — the critic should challenge this hardest. | Phase replans. | Constraint-2 stop gate. Approach A is not load-bearing; the loop has an honest exit if it doesn't move the metric. |

## 5. ADR Candidates

Decisions in this phase that warrant ADRs in [`docs/architecture/decisions/`](../../docs/architecture/decisions/):

- **ADR-001: Approach choice.** Browser-native online RL with feature-vector observation, no headless simulator. Captures the comparison table above and the post-mortem evidence each rejection cites.
- **ADR-002: Platform choice.** Windows-native (not WSL2) for both training and evaluation. Cites the post-mortem's environment-brittleness section and the vision lock's Windows-native operational definition.
- **ADR-003: Observation space.** Hand-engineered feature vector extracted from the live DOM/JS state via read-only access; specific dimensions pinned. Records exactly which fields are read and the read mechanism.
- **ADR-004: Action space.** Discrete (no-op / jump / duck) — needs explicit lock to forestall action-space tinkering as a tuning lever later in the phase.
- **ADR-005: Validation harness shape.** Single eval script, real-time only, deterministic episode-boundary detection, score-readout extraction, pinned Chrome/ChromeDriver versions, raw-per-episode-score artifact format. This is the "harness is real" ADR; AC-HARNESS verifies its claims.
- **ADR-006: Singleton infra rule operationalized.** How the "one env / one train / one eval" rule is enforced at slice-review time (file-existence check; reviewer is briefed to flag any new file in `src/` or `scripts/` that duplicates an existing role).

ADRs are written by the planner during implementation-planning or by the builder at the slice that introduces the decision; they are *not* a prerequisite for this design plan being approved.

## 6. Test Strategy

| Layer | What gets tested | How |
|---|---|---|
| **Unit** | Observation extraction (DOM-state → feature vector), reward computation, episode-boundary detection, action-encoding. Pure functions where possible; thin adapters around the live DOM where not. | `pytest`, against fixture HTML/DOM-state snapshots captured from a real session in slice 1. No live browser in unit tests. |
| **Integration** | Env step contract (`reset() / step()` returns the documented shapes; episode terminates on the page's game-over). Training-loop-to-env integration smoke (one short training run completes without crashing, produces a checkpoint). | `pytest` with a real but short-lived Chrome instance, marked slow / browser-only so unit runs stay fast. |
| **End-to-end (real-time browser, MET-bearing)** | The eval script, run against the committed checkpoint, produces 20 consecutive real-time episodes with raw scores logged. AC-MET is checked here and only here. AC-HARNESS is checked here on the heuristic sanity baseline. | The eval script itself is the test. Output is the raw per-episode score array, committed as an artifact. |
| **Manual** | The independent manual score count on the heuristic baseline (AC-HARNESS). The "watch the agent play in a Chrome window for one episode and confirm it looks like real-time" sanity check before declaring MET. | Human at the keyboard, screen-recording optional. Documented in the phase wrap. |

The e2e layer is where MET lives. Unit and integration tests cannot be cited toward MET.

## 7. Slice Breakdown

Slices are ordered so that the validation harness exists before any learning code, so every later slice can be measured against MET-shaped numbers (real-time, unmodified Chrome). The final slice is the MET evaluation itself.

**Framing for slices 3–6 (read this first).** The most plausible terminal state of this phase is *not* slice 6 producing MET. It is the AC-STOP-GATE firing somewhere in slices 3–5 and the phase exiting to strategic re-plan. The post-mortem's evidence base (no prior run has produced mean ≥ 2000 on the real game; the only deployable real-time agent landed at mean ~555 after two days of clock time; the v1 PPO landed at mean 64 real-time after multi-week iteration) does not support "two bounded iterations from cold start clear MET." Slices 3–5 are structured to either (a) produce real-time-measured evidence that this approach is moving toward MET, in which case slice 6 runs and AC-MET is evaluated, or (b) trip the gate and route to strategic re-plan. **Outcome (b) is not a failure of this phase; it is the phase's primary deliverable in the most plausible outcome.** Slice 6 is conditional: it runs only if neither sub-gate of AC-STOP-GATE has fired by end of slice 5 *and* the slice 5 eval-mean is within plausible reach of MET (operational threshold: ≥ ~1500). Otherwise the phase ends at the gate.

1. **Slice 1 — Real-time validation harness + heuristic sanity baseline.**
   *Files (hints, not commitments):* `src/browser.py` (thin browser-interface adapter: DOM read, key send, game-over detection — *no* Gymnasium-style observation/action/reward contract; that is deferred to slice 2), `src/heuristic.py` (frozen sanity baseline only), `scripts/eval.py` (single eval script), pinned Chrome/ChromeDriver setup docs, fixture-capture utility (captures DOM-state snapshots, not env observations). `src/env.py` does **not** exist at end of slice 1.
   *Scope:* connect to a real `chrome://dino` in unmodified Windows Chrome; extract score readout and game-over signal; run a fixed speed-adaptive heuristic for 20 episodes; produce raw per-episode scores; verify AC-HARNESS via the manual 5-episode exact-match spot-check. Measure and log: end-to-end observe-decide-act latency, sample-per-second throughput, game-over detection delay. These measurements gate every subsequent slice.
   *Slice-1 exit branches (any one of which routes to strategic re-plan or human decision before slice 2 begins):*
   - **Throughput exit**: if the measured throughput implies two RL iterations (slices 4 + 5) would exceed **14 wall-clock days** combined → `Stage: blocked, Blocked Kind: awaiting-human-decision` with the throughput measurement and projected iteration time as the artifact. (Per §4b; not routed through AC-STOP-GATE.)
   - **Heuristic-stronger-than-expected exit**: if the slice-1 heuristic real-time eval-mean lands ≥ ~1500, the candidate-set rejection of option C (heuristic-only) is reopened via strategic re-plan — the phase may pivot to a heuristic-primary approach rather than a learned-policy primary approach.
   - **Latency exit**: if observe-decide-act latency exceeds the heuristic's reaction budget at speeds where MET would be reached, surface as `awaiting-human-decision` (Selenium → CDP `Input.dispatchKeyEvent` is an ADR candidate, not an automatic switch).
   *Out of scope:* anything learned. No `train.py` exists yet. No env module yet.

2. **Slice 2 — Env contract + observation/action space + reward.**
   *Files:* introduces `src/env.py` (the single env module — first appears here, not in slice 1) layered on top of `src/browser.py`; adds `tests/test_env.py` against the DOM-state fixtures captured in slice 1.
   *Scope:* lock the observation feature vector (ADR-003), action space (ADR-004), and reward signal. Unit-test purely against captured DOM-state fixtures so this slice does not need a live browser to pass tests. The env's `step()` is exercised live in an integration test that runs a random policy for a few episodes and confirms episodes terminate cleanly. Because `src/env.py` first appears in this slice, the observation/action/reward contract is locked here and is not changed retroactively against slice 1's harness number — slice 1's harness ran the heuristic against `src/browser.py` directly, and that number remains the AC-HARNESS-verified baseline.

3. **Slice 3 — Training loop (single training script).**
   *Files:* `scripts/train.py` (single training script), checkpoint format, `logs/` artifact directory.
   *Scope:* implement the chosen RL algorithm (algorithm choice — DQN-family vs. PPO — is an implementation-planning decision, not a vision decision). Train against the live env. Write checkpoints. Crucially: the training script *invokes the eval script* periodically against a hold-out evaluation, so progress is always measured in MET-shaped numbers (real-time mean over N episodes), never in training-side reward proxies.
   *Beat-baseline gate (AC-STOP-GATE sub-gate, fires here for the first time):* if the slice-3 learned-policy real-time eval-mean is **≤ the slice-1 heuristic real-time eval-mean**, the phase exits to strategic re-plan **before slice 4 begins**. The learned model has no claim on phase progression until it beats the frozen baseline. This is the post-mortem's lesson 4 codified at the design level ("the heuristic is the baseline to beat, not a trophy"): RL underperforming the heuristic means RL has not done anything yet, regardless of how training-side reward looks.

4. **Slice 4 — One training iteration.**
   *Files:* training-config tweaks; possibly reward-shaping changes (under ADR if non-trivial).
   *Scope:* one bounded round of "look at the eval-mean trajectory, change one thing, retrain." Outputs a new eval-mean number against the same harness as slice 1.
   *Movement gate (AC-STOP-GATE sub-gate):* if slice 4's eval mean does not move **both** ≥ +10% relative **and** ≥ +50 absolute over slice 3's eval mean (i.e., max-of, not min-of), the slice-5 wrap is required to either trip the gate or document why a second sub-threshold-crossing is acceptable evidence.
   *Beat-baseline gate (still active):* if slice 4's eval-mean is ≤ slice-1 heuristic eval-mean, gate fires before slice 5.

5. **Slice 5 — Second training iteration.**
   Same shape as slice 4, one more bounded change. After this slice, AC-STOP-GATE is *checked end-to-end*. The gate fires (next stage is strategic re-plan, not slice 6) if **either**: (a) neither slice 4 nor slice 5 cleared both +10% relative and +50 absolute over the prior slice's eval-mean (movement gate), or (b) slice 5's eval-mean ≤ slice-1 heuristic eval-mean (beat-baseline gate). The phase wrap documents either "gate fired on [movement / baseline / both], replanned" or "gate did not fire, deltas were [... ], slice-5 eval-mean [...] vs heuristic baseline [...]".

6. **Slice 6 — MET evaluation and phase wrap. Conditional on slice 5.**
   *Precondition:* slice 6 executes **only if** AC-STOP-GATE has not fired through slice 5 *and* the slice-5 eval-mean is within plausible reach of MET (operational threshold: ≥ ~1500). If either condition fails, the phase ends after slice 5 with `Stage: blocked` (`Blocked Kind: awaiting-human-decision` if the gate fired; the strategic re-plan happens out of this phase). Slice 6 is **not** the expected terminal state of this phase under the post-mortem's evidence base.
   *Files (if executed):* a final committed checkpoint + raw per-episode-score artifact + phase wrap doc.
   *Scope (if executed):* run the eval script for 20 consecutive real-time episodes against the best checkpoint. AC-MET is evaluated against this single artifact. If MET is met, write the phase wrap and propose phase 2. If MET is not met, the phase ends with `Stage: blocked, Blocked Kind: awaiting-human-decision` per binding constraint 4 — the loop does not auto-redefine MET to fit what was achieved.

The slice count is deliberately small. The post-mortem identified slice proliferation as a failure mode; six slices is the minimum that puts (a) a real harness before any learning, (b) at least one stop-gate check inside the phase, and (c) a real MET evaluation as the terminal step *if* the gates allow it.

---

## Items flagged for human / critic resolution

- **Algorithm choice (DQN-family vs. PPO vs. other).** Deferred to implementation planning. The vision is approach-agnostic on this; the post-mortem evidence is mixed (2023 DQN was the only deployable agent; 2026 v1 PPO failed for sim-transfer reasons that don't apply here). Calling this out so the critic can challenge if they think it should be locked at the design level.
- **Selenium vs. CDP `Input.dispatchKeyEvent` for action dispatch.** Surfaces in slice-1 latency measurement. If Selenium key-event latency caps achievable score below MET, switching to CDP is an ADR; flagging now so the critic does not treat the choice as already made.
- **Whether reward = "+1 per frame survived" is sufficient or whether even simple shaping (e.g., +bonus for surviving past speed-up thresholds) is needed.** Implementation-plan decision; flagged because reward shaping was a v1 over-engineering vector and the bar for adding any should be high.
- **The phase-1 wall-clock budget.** Vision says "time-flexible," but binding constraint 2 means iterations are bounded by metric movement, not by wall-clock. If a slice takes a week of compute to produce one eval-mean number, the gate's two-iteration window is a long calendar window. Worth a human noting whether that is acceptable or whether a soft wall-clock cap should be added. (R1 partially addressed: §7 slice 1 now has a 14-day throughput exit before slice 2; the calendar-cost concern beyond that point is still flagged.)

---

## Round 1 Response

Diff-friendly per-item summary of the changes made in response to [`phase-1-critique-design-R1.md`](phase-1-critique-design-R1.md). Each item references the corresponding section of the revised plan.

1. **Concern (Approach C rejection is weak evidence) — addressed.** Rewrote the option-C cell in the candidate-set table: removed the "real-time mean is likely well below MET" guess; replaced with the honest framing "MET = 2000 sits ~3.6× above the only frame-stepped heuristic measurement; we have no real-time heuristic measurement." Added a §7 slice 1 revisit branch: if the slice-1 measured real-time heuristic mean ≥ ~1500, the C-rejection is reopened via strategic re-plan before slice 2 begins.

2. **Blocker (over-promised path to MET in two iterations) — addressed.** Rewrote the §0 phase intro paragraph and added a "Framing for slices 3–6 (read this first)" block at the top of §7. Both make explicit that the stop-gate-fires-and-we-replan exit is the most plausible terminal state of this phase, not slice 6 producing MET. Slice 6 is now explicitly **conditional**: it executes only if AC-STOP-GATE has not fired through slice 5 *and* the slice-5 eval-mean ≥ ~1500. Otherwise the phase ends after slice 5 with `Stage: blocked`. The phase title was amended to "Real-time browser-native agent to MET (or honest stop)" to make the dual-outcome framing visible at a glance. (Chose the "own that the phase most likely ends in strategic re-plan" path rather than expanding the iteration budget — the iteration budget is a vision-level constraint, not a design-plan lever.)

3. **Blocker (vision-lock threshold direction "whichever is smaller") — addressed via two coordinated edits.**
   - Added `## Proposed Vision Updates` section to [`roadmap/CURRENT-STATE.md`](../CURRENT-STATE.md) (between `## Waivers` and `## Proposed Workflow Improvements`), proposing the threshold be amended from "whichever is smaller" to "whichever is larger" / "both must be cleared," with the v1 walk-through (48 → 53 → 64; deltas 5 and 11 currently pass) cited and the proposal marked awaiting human decision.
   - In this design plan, AC-STOP-GATE and §7 slice 4 / slice 5 use the larger-of / both-must-clear interpretation, now matching vision lock v1.1.0 (binding constraint 2 amended 2026-04-17 from "whichever is smaller" to "both thresholds must be cleared").

4. **Concern (throughput as implicit phase-blocker) — addressed.** Added an explicit slice-1-exit branch to §7: if measured throughput implies slices 4 + 5 exceed **14 wall-clock days** combined, the phase exits to `Stage: blocked, Blocked Kind: awaiting-human-decision` *before slice 2 begins*. The 14-day number is concrete and called out as a soft cap revisable by the human at the block point. Edited §4b's first row mitigation to match: removed the "constraint-2 stop gate fires" misuse, replaced with the dedicated 14-day throughput exit. The throughput exit is **not** routed through AC-STOP-GATE.

5. **Concern (AC-HARNESS ±5% on integer-vs-integer) — addressed.** Replaced ±5% with **exact match** in §2 AC-HARNESS. Defined an operational gap allowance: harness's reported per-episode score may be lower than the page's displayed final score by **at most one score-tick** to accommodate the case where the harness samples score during play and game-over preempts the last sample. Any larger or systematic gap fails AC-HARNESS. Story 1's AC was not separately updated because the user-stories block was stripped per item 9; the phase-level AC governs.

6. **Concern (singleton rule vs `src/heuristic.py`) — addressed.** Picked option (a). Extended AC-SINGLETON wording to "exactly one learned-policy module and exactly one fixed-policy (heuristic) module; both invoked through the single eval script." This codifies `src/heuristic.py`'s status and bounds future drift toward the v1 `scripts/heuristic_agent.py` pattern. Did not pick option (b) (deleting `src/heuristic.py` after slice 1) because the heuristic is the baseline AC-STOP-GATE's beat-baseline sub-gate compares against in slices 3–5; deleting it would break the gate's ability to re-verify the baseline.

7. **Concern (slice 1 introduces env before slice 2 locks contract) — addressed.** Picked the recommended reading: slice 1 now ships `src/browser.py` (a thin browser-interface adapter without a Gym-style observation/action/reward contract); `src/env.py` is deferred to slice 2 along with its contract. Slice 1's fixture-capture utility now captures DOM-state snapshots (not env observations). Updated §7 slice 1 "Files (hints)" line and slice 2 to reflect that `src/env.py` first appears in slice 2. Slice 1's harness number stays valid as the AC-HARNESS-verified baseline because it ran the heuristic against `src/browser.py` directly, not against an env contract that later changes. (Story 1's "exactly one env module" line was not separately updated because the user-stories block was stripped per item 9.)

8. **PASS (Selenium vs CDP).** No action — vision permits CDP `Input.dispatchKeyEvent` per the vision lock's "read-only DOM/JS observation" wording, and the plan's framing of this as ADR territory is correct.

9. **Concern (user stories add ceremony, not information) — addressed via option (a).** Replaced §1 contents with a single paragraph stating that phase 1 has no end-user beyond the operator, that ACs in §2 govern acceptance, that user stories are not produced for this phase, and that the product-owner round surfaced no story-level signal not already in §2 / §7. Kept the original story-form draft inside a `<details>` block as a record of the product-owner round (not load-bearing on phase advancement). **Deleted the duplicate `## User Stories` heading at line 29** that was a hook-workaround artifact. Removed the redundant `## Scope Notes` block whose content was self-referential to the now-stripped stories.

10. **Concern (missing "beat the heuristic" gate) — addressed by extending AC-STOP-GATE.** AC-STOP-GATE now has two sub-gates: **movement gate** (prior threshold direction, now using the intended larger-of interpretation) and **beat-baseline gate** (slice's learned-policy real-time eval-mean ≤ slice-1 heuristic real-time eval-mean ⇒ gate fires). The beat-baseline sub-gate fires from slice 3 onward, not just after slice 4. §7 slice 3 has an explicit "beat-baseline gate fires here for the first time" subsection that exits the phase to strategic re-plan before slice 4 if the learned policy hasn't beaten the frozen baseline. Codifies post-mortem lesson 4 at the design level without re-promoting it to vision-binding. (Chose to fold into AC-STOP-GATE rather than create a separate AC-BEAT-BASELINE — keeps the stop-gate machinery as the single conceptual gate the wrap reports against.)

### Items where I deviated from the critic's recommendation

- **Item 2 (over-promised path).** The critic offered two paths: expand the iteration budget or own the strategic-replan-likely outcome. I chose the second. The iteration budget (max two non-meaningful iterations per binding constraint 2) is a vision-level constraint; the design plan does not have authority to expand it. Owning the realistic outcome distribution is the path that respects authority order.
- **Item 6 (singleton vs `src/heuristic.py`).** The critic offered (a) extend AC-SINGLETON or (b) delete `src/heuristic.py` after slice 1. I picked (a). Reason given inline above: AC-STOP-GATE's beat-baseline sub-gate (added per item 10) needs the heuristic to remain re-runnable through the phase, so deleting it after slice 1 would break the gate.
- **Item 9 (user stories).** The critic offered (a) strip them or (b) compress them aggressively. The prompt instructed (a) unless I had a reason to keep them. I picked (a) but kept the original story-form draft inside a `<details>` block as a record that the product-owner round ran. This is not a deviation in substance; it preserves the audit trail.
