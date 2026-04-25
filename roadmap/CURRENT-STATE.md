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
- 2026-04-17 slice-1 source half: tester wrote 16 tests (12 unit + 1
  schema-skipped + 4 schema = 14 active + 2 skipped); test contract
  verified ModuleNotFoundError pre-implementation. Builder implemented
  src/browser.py, src/heuristic.py, scripts/eval.py,
  scripts/capture_fixtures.py with the §3.5 held-key invariant, single-
  call DOM read, page-formula score readout, version pinning, pinned
  artifact schema. ADR-001/002/005/006/008 written. Reviewer: pass, 0
  Critical, 0 Major, 4 Minor (2 fixed inline: dead poll loop, missing
  per-episode wall-clock cap; 2 logged TD-001/TD-002). 14 tests pass.
  Slice 1 source committed as 7f1afa55. Stage → blocked /
  awaiting-human-decision pending operator runtime install per
  docs/setup/windows-chrome-pinning.md (download pinned Chrome +
  ChromeDriver, paste back versions + SHA256s).
- 2026-04-23 slice-1 live half: operator delivered Chrome 148.0.7778.56
  (Chrome SHA256 1BCB7A33…7CAC, Driver SHA256 E6D398D2…AA88) to
  C:\chrome-dino-runtime\. Filled in the pinning table, set
  `PINNED_CHROME_MAJOR = 148`, un-skipped `test_one_short_episode`. Three
  bugs surfaced and were fixed before the eval ran:
  (1) **Singleton API** — Chromium dino was rewritten to TypeScript and
  `Runner.instance_` no longer exists; modern API is
  `Runner.getInstance()`. Created
  [`.github/skills/chromium-dino-runner/`](../.github/skills/chromium-dino-runner/SKILL.md)
  to document the new API, the `initializeInstance` assert pitfall, the
  bootstrap sequence, the visibility/blur pause behaviour, and the
  fixed-by-source score formula. Updated `_READ_STATE_JS`, `_GET_SCORE_JS`,
  `_GAME_OVER_JS`, `_PLAYING_JS` with a feature-detected dual-path probe
  (modern first, legacy fallback). (2) **Score formula** — design-plan/impl-
  plan locked `Math.floor(distanceRan * COEFFICIENT)`. Authoritative source
  in `distance_meter.ts::getActualDistance` is
  `Math.round(Math.ceil(distanceRan) * 0.025)`; corrected. (3) **Action
  dispatch** — CDP `Input.dispatchKeyEvent` was sending `{type, key}` only;
  dino's `onKeyDown` reads `e.keyCode` (= CDP `windowsVirtualKeyCode`).
  Added `_KEY_META` table (Space=32, ArrowUp=38, ArrowDown=40) so each
  dispatch carries `code` + `windowsVirtualKeyCode` too. (4) **Episode
  reset** — adapter docstring delegates the wait to the eval layer; eval
  was sending Space and immediately reading state, hitting the 1200 ms
  `gameoverClearTime` gate after a crash and reading the still-crashed
  state. Wrapped boot in a 5 s deadline / 250 ms retry loop in
  `_run_one_episode` that re-dispatches Space until the page reports
  `playing && !crashed`. Live test passes (14 unit + 1 browser + 1
  skipped). 20-episode heuristic eval ran clean to
  `logs/slice1/heuristic_eval.json`. Captured 5 of 7 fixture scenarios via
  capture_fixtures (mid_duck and near_crash unreachable because the
  heuristic crashes on the first cactus — TD-004). **Surfaced concerns**:
  measured heuristic mean = 48.3 (vs design-plan assumption ~1500); root
  cause is the frozen jump threshold firing too early so the dino is
  descending when the cactus arrives — TD-003 logs this as HIGH priority
  because it interacts with VISION-LOCK v1.1.0 binding-constraint 2 (the
  +50 absolute stop-gate becomes trivially clearable from a 48 baseline,
  removing nearly all stop-gate signal). Human decision required before
  slice 3 commits training: tighten AC-STOP-GATE (v1.2.0 lock amendment),
  swap the frozen baseline (also requires lock amendment for AC-SINGLETON
  identity), or accept that MET=2000 carries the real evaluation weight.
  See TD-003 for full disposition options.
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

- 2026-04-25 slice-2 complete: gymnasium env contract shipped per ADR-003 (observation: 14-dim float32 with explicit no-obstacle sentinel +1/0/0/0/-1, scalar type_id, window=2 with amendment-record for window=3 lift; AC-SINGLETON satisfied � MAX_SPEED/CANVAS_HEIGHT/TREX_XPOS module-level literals justified by Chrome-148 pin, canvas_width per-step from raw_state) and ADR-004 (Discrete(3) NOOP/JUMP/DUCK; held-key invariant for both ArrowDown and ArrowUp recorded with 2023 mid-tier-pterodactyl rationale and slice-1 endJump() rationale). 21 unit tests + 1 @pytest.mark.browser integration test. Reviewer R1 found 1 Major (ADR-003 normalization-constants paragraph contradicted as-shipped mechanism); resolved by amending ADR-003 with a per-constant mechanism table + lift trigger. R2 verdict: pass / 0 critical / 0 major. Four reviewer minors (#2 unknown-type sentinel inconsistency, #3 silent default fallbacks, #4 swallowed get_score exception, #5 reward magnitude on no-op past-terminal step) deferred to TD-007 + TD-008 with explicit why-accepted resting on real invariants (Chrome-148 pin, defensive get_score JS, eval-loop break-on-terminated). Commit 17b40fbd. Held-jump conflict between original spec �3.5 and slice-1 implementation resolved at the doc layer: ADR-004 records held ArrowUp as the accepted behavior. Stage advanced to executing / Active Slice = 3 with reset evidence � slice 3 is SB3 DQN training (=500k env-steps capped at 3 days wall-clock); session stops here so the long-running training launch can begin in a fresh session.

- 2026-04-25 resume: human decision on slice-3 wall-clock cap = **4 hours** (vs the 3-day cap in impl plan �6 slice 3). All other slice-3 mechanics from the impl plan stand: =500k env-steps + =3 completed periodic eval cycles are still the �3.6 floors gating beat-baseline evaluation, but the wall-clock-cap exit fires at 4h instead of 3d. TD-003 disposition deferred � proceeding with the slice-1 heuristic baseline (mean=401) as the AC-STOP-GATE comparator; if the 4h cap fires before �3.6 floors are met, the slice-3 budget-floor exit branch (Stage=blocked, Blocked Kind=awaiting-human-decision with throughput projection + eval trajectory artifact) takes precedence over the beat-baseline gate per the impl plan. Stage advanced to executing; slice 3 authoring (ADR-007, src/policy.py, scripts/train.py, tests/test_policy.py, tests/test_train_cli.py) begins next session.

- 2026-04-25 slice-3 authoring complete: ADR-007 (SB3 DQN, Double-DQN, MLP [64,64], hyperparameters trimmed for 4h cap as slice-3-scoped deviations), src/policy.py (LearnedPolicy.load + .act -> int with strict-int coercion), scripts/train.py (CLI with --total-steps required, --eval-every default 50000, --max-wall-hours default 4.0, periodic subprocess eval via scripts/eval.py, per-env-step BaseCallback wall-clock guard), scripts/eval.py adapter (LearnedPolicy.act consumes 14-dim observation; eval._resolve_policy wraps with _observation_from_state). 10 new tests (5 policy + 5 train CLI), all 45 passing. Reviewer R1: 1 Major (wall-clock cap polled per chunk, ~80min overrun risk) resolved by per-env-step BaseCallback; R2: pass / 0 critical / 0 major. Two minors deferred as TD-009 (_observation_from_state leading-underscore but cross-imported) and TD-010 (_git_sha duplicated). Stage now blocked / awaiting-human-decision: the actual 4h DQN training run is the next step but is operator-launched (it's a 4h foreground process that this session cannot run synchronously). Resume with /resume to launch `python scripts/train.py --total-steps 200000` (or operator-chosen step budget) in a dedicated terminal; the slice-3 evidence half (eval-mean trajectory + beat-baseline gate evaluation) follows.
