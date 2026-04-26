# chrome-dino — Narrative State

> **Machine-readable workflow state lives in [state.md](state.md).** Hooks
> parse that file. This file holds narrative context that humans read and
> agents append to.
>
> **Per-session activity logs live in [sessions/](sessions/).**

## Active Session

- **Log**: sessions/15f5c0c3-9cbd-49f3-8128-35ce898c612c.md

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

- 2026-04-25 slice-3 hotfix (advanced Stage blocked->executing to apply): user reported intermittent rendering during their wall-cap test of train.py. Root-caused TWO bugs: (a) DinoEnv.reset() was missing the boot-retry loop that scripts/eval.py has � page sometimes hadn't transitioned to playing && !crashed when reset returned, so episodes ran against a frozen game; (b) Chrome's onVisibilityChange handler called Runner.stop() when the OS window lost focus, freezing the game mid-episode and trapping the policy in an unending no-op loop. Fixes: lifted the eval.py boot-retry pattern into env.reset() (5s timeout, 250ms retry interval, 20ms inner poll); enabled CDP Emulation.setFocusEmulationEnabled in browser.launch() so the page never sees a blur. Also fixed a latent subprocess bug in train.py where periodic eval inherited cwd but not PYTHONPATH (silently failed for any caller that didn't pre-export it). Added --device flag to train.py CLI; current torch is 2.11.0+cpu so SB3 runs on CPU regardless � for the 14-dim MLP[64,64] this is fine (env-step latency dominates), but documented the option. Smoke test: 500 steps in 26s (~19 steps/sec, healthy � vs the broken 62 steps/sec against a paused game). Tests Pass=yes (47 passed). Re-blocked Stage=blocked / awaiting-human-decision so operator can launch the 4h training run.

- 2026-04-25 slice-3 hotfix #2: user reported page still showed `Press space to play` static landing on first try of the 4h run. Root cause: `Emulation.setFocusEmulationEnabled` alone wasn't sufficient � Chromium's dino Runner binds `onVisibilityChange` to `document.visibilitychange` / `window.blur` directly, and those events still fire when the OS window loses focus regardless of the focus-emulation flag (which only spoofs `document.hasFocus` semantics). Fixes layered three deep: (1) kept setFocusEmulationEnabled; (2) added `Page.addScriptToEvaluateOnNewDocument` injecting a pre-page script that pins `document.visibilityState='visible'`+`hidden=false` non-configurably AND swallows visibilitychange/blur/pagehide at capture phase before Runner's bubble-phase listener runs (load-bearing fix); (3) added inline `Runner.getInstance().play()` wakeup in the read_state JS as belt-and-braces for any post-activation paused state. Smoke verified end-to-end: 1000 steps + 2 eval cycles in 50s (~20 steps/sec). 47 tests pass.

- 2026-04-25 slice-3 sanity-probe addition: added Browser.sanity_probe() that dispatches kickoff Space then polls read_state for up to 2s requiring playing && currentSpeed > 0 AND distanceRan strictly increasing between two reads. Wired into scripts/train.py at both browser-launch points (initial + post-eval re-launch) so a render-stalled page fails fast instead of burning the 4h training budget. 50 tests pass; live smoke confirmed clean.

- 2026-04-25 slice-3 training run COMPLETE (eval flat at noise floor): commit f3a8ade2, run dqn-20260425T233838Z, 750k steps in 2h14m, exit_reason=step-budget. Eval mean held 48-51 across all 15 checkpoints (50k -> 750k). Final 750k checkpoint probed: action distribution {NOOP:72, JUMP:52, DUCK:76} over 200 random obs (NOT argmax-locked); Q-values at zeros [37.56, 37.55, 37.60] (delta ~0.05 vs magnitude ~37). Diagnosis: reward shape (+1/step, -100/terminal) doesn't carry action-conditional advantage signal; Q-net learned state value (37 -> 96 across input ranges) but not action preference. Argmax over near-tie Q's = effectively random play, hence noise-floor eval. Hypothesis #1 from architecture review confirmed. Tech-debt logged: ep_rew_mean CSV column was empty for all rows (model.logger.name_to_value is cleared by SB3 dump cycle; should use model.ep_info_buffer instead).\n\n- 2026-04-26 resume: stale `Blocked Reason` (it asked operator to launch the 4h training run, which has since completed). Slice-3 beat-baseline gate fired (eval-mean ~50 << slice-1 heuristic 401, plateaued); per impl plan §6 slice-3 task this is exactly the `awaiting-human-decision` branch. Human decision: **advance to Slice 4** per the queued plan in this file (primary: reward reshape +0.1/step, -1/terminal supersedes ADR-003 reward subsection; folded-in: learning_starts 1k→10k, exploration_fraction 0.1→0.2, ep_rew_mean logging fix). Stage advanced to `executing`, Active Slice = 4, slice-evidence reset. Note: impl plan §6 slice 4 task 1 prefers hyperparameter changes over ADR-gated changes; reward reshape requires an ADR-003 amendment — builder must write that ADR amendment as part of slice-4 authoring, not skip it. Slice-3 evidence half (formal beat-baseline-gate wrap citing per-episode distributions) is folded into the slice-4 wrap's "rationale citing slice-3 evidence" requirement rather than written as a separate slice-3 wrap.

## Slice 4 plan (queued, not yet executed)

ONE bounded change at a time per the phase-1 design slice-4 story. Most-load-bearing first: REWARD RESHAPING.

Primary (new ADR superseding ADR-003 reward subsection):
- +0.1/step survival, -1/terminal (preserves sign, restores per-action sensitivity above gradient noise floor)

Folded-in fixes (no separate ADR needed):
- Logging bug: switch ep_rew_mean source from model.logger.name_to_value['rollout/ep_rew_mean'] (cleared by dump) to mean(e['r'] for e in model.ep_info_buffer)
- learning_starts: 1k -> 10k (more replay diversity before first gradient)
- exploration_fraction: 0.1 -> 0.2 (decay over 20% of steps, not 10%)

NOT touching in slice 4 (one variable at a time):
- Network width [64, 64]
- Algorithm choice
- Observation features (ADR-003)

Reward magnitude analysis recorded in /memories/repo/training-observations.md for reference when picking the exact ratio.
