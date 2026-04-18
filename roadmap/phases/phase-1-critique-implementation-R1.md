# Phase 1 Implementation Critique — Round 1

**Reviewing**: [phase-1-implementation.md](phase-1-implementation.md)
**Approved design**: [phase-1-design.md](phase-1-design.md) (Design Status: approved, after design-critique R2)
**Anchors**: [vision lock v1.1.0](../../docs/vision/VISION-LOCK.md), [post-mortem](../../project-history.md#post-mortem-how-the-2026-run-went-off-the-rails)
**Stage**: implementation-critique, round 1 of max 2.

## Summary

| # | Topic | Verdict |
|---|-------|---------|
| 1 | DQN choice + MLP capacity | **PASS** (with citation defect, see #1a) |
| 1a | Cited 2023 baseline number (870 vs 555) | **CONCERN** |
| 2 | CDP locked before slice-1 measurement | **PASS** |
| 3a | 2-obstacle window vs MET-speed planning horizon | **CONCERN** |
| 3b | Sentinel encoding (`xPos_rel=+1.0, type_id=-1`) | **PASS** |
| 3c | Observation dim count (14) vs "one-hot in tensor" claim | **BLOCKER** |
| 4 | Reward magnitude (`+1/-100`) calibration | **PASS** |
| 5 | Stateful duck — release on NOOP only, not on JUMP | **CONCERN** |
| 6 | `src/browser.py` and AC-SINGLETON | **PASS** |
| 7 | 14-day budget routing (separate from AC-STOP-GATE) | **PASS** |
| 8 | Subprocess vs in-process periodic eval | **PASS** (with cadence-pinning note) |
| 9 | Fixture-capture spec sufficient for tester isolation | **PASS** |
| 10 | ADR coverage | **CONCERN** (missing step-pacing decision) |
| 11 | Open-question deferrals | **PASS** with one addition (step pacing) |
| 12 | Post-mortem cross-check | **PASS** |

**Overall verdict: revise.** One BLOCKER (#3c, internal contradiction in the observation spec — the dim count and the "one-hot in tensor" wording are mutually inconsistent), three CONCERNs that are concrete fixes (#1a citation, #5 duck-on-jump, #10 step-pacing decision is not recorded anywhere), and one architectural framing concern (#3a) that may or may not warrant a planner response. None are rethink-grade — the core approach (browser-native DQN with a hand-engineered feature vector and a stateful CDP key adapter) is well-grounded in the post-mortem and consistent with the approved design plan. The fixes are bounded; R2 should be lightweight.

---

## Per-item findings

### 1. Algorithm: SB3 DQN (double + dueling, MLP [64,64]) — PASS

The §3.1 reasoning is the correct shape: at ~1 ep / 10–60s real-time throughput, on-policy methods (PPO) discard each rollout after one update while off-policy DQN reuses every transition many times. PPO's headline sample-efficiency-per-gradient-step pitch is irrelevant when the binding constraint is samples-per-wall-clock-hour. The post-mortem's case against v1 is *not* a case against DQN-as-an-algorithm-class; it is a case against headless-sim-trained-anything. Discrete action space (§3.5) is DQN's natural fit, and replay buffers compose more cleanly with the periodic-pause-for-eval pattern than rollout buffers do. **The swap criterion at "≥ ~50 samples/sec sustained → reopen ADR-007 for PPO" is the right escape hatch** — it commits to the choice without burying the alternative.

MLP `[64, 64]` over a 14-dim observation is ~5k parameters — well inside the design plan's "≤ ~100k params" ceiling and well above the capacity floor for this problem class (the 2023 DQN ran a CNN over images and learned the basic policy; a small MLP over hand-engineered features is fewer effective parameters but applied to a dramatically higher-signal input). No capacity concern.

#### 1a. Citation defect — CONCERN

> §3.1: *"the 2023 DQN (the only deployable real-time agent in the project's history, mean ~870 cited in the design plan)"*

The design plan §0 cites the 2023 DQN at **mean ~555**, not 870. The post-mortem cites mean ~555 / max unknown for the 2023 run; "870" appears nowhere in either anchor document. This is a small factual error but it lives inside the load-bearing argument for picking DQN — and the post-mortem's central lesson is that numbers that don't trace to a primary source are how v1 went wrong. Fix the citation; keep the argument (which works fine at 555).

- **Recommendation**: change to `mean ~555` and re-cite design plan §0 / post-mortem § Attempt 2. The argument doesn't depend on whether the prior number was 555 or 870; making it match the source removes a small but real foothold for "this plan invents numbers."

### 2. CDP locked as default before slice 1 measures — PASS

The design plan §7 slice 1 framed the Selenium↔CDP swap as "an ADR candidate, not an automatic switch" surfacing in slice-1 latency measurement. The implementation plan locks CDP as default *before* measurement, deferring measurement to ADR-008's evidence section.

This is defensible:

1. The 2023 implementation already established Selenium key-event latency as a real bottleneck (post-mortem § Attempt 2). Defaulting to the known-slow option and asking slice 1 to prove the new option is fine would inject a guaranteed-bad measurement when the alternative is known-better.
2. The latency exit branch (`p99 > 16 ms` → `awaiting-human-decision`) gives the slice-1 measurement a real veto, just over a different default.
3. ADR-008 still depends on the slice-1 measurement for its evidence section, so the lock isn't decision-free — it's "default to the better-justified option, document with measurement."

**Vision-lock check on CDP `Input.dispatchKeyEvent`**: vision lock § Operational Definitions permits "automation driver attached" and "Read-only DOM/JS observation" but forbids "injected JavaScript that mutates game state." A `KeyboardEvent` synthesized via CDP enters the page's normal `EventTarget` pipeline — the page's event handler reads it the same way it would read a real keypress. No JS state field is set. No game variable is poked. This is genuinely the same intervention surface as a human keypress, just delivered without OS-level focus dependency. The planner's flagged open question 2 is appropriately self-aware; ADR-008 should explicitly take this position so the next reader doesn't have to re-derive it. PASS.

### 3a. 2-obstacle observation window — CONCERN

The locked observation includes obstacles `[0]` and `[1]` only. At MET speeds (where the page reaches `currentSpeed` near `MAX_SPEED`), obstacle spacing tightens and 3-obstacle clusters of cacti appear regularly. The 2026 v1 used 3 nearest obstacles (post-mortem § 2026 Attempt 3 observations: "up to 3 nearest obstacles"). The implementation plan reduces this to 2 without recording why.

**Why this might be fine**: at the speeds where MET (mean 2000) lives, spacing per the page's own clear-time logic still leaves the 3rd obstacle off-screen-right when the agent is committing to action on the 1st. A 2-obstacle window then covers exactly the planning horizon the policy needs.

**Why this might not be fine**: the post-mortem's bug #1 was an obstacle-density bug ("`minGap * gapCoefficient` instead of `width * speed + minGap * gapCoefficient`") that made obstacles 2–3× too dense. If you got the *real* density wrong by a factor in the sim, the *real* density's planning horizon at MET speeds isn't established by the 2026 v1 run — and the only prior real-time data point we have (2023 DQN, image-based) saw the entire screen anyway.

**Recommendation**: the planner should either (a) cite a concrete reason for narrowing to 2 (e.g., "the page's own `Obstacle` spawning logic guarantees the 3rd obstacle is always off-screen-right when the 1st is at xPos_rel < 0.5") so ADR-003 records the rationale, or (b) widen to 3 obstacles (adds 5 dims, total 19; trivial cost in MLP capacity) to hedge against the post-mortem-style "we narrowed something and it turned out to be the binding gap" failure mode. Either is acceptable to me; what's not acceptable is the silent narrowing without rationale.

### 3b. Sentinel encoding — PASS

The user's framing in the prompt — "if the network learns `xPos_rel < 0.3 → jump`, it will jump on the sentinel boundary" — is mitigated by the second sentinel field. The plan encodes `type_id = -1` for "no obstacle," and real types are non-negative (0, 1, 2). The MLP can learn `(type_id sentinel) → suppress xPos_rel signal` cleanly because the sentinel is *categorical* in the type field, not just a value at the end of the position range. `type_id == -1` IS the "obstacle present" flag — just inverted. The post-mortem's bug #2 (0.0 meant both "no obstacle" and "obstacle at dino") is genuinely fixed by this encoding.

The one residual concern is **encoding**: `type_id = -1` only works if type is fed to the MLP as a scalar (where -1 is a representable value distinct from 0/1/2). If type is one-hot, "-1" doesn't map to anything and the sentinel for "no obstacle" must instead be the all-zeros one-hot or a 4th category. Which raises:

### 3c. Observation dimensionality — BLOCKER

§3.4 says:

> *"`type_id` (CACTUS_SMALL=0, CACTUS_LARGE=1, PTERODACTYL=2; **one-hot in tensor**, but recorded as ordinal here for clarity)"*

and:

> *"**Total: 14-dim float32 vector.**"*

These are inconsistent.

- 4 dino fields (`dino_y_norm`, `dino_jumping`, `dino_ducking`, `current_speed_norm`).
- Per obstacle, 4 numeric fields (`xPos_rel`, `yPos_norm`, `width_norm`, `height_norm`) + `type_id`.
- If `type_id` is **scalar** with values in `{-1, 0, 1, 2}`: 5 fields × 2 obstacles = 10. Total: **4 + 10 = 14**. ✓ matches the headline number.
- If `type_id` is **one-hot** over the 3 real types: 4 + 3 = 7 per obstacle × 2 = 14. Total: **4 + 14 = 18**.
- If one-hot must include a "no obstacle" 4th category (so the sentinel doesn't collide): 4 + 4 = 8 per obstacle × 2 = 16. Total: **4 + 16 = 20**.

The "14-dim total" number is only consistent with a **scalar `type_id` ∈ {-1, 0, 1, 2}**, not with a one-hot encoding. So either the dim count is wrong, the "one-hot in tensor" claim is wrong, or the sentinel encoding strategy is wrong. ADR-003 will inherit whichever inconsistency is left in.

This is a small textual fix but it touches a load-bearing piece of the contract — slice 2 builds the env, the tester writes test_env.py from this spec, and the network's input shape depends on which interpretation is the real one. The reviewer who landed ADR-003 against this spec would either notice and ask the same question (delaying slice 2) or paper over it (and create a v1-style "constants don't agree across files" defect).

- **Type**: Acceptance Gap / internal inconsistency
- **Severity**: Blocking
- **Affects**: §3.4 (observation feature vector) and downstream ADR-003 / `src/env.py` / `tests/test_env.py`
- **Recommendation**: pick one of:
  - **Scalar type_id** with values `{-1, 0, 1, 2}`. Simpler. 14-dim count stays correct. Loses some MLP-friendliness (the network has to learn that the type field is categorical, not ordinal — though for 3 categories this is empirically not a problem in practice with MLPs).
  - **One-hot with explicit "no obstacle" 4th category**. Cleaner representation for a small MLP. Total dim becomes 20. Drop the `type_id = -1` sentinel and use the one-hot's `[0,0,0,1]` slot as the absence indicator.
  - **One-hot 3 + separate `obstacle_present` bit**. Total dim becomes 18. Most explicit; matches common practice.
  Whichever you pick, fix both the parenthetical and the headline dim count in §3.4, and resolve the `type_id = -1` sentinel description (which is incompatible with one-hot).

### 4. Reward magnitudes (`+1/step, -100 terminal`) — PASS

The user's framing in the prompt deserves its own answer: yes, at the heuristic-baseline regime (mean ~559 frame-stepped, episodes on the order of 1000–3000 steps), the `-100` terminal is small relative to the per-step accumulation. But the credit-assignment regime that matters for DQN learning is **early training**, where episodes are 50–200 steps and -100 vs +50/+100 IS a strong, discriminative terminal signal. As the policy improves, the terminal-vs-cumulative ratio naturally drifts toward "terminal is small" — which is the right shape, because at that point the policy already knows when to jump and the per-step survival signal carries the marginal improvement work.

The plan's commitment to "if slice 4 or 5 telemetry shows the magnitude is wrong, it's tuned in-place" is the correct backstop. The distinction the plan draws between *magnitude* tuning (not ADR-gated) and *shape* changes (ADR-gated) is a reasonable line — magnitude tuning preserves the optimization target's shape, only its scale; shaping changes the target. Defensible.

The only nit: §3.3 says "magnitude tuning is not 'shaping' and is not ADR-gated." A reader could read that as license to tweak `-100` to `-50` to `-200` between slice 3 and slice 5 without recording it. Recommend adding "magnitude changes are recorded in the slice wrap that introduces them" to close the audit-trail gap. Minor.

### 5. Stateful duck — release on NOOP only — CONCERN

§3.5's action mapping table:

| Action | CDP key event sequence |
|---|---|
| `NOOP=0` | If a key was held from prior `DUCK`, dispatch `keyUp` for `ArrowDown`. Otherwise nothing. |
| `JUMP=1` | `keyDown` `ArrowUp`, then immediately `keyUp` `ArrowUp` (within the same `step()`). |
| `DUCK=2` | If `ArrowDown` not currently held, dispatch `keyDown` `ArrowDown`. Do **not** release until a non-`DUCK` action is sent. |

**Bug latent in this table**: JUMP does not release a held duck. If the agent issues `DUCK → JUMP`, the adapter sends `ArrowDown keyDown` (held), then `ArrowUp keyDown / keyUp`. ArrowDown remains held. The Chrome dino game's input handler interprets "ArrowUp pressed while ArrowDown held" as a corner case — empirically it does not produce a clean jump (the dino exits ducking and tries to jump from the duck pose, with reduced height or no jump at all depending on the game's frame timing). This is exactly the post-mortem's class-of-bug "every file had a local justification for the state-machine edge case nobody traced end-to-end."

The fix is one row: JUMP should also release a held ArrowDown before dispatching ArrowUp. Or, equivalently, NOOP-style preconditions on every non-DUCK action.

- **Type**: Edge Case / specification defect
- **Severity**: Major (latent functional bug; will silently degrade learned-policy performance until someone watches a recording)
- **Affects**: §3.5 action mapping; `src/browser.py` slice-1 implementation; `tests/test_browser.py` duck-key-release state-machine test
- **Recommendation**: change the JUMP row to "If `ArrowDown` currently held, dispatch `keyUp` `ArrowDown` first; then `keyDown`/`keyUp` `ArrowUp`." Or generalize: "any non-DUCK action releases a held ArrowDown before dispatching its own keys." Update the slice-1 task-2 description and the test in slice-1 task-7's test list to exercise the `DUCK → JUMP` transition.

### 6. `src/browser.py` and AC-SINGLETON — PASS

AC-SINGLETON in the design plan (§2) enumerates: one Gymnasium env, one training script, one eval script, one learned-policy module, one fixed-policy (heuristic) module — all five invoked through the single eval script. `src/browser.py` is not in that list, but it isn't a duplicate of anything in that list either. It's a browser-lifecycle adapter that the env depends on. The design plan's §7 slice 1 explicitly hints at `src/browser.py` ("a thin browser-interface adapter without a Gym-style observation/action/reward contract"), so the implementation plan's introduction of it is consistent with what the design plan already approved.

The post-mortem's "every file had a local justification" concern is real but is pointed at a different pattern: two envs that share no code, two training scripts that are 95% duplicates, two validation scripts. None of those patterns is what `src/browser.py` is — it's a single module owning a single concern (Chrome lifecycle + raw page I/O), called by exactly one consumer (`src/env.py`). The §4 module-ownership-boundaries section makes the call/dependency direction explicit, which is the actual antidote to the v1 sprawl pattern.

The plan's choice to *not* fold browser-lifecycle into env.py keeps the env.py file focused on the Gym contract — which makes the env unit-testable against fixtures (a `FakeBrowser`) without standing up Chrome. That's the post-mortem-anchored win. PASS.

(Minor: the plan could note in AC-SINGLETON's wording, or in ADR-006, that "browser interface adapter" is a bounded sixth module class with exactly-one-of cardinality — to forestall future drift toward `src/browser_v2.py`. Optional.)

### 7. 14-day budget routing — PASS

The design plan §4b explicitly demanded throughput exits be separate from AC-STOP-GATE's metric-movement gate. The implementation plan honors that: the 14-day cap is a slice-1 throughput exit branch, routed via `awaiting-human-decision`, not folded into the constraint-2 stop gate. §3.6 restates this. The two gates measure different things and now exit through different paths. Correct disposition.

**Realism of 7 days/iter**: at 1 ep / 30s real-time and ~1000 steps/episode average, that's ~30 steps/sec → ~2.6M steps in 7 days of pure training. Net of periodic-eval pauses and Chrome cold-restarts (see #8), call it ~1.5–2M effective steps. That's in the credible range for SB3 DQN to reach mean 1500–2000 from a cold start *if* the policy is going to converge at all on this representation; it's also entirely plausible that it doesn't converge, which is what AC-STOP-GATE catches. The 7-day number isn't crazy. The budget is the right ballpark.

### 8. Subprocess vs in-process periodic eval — PASS, with cadence note

The default of subprocess-`scripts/eval.py` keeps training-Chrome and eval-Chrome state cleanly isolated. That's the safer interpretation of vision-lock constraint 3 (per §8 risk 3 in the plan), and it means the eval harness behaves identically whether invoked from training or from the operator at the CLI — preventing the "eval drifts from its standalone behavior" failure mode.

**The cost the plan does not quantify**: each subprocess eval is a Chrome cold-launch + chrome://dino navigate + offline-trigger (~5–10s overhead) + 20 episodes (~10 minutes at heuristic-shape episodes, less at early-training-shape episodes). At an `--eval-every` cadence of, say, 10k steps × 100 evals across a 1M-step training run, that's order-of 100 cold Chrome launches and ~16 hours of pure eval time inside the training-wall-clock budget. At 100k steps cadence, 10 evals and ~1.5 hours. **This makes the eval cadence a real budget-eating knob**, not a free observation.

- **Recommendation**: §6 slice 3 task 4 should record an explicit default for `--eval-every` (something on the order of 50k–100k steps for the first iteration, refinable based on slice-3 throughput evidence) and the slice-3 wrap should record the actual cadence chosen and its share of slice-3 wall-clock. Otherwise this is the kind of unrecorded-knob the post-mortem warned about. Not blocking — slice 3 owns this.

The fallback to in-process eval (re-using the training Chrome) is a reasonable hedge if subprocess proves prohibitively expensive in practice; the plan correctly flags it in §8 risk 3 rather than pre-committing.

### 9. Fixture-capture utility — PASS

§7 / §6 slice 1 task 5 specifies the capture cases (a)–(g), file naming (`tests/fixtures/dom_state/ep<N>_step<M>.json`), and that the format is "the raw dict from `Browser.read_state()`" — i.e., the DOM-source-shaped dict, not the post-normalization 14-dim vector. The slice-2 tester needs:

1. The raw dict's schema (which keys are present, what their types are).
2. The case-coverage list (so they know which fixture corresponds to which test).
3. The expected post-normalization observation values (so they can assert on env output).

(1) is derivable from §3.4's "Source (JS path)" column + (post-fix) the dim/encoding clarification from item 3c above. (2) is the (a)–(g) list. (3) is computable from §3.4's normalization rules.

The tester-isolation hook will be satisfied: tester reads §3.4 + ADR-003 (when written in slice 2) + §6 slice-2 task list, never reads `src/env.py`. The fixture-format anti-staleness clause (top-level `chrome_version` / `chromedriver_version`) is a nice belt-and-suspenders for the version-pinning concern.

The one prerequisite for this to work cleanly is **that #3c is resolved before slice 2's tester begins** — the tester needs to know the observation tensor's shape and encoding to write the assertions. If the dim/encoding ambiguity persists, the tester will write tests that disagree with the env. Treating this as further evidence that #3c is genuinely blocking.

### 10. ADRs — CONCERN (one missing decision)

The eight planned ADRs (001–008) cover the design choices the plan makes explicitly. The reward-magnitude carve-out (no ADR for magnitude, ADR required for shape) is a defensible line.

**Missing**: there is no decision recorded anywhere — neither in an ADR nor in a §3 lock — for **how the env paces its `step()` calls relative to the page's animation frame**. Three plausible regimes:

1. **Free-run**: `step()` reads page state, decides, sends action, returns immediately. The page advances on its own clock between calls. Wall-clock between consecutive `step()` calls = whatever Selenium/CDP latency adds up to. Effective control rate is jittery and varies with system load.
2. **Frame-rate-paced**: `step()` waits until the page has advanced N frames since the last `step()` (using `Runner.instance_.time` or similar) before returning. Effective control rate is fixed; some real-time wall-clock is burned in `time.sleep`.
3. **Wall-clock-paced**: `step()` sleeps to enforce a fixed minimum wall-clock interval between calls. Control rate is fixed but page-frame-count per step still varies.

**This is the post-mortem's central failure mode**. The 2026 v1 trained on the headless sim's deterministic 60fps and deployed at Chrome's actual 51fps; the 15% timing mismatch was the binding gap that three iterations of physics fixes never closed. Training browser-native means there is no sim/deployment mismatch — but the env still has to make a choice about whether the policy sees a fixed sample rate or a variable one, and that choice is not recorded.

The plan implicitly assumes regime 1 (free-run) because §6 slice 1 task 4 logs per-step latency p50/p99 — a metric only meaningful if step rate isn't pinned. But the choice isn't justified anywhere. A learned policy under free-run learns to be timing-agnostic (which is robust); a learned policy under frame-rate-paced learns to assume a fixed obstacle-displacement-per-step (which is brittle if the pacing slips).

- **Type**: Assumption (unrecorded)
- **Severity**: Major
- **Affects**: ADR-003, `src/env.py`, all subsequent learned-policy behavior
- **Recommendation**: add a §3.7 "Step pacing" lock (or equivalent) recording which regime the env uses and why, and add it to the ADR-003 scope (the observation contract includes "what does one step mean in real-time?"). Acceptable resolution: pick free-run with an explicit acknowledgement that the policy must learn to be timing-jitter-tolerant; cite that this is the deployment condition and there is no other condition to match. Alternatively pick frame-rate-paced and accept the wall-clock cost. Either is fine; the post-mortem-anchored failure is *not recording the choice*.

### 11. Open-question deferrals — PASS, with addition

Walking the six the planner listed:

1. **Subprocess vs in-process eval** — defer is acceptable; #8 above. The vision-lock constraint-3 question is well-framed. Slice-3 wrap records the actual choice.
2. **CDP key dispatch as legitimate** — ADR-008 takes a position; defer ok, see #2.
3. **Reward shaping vs observation refinement budget** — the planner's "objective vs representation" distinction is the right axis. Acceptable to defer; slice 4 / 5 ADR amendments are the lock points.
4. **Score-readout formula** — defer to slice-1 measurement, fine.
5. **Heuristic threshold details** — fine; the heuristic is frozen and AC-STOP-GATE compares against whatever it produces.
6. **Algorithm choice at design vs implementation level** — the swap criterion is the safety; fine.
7. **Slice-3 noise-floor exit** — the planner correctly declines to add it (would be implementation-overreach into AC-STOP-GATE). Fine.

**Add**: open question on step pacing (#10). Either resolve in this revision or list it explicitly so the ADR-003 author lands the decision in slice 2.

### 12. Post-mortem cross-check — PASS

Cross-walking the post-mortem's "What the redux has to do differently":

1. **Real-time browser score is the only success metric** → AC-MET, no frame-stepper, no headless sim. ✓
2. **Stopping is a first-class action** → AC-STOP-GATE active from slice 3 (beat-baseline) and slice 5 (movement). ✓
3. **One env / one train / one eval** → AC-SINGLETON; module-ownership boundaries explicit in §4. ✓
4. **Heuristic is the baseline to beat** → beat-baseline sub-gate fires from slice 3. ✓
5. **Vision lock written once and defended** → no plan-driven vision edits; binding constraint 4 honored. ✓

Bug-list cross-walk:

- **Sim-to-real timing mismatch (the actual root cause)** → no sim. ✓ (Note: the residual "step pacing in the env itself" question — item 10 — is the live descendant of this concern in a no-sim world. Calling it out now means it gets settled in slice 2, not in slice 5 retrospectively.)
- **Sentinel encoding (bug #2)** → §3.4 codifies (modulo #3c). ✓
- **Velocity normalization mismatch / observation mapping bugs** → no separate sim, single normalization location, version-checked DOM read with explicit field-presence validation (§8 risk 6). ✓
- **No JS frame-stepping as deliverable** → not in the file list, not in the eval entry point, not in the plan anywhere. ✓
- **Scaffolding sprawl** → §4's exclusion list ("no `utils.py`, no `observation.py` separate from `env.py`, no `replay_buffer.py`, no integration/unit directory split") is the post-mortem-anchored discipline. ✓

Nothing in the post-mortem is missed at the architectural level. The remaining risk is execution: the slice-review reviewer has to *actually* enforce the "no second module of class X" rule, which is a workflow concern (Tier 2 artifact-verified, not Tier 1 hook-enforced) — but that's a builder/reviewer responsibility, not a plan defect.

---

## Verdict

**Verdict: revise.**

Reason: one BLOCKER (#3c — internal contradiction in the observation spec; the dim count and the encoding claim cannot both be true) and three concrete CONCERNs (#1a citation, #5 duck-on-jump latent bug, #10 missing step-pacing decision). All four are bounded fixes with clear recommendations; none threaten the algorithm choice, the action-dispatch lock, the file layout, the slice ordering, or the gate machinery. R2 should be lightweight and primarily verify these specific edits. The core implementation approach — browser-native online DQN with a hand-engineered feature vector, CDP key dispatch, single Chrome instance, AC-STOP-GATE active from slice 3, conditional MET evaluation at slice 6 — is sound and consistent with the approved design plan and the post-mortem's lessons.
