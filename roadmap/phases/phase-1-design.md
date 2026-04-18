# Phase 1 — Design Plan

**Phase Title**: Real-time browser-native agent to MET
**Status**: in-critique
**Vision anchor**: [`docs/vision/VISION-LOCK.md`](../../docs/vision/VISION-LOCK.md) v1.0.0
**Post-mortem anchor**: [`project-history.md`](../../project-history.md) § "Post-Mortem: How the 2026 Run Went Off the Rails"

This design is the redux's first phase. Its only goal is to hit MET — mean ≥ 2000 across 20 consecutive real-time episodes in unmodified Chrome on Windows — with one approach, one environment, one training script, one eval script. Every section below is grounded in the post-mortem. Where this plan disagrees with the v1 journal narrative, the post-mortem wins.

## Approach Choice (committed)

**Committed approach: Browser-native online reinforcement learning, single Chrome instance, hand-engineered feature-vector observation extracted from the live page, no headless simulator at any point in the pipeline.**

The candidate-set comparison the critic should challenge:

| Option | Why it's plausible | Post-mortem evidence against | Verdict |
|---|---|---|---|
| **A. Browser-native online RL (chosen)** | Trains directly on the deployment distribution. The class of failure that dominated v1 — sim→real transfer collapse — is structurally impossible because there is no sim. The only previously-shipped real-time agent (2023 DQN, mean ~870) used this shape. | Sample throughput is bounded by real time (≈ one episode per 10–60s). Hits the 3070 Ti's compute budget gently but the wall-clock budget hard. | **Chosen.** |
| **B. Headless-sim RL with domain randomization** | Fast sample collection; orders-of-magnitude more frames per wall-clock hour. | This is exactly what v1 did. v1's transfer ratios were 8% → 9% → 11% across three iterations of physics fixes; the post-mortem identifies the simulator as the wrong abstraction layer entirely, not as a tunable. Adopting B in v1-redux re-creates the dominant failure mode from scratch. | Rejected. |
| **C. Heuristic-only (speed-adaptive rules)** | The 2018 implementation reportedly hit max 2645 with this shape; lowest implementation risk; no training loop. | 2018 reported a *max*, not a mean over 20. We have no evidence of mean ≥ 2000 from a heuristic at speeds where the Dino's reaction window collapses. v1's heuristic hit mean 559 frame-stepped — meaning real-time mean is likely well below MET. The post-mortem demotes the heuristic to "sanity check on the harness," consistent with the user's drop of post-mortem constraint #4. | Rejected as the primary, retained as the harness sanity-check baseline. |
| **D. Behavioural cloning from heuristic + RL fine-tune** | Could warm-start RL past the early-game floor and shorten wall-clock. | Adds a second data pipeline (heuristic rollout collector) and a second optimizer phase (BC then RL), against binding constraint 3. No evidence from prior runs that BC warm-start matters at this scale. | Rejected for v1; available as a strategic-replan target if approach A stalls under the constraint-2 gate. |

**One-line justification:** browser-native online RL is the *only* candidate whose dominant failure mode is "too slow to train" (recoverable by re-plan) rather than "trains the wrong thing" (which is what v1's headless-sim RL did, three times in a row).

The heuristic from option C is still implemented in this phase — but only as a fixed, frozen sanity baseline run through the validation harness in slice 1, to prove the harness actually scores a deployable agent correctly. It is *not* the deliverable and it is *not* in the MET path.

## 1. User Stories

*(to be populated by product-owner)*

## 2. Acceptance Criteria

Each user story will receive its own acceptance criteria from the product-owner. Phase-level criteria, traceable to MET, are stated below; story-level criteria must be consistent with these.

- **AC-MET (binds to vision MET).** A documented evaluation run produces mean score ≥ 2000 across 20 consecutive real-time episodes in unmodified Chrome on Windows-native, executed by the single eval script defined in this phase, with raw per-episode scores committed alongside the model checkpoint.
- **AC-HARNESS.** The validation harness, run against the heuristic sanity baseline from slice 1, produces a mean score that matches an independent manual count of the page's score readout to within ±5% on a 5-episode spot-check. (This is the "the harness is real" gate; no learned model may be claimed against MET until this passes.)
- **AC-SINGLETON.** The repo at end of phase contains exactly one Gymnasium-style environment module, exactly one training script, and exactly one evaluation script. Any deviation is backed by an ADR landed before the duplicate is created.
- **AC-STOP-GATE.** The phase plan executes the binding-constraint-2 stop gate at least once if metric movement falls below the threshold; if it never trips, the phase wrap explicitly documents that fact.
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
| Real-time sample throughput too low to converge in reasonable wall-clock. | Medium-High | Phase blocks on MET. | Slice 1 measures actual sample throughput before any learning code is written. If throughput-per-hour × expected-sample-budget exceeds the project's wall-clock tolerance, the constraint-2 stop gate fires immediately and we strategic-replan to (e.g.) BC warm-start before investing in a doomed RL loop. |
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

1. **Slice 1 — Real-time validation harness + heuristic sanity baseline.**
   *Files (hints, not commitments):* `src/env.py` (single env module), `src/heuristic.py` (frozen sanity baseline only), `scripts/eval.py` (single eval script), pinned Chrome/ChromeDriver setup docs, fixture-capture utility.
   *Scope:* connect to a real `chrome://dino` in unmodified Windows Chrome; extract score readout and game-over signal; run a fixed speed-adaptive heuristic for 20 episodes; produce raw per-episode scores; verify AC-HARNESS via the manual 5-episode spot-check. Measure and log: end-to-end observe-decide-act latency, sample-per-second throughput, game-over detection delay. These measurements gate every subsequent slice.
   *Out of scope:* anything learned. No `train.py` exists yet.

2. **Slice 2 — Env contract + observation/action space + reward.**
   *Files:* extends `src/env.py`; adds `tests/test_env.py` against fixtures captured in slice 1.
   *Scope:* lock the observation feature vector (ADR-003), action space (ADR-004), and reward signal. Unit-test purely against captured DOM-state fixtures so this slice does not need a live browser to pass tests. The env's `step()` is exercised live in an integration test that runs a random policy for a few episodes and confirms episodes terminate cleanly.

3. **Slice 3 — Training loop (single training script).**
   *Files:* `scripts/train.py` (single training script), checkpoint format, `logs/` artifact directory.
   *Scope:* implement the chosen RL algorithm (algorithm choice — DQN-family vs. PPO — is an implementation-planning decision, not a vision decision). Train against the live env. Write checkpoints. Crucially: the training script *invokes the eval script* periodically against a hold-out evaluation, so progress is always measured in MET-shaped numbers (real-time mean over N episodes), never in training-side reward proxies.
   *Stop-gate checkpoint:* this slice's wrap reports the first real-time-mean number from a learned policy. If it's already plausibly on a trajectory to MET, proceed; if it's not moving, the constraint-2 stop gate may fire here.

4. **Slice 4 — One training iteration.**
   *Files:* training-config tweaks; possibly reward-shaping changes (under ADR if non-trivial).
   *Scope:* one bounded round of "look at the eval-mean trajectory, change one thing, retrain." Outputs a new eval-mean number against the same harness as slice 1.
   *Stop-gate:* if slice 4's eval mean does not move ≥ +10% relative or +50 absolute over slice 3's eval mean (whichever is smaller), the constraint-2 gate fires after slice 5.

5. **Slice 5 — Second training iteration.**
   Same shape as slice 4, one more bounded change. After this slice, the constraint-2 gate is *checked* — if neither slice 4 nor slice 5 moved the metric meaningfully relative to the previous slice, the next stage is strategic re-plan, not slice 6. The phase wrap will document either "gate fired, replanned" or "gate did not fire, metric trajectory was [...]".

6. **Slice 6 — MET evaluation and phase wrap.**
   *Files:* a final committed checkpoint + raw per-episode-score artifact + phase wrap doc.
   *Scope:* run the eval script for 20 consecutive real-time episodes against the best checkpoint. AC-MET is evaluated against this single artifact. If MET is met, write the phase wrap and propose phase 2 (likely: a second approach for comparison, or the writeup). If MET is not met, the phase ends with `Stage: blocked, Blocked Kind: awaiting-human-decision` per binding constraint 4 — the loop does not auto-redefine MET to fit what was achieved.

The slice count is deliberately small. The post-mortem identified slice proliferation as a failure mode; six slices is the minimum that puts (a) a real harness before any learning, (b) at least one stop-gate check inside the phase, and (c) a real MET evaluation as the terminal step.

---

## Items flagged for human / critic resolution

- **Algorithm choice (DQN-family vs. PPO vs. other).** Deferred to implementation planning. The vision is approach-agnostic on this; the post-mortem evidence is mixed (2023 DQN was the only deployable agent; 2026 v1 PPO failed for sim-transfer reasons that don't apply here). Calling this out so the critic can challenge if they think it should be locked at the design level.
- **Selenium vs. CDP `Input.dispatchKeyEvent` for action dispatch.** Surfaces in slice-1 latency measurement. If Selenium key-event latency caps achievable score below MET, switching to CDP is an ADR; flagging now so the critic does not treat the choice as already made.
- **Whether reward = "+1 per frame survived" is sufficient or whether even simple shaping (e.g., +bonus for surviving past speed-up thresholds) is needed.** Implementation-plan decision; flagged because reward shaping was a v1 over-engineering vector and the bar for adding any should be high.
- **The phase-1 wall-clock budget.** Vision says "time-flexible," but binding constraint 2 means iterations are bounded by metric movement, not by wall-clock. If a slice takes a week of compute to produce one eval-mean number, the gate's two-iteration window is a long calendar window. Worth a human noting whether that is acceptable or whether a soft wall-clock cap should be added.
