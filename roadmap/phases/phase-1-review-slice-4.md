# Phase 1 — Slice 4 review

**Reviewer scope**: per-slice code quality, architecture compliance, security, doc-sync. Strategic "did we tune the right knob" is the product-owner's call; I review what shipped against [`phase-1-implementation.md`](phase-1-implementation.md) §3.3 and §6 slice 4.

**Files reviewed**:

- [src/env.py](../../src/env.py) — `REWARD_STEP`, `REWARD_TERMINAL`, step docstring.
- [tests/test_env.py](../../tests/test_env.py) — `test_reward_per_step_then_terminal` magnitudes.
- [scripts/train.py](../../scripts/train.py) — `_DQN_KWARGS["learning_starts"]`, `_DQN_KWARGS["exploration_fraction"]`, `ep_rew_mean` source.
- [docs/reference/tech-debt.md](../../docs/reference/tech-debt.md) — TD-008 description.

## Findings

| Severity | File | Finding | Recommendation |
|----------|------|---------|----------------|
| Major | [scripts/train.py:42](../../scripts/train.py#L42), [scripts/train.py:47](../../scripts/train.py#L47), [src/env.py:50-51](../../src/env.py#L50-L51) | **Multiple coupled training-variable changes in one slice.** Impl plan §6 slice 4 task 1 says "Identify exactly one bounded change" and "Exactly one change." The slice ships three training-relevant deltas: reward magnitude (the bounded change), `learning_starts 1k→10k`, `exploration_fraction 0.1→0.2`. The slice-3 diagnosis (Q-collapse to state-value with action-near-tie) motivates the reward change; replay-buffer diversity (`learning_starts`) and exploration-schedule width (`exploration_fraction`) are independent hypotheses, not "tightly coupled small fixes that don't add a variable." If the slice-4 eval-mean moves, attribution is impossible — exactly the trap the §6 wording was written to avoid. The user prompt's framing ("three small folded-in fixes that the impl plan permits") is not what §6 slice 4 task 1 says; impl §6 slice 4 task 1 permits **one** change, not "one + tightly-coupled fixes." | Pick one. Recommended: keep the reward magnitude change only (it is the change the slice-3 diagnosis directly motivates); revert `learning_starts` and `exploration_fraction` to their slice-3 values for slice 4. If the operator believes `learning_starts` is necessary to avoid early-replay collapse under the new reward scale, document that coupling argument in the slice wrap and accept that slice 4 measures the joint effect — but `exploration_fraction` should still revert (see next finding). At minimum, the slice-4 wrap must enumerate every change and explicitly accept the attribution loss. |
| Major | [scripts/train.py:47](../../scripts/train.py#L47) | **`exploration_fraction` change is effectively a no-op under chunked `model.learn(reset_num_timesteps=False)`.** SB3's `BaseAlgorithm._setup_learn(total_timesteps, reset_num_timesteps=False)` sets `self._total_timesteps = num_timesteps + chunk`, and the linear ε schedule reads `progress_remaining = 1 - num_timesteps / _total_timesteps`. The slice-4 train loop calls `learn(total_timesteps=chunk, reset_num_timesteps=False)` with `chunk` bounded by the next ckpt/eval event (~25k steps). For chunk 2 onward, at chunk start `1 - progress_remaining = num_timesteps/(num_timesteps+chunk)` (e.g., n=25k, chunk=25k → 0.5), which already exceeds `exploration_fraction` (0.2), so `get_linear_fn` returns `final_eps=0.05` for the entire chunk. The 0.1→0.2 bump only affects when ε hits `final_eps` *within chunk 1*, and even there `learning_starts=10000` with chunk=25000 gives `(1-progress_remaining) = 10000/25000 = 0.4 > 0.2` at the moment learning starts — i.e., ε is *already at `final_eps=0.05`* the first time a gradient update fires. The user prompt's stated math ("epsilon decays from 1.0 to 0.05 over 57.6k steps") assumes a monolithic `learn(total_timesteps=288000)` call; the chunked architecture defeats it. The same defect existed in slice 3 with `exploration_fraction=0.1` — it just gets escalated to a Major now because slice 4 explicitly justifies the bump in code comments and the user prompt as "decay over 20% of steps," which the runtime does not honor. | Two viable fixes, pick one: (a) revert `exploration_fraction` to 0.1 and record an open question or tech-debt item that the chunked-learn architecture renders this hyperparameter near-inoperative, deferring a fix; or (b) implement a hand-rolled epsilon schedule (e.g., a custom callback that sets `model.exploration_rate` per step against the *budget* `args.total_steps`, not against the per-chunk `_total_timesteps`). Option (a) is cheaper and consistent with slice-4 being one bounded change. Either way, the post-fix slice-4 wrap must state the actual ε trajectory observed (read from `model.exploration_rate` at chunk boundaries) — not the intended one. |
| Major | [scripts/train.py:42](../../scripts/train.py#L42) | **`learning_starts=10000` interaction with the (broken) ε schedule.** Combined with finding above: during steps 0–10000 SB3's `_sample_action` returns uniform-random actions regardless of ε; at step 10001 ε is already pinned at `final_eps=0.05`. The agent therefore has *no* ε-greedy exploration phase at all — it goes straight from "uniform random" to "0.05-noise argmax." If the slice-3 diagnosis is correct (Q-net learned V(s) but not action preference), this is the wrong direction: action-discrimination needs *more* on-policy exploration with a partially-trained Q-net, not less. Even on its own merits, 10k pure-random steps for replay diversity is fine (3.5% of the 288k 4h budget projection — proportionate), but the implicit cost is that the only exploration the run gets is during those 10k pure-random steps. | Tied to the previous finding's fix. If a hand-rolled ε schedule is implemented against `args.total_steps`, the bump to 10k makes sense (random fill + a real ε decay window post-learning_starts). If the no-op stays, consider whether the slice-4 hypothesis even has the experimental support it needs to be informative. |
| Minor | [docs/reference/tech-debt.md:88](../../docs/reference/tech-debt.md#L88) | **TD-008 title is now stale.** Title reads "diverges to -8" — derived from the old `REWARD_TERMINAL=-100` × ~8 spurious steps assumption. With `REWARD_TERMINAL=-1.0`, the same divergence over the same number of steps is at most ~-0.08 (or, more realistically, -1.0 per spurious step), and the body says exactly that. The title and body now disagree on the magnitude of the bug being tracked. | Retitle to something like "`DinoEnv.step` returns `REWARD_TERMINAL` on every no-op past-terminal step" (drop the magnitude from the title, since it's now version-dependent on the constant the title is meant to track). Optionally re-rank Priority — the divergence shrank by 100×, so the case for fixing it is weaker, not stronger. |
| Nit | [scripts/train.py:282-292](../../scripts/train.py#L282-L292) | The `ep_rew_mean` fix is correct and matches SB3 internals (`safe_mean([ep_info["r"] for ep_info in self.ep_info_buffer])` is what SB3 uses for its own logger). One small confirmation worth recording in the slice wrap: SB3's `BaseAlgorithm.__init__` invokes `_wrap_env(env, monitor_wrapper=True, …)` which auto-wraps `DinoEnv` in `Monitor` (the user prompt asked the reviewer to confirm — confirmed by reading SB3 source). `model.set_env(env)` post-eval re-applies the wrap. So `ep_info_buffer` will populate as completed episodes' `info["episode"]` dicts arrive. The `getattr(model, "ep_info_buffer", None)` guard is defensive against an SB3 minor-version rename and is fine to keep. | None — informational. Note in the wrap that the fix is verified, not just hypothesized. |
| Nit | [src/env.py:122](../../src/env.py#L122) | The class docstring still says `truncated == False always`. Still true. The reward-`+0.1`/`-1.0` line is correctly updated. Good. | None. |

## Doc-sync checklist

| # | Item | Status |
|---|------|--------|
| 1 | Vision lock accurate? | ✓ — magnitude tuning is permitted under impl §3.3 ("magnitude tuning is not 'shaping' and is not ADR-gated"). VISION-LOCK v1.1.0 binding constraint 4 forbids reward *shape* changes (extra terms); the two-term shape `+step / -terminal` is unchanged. No violation. |
| 2 | Architecture overview accurate? | ✓ — `docs/architecture/overview.md` does not enumerate reward magnitudes; nothing to update. |
| 3 | README accurate? | ✓ — README does not pin reward magnitudes. |
| 4 | Open questions stale? | ✓ — none of the open questions track the reward magnitude. |
| 5 | Tech debt stale? | Minor finding above (TD-008 title). Otherwise clean. |
| 6 | Glossary complete? | ✓ — no new terms introduced. |
| 7 | Slice-4 wrap exists with old/new values + rationale + slice-3 evidence (impl §3.3 mandate)? | **Not yet** — slice is still executing. Flagged here as the wrap must record: (a) old/new `REWARD_STEP` and `REWARD_TERMINAL`, (b) slice-3 evidence (Q-value near-ties at zeros across action dim ≈ 37, action distribution non-argmax-locked), (c) the additional `learning_starts` and `exploration_fraction` deltas + their independent rationale (or revert), (d) the actual exploration trajectory observed once the schedule fix above is resolved. Without this the impl §3.3 audit-trail-without-ADR contract is incomplete. |

## Spec-compliance summary

- **§3.3 magnitude-tuning permission**: satisfied — reward shape (two-term linear) unchanged, only scalar magnitudes touched. No ADR required. ✓
- **§6 slice 4 task 1 "exactly one bounded change"**: violated. See Major #1.
- **§6 slice 4 task 2 "documented in slice-4 wrap with rationale"**: not yet observable (wrap not written). Doc-sync row #7.
- **§6 slice 4 "no new tests required"**: satisfied — tests/test_env.py only had its expected magnitudes retuned, no new test cases.
- **AC-SINGLETON (in-place edit, not `train_v2.py`)**: satisfied. ✓

## Verdict

Review Verdict: needs-fixes
Critical Findings: 0
Major Findings: 3

---

## R2 (post-fix re-review)

**Files re-reviewed**:

- [scripts/train.py](../../scripts/train.py) — reverts of `learning_starts`, `exploration_fraction`.
- [docs/reference/tech-debt.md](../../docs/reference/tech-debt.md) — TD-008 title; new TD-011.

### R1 finding closure

| R1 finding | Closure |
|------------|---------|
| Major #1 — multiple coupled training-variable changes | **Closed.** [scripts/train.py:42](../../scripts/train.py#L42) reads `"learning_starts": 1_000` and [scripts/train.py:47](../../scripts/train.py#L47) reads `"exploration_fraction": 0.1` — both at slice-3 values. The only training-relevant deltas remaining vs. slice 3 are `REWARD_STEP: 1.0 → 0.1` and `REWARD_TERMINAL: -100.0 → -1.0` ([src/env.py:50-51](../../src/env.py#L50-L51)). The `ep_rew_mean` logging fix ([scripts/train.py:282-292](../../scripts/train.py#L282-L292)) is a pure observability change with no effect on training behavior — agreed with the prompt's classification. Slice 4 now ships exactly one bounded experimental variable. Attribution restored. |
| Major #2 — `exploration_fraction` no-op under chunked `model.learn` | **Closed via TD-011.** [docs/reference/tech-debt.md:139-142](../../docs/reference/tech-debt.md#L139-L142) captures the mechanism (`_total_timesteps = num_timesteps + chunk` per call → ε pinned at `final_eps = 0.05` from chunk 2 onward), the slice-4 acceptance argument (independent variable from reward magnitudes; would compete for attribution), and the resolution path (single `model.learn(total_timesteps=total_steps, callback=...)` with `BaseCallback`-driven checkpoint/eval/CSV cadence). Priority **High**, slice-5 candidate. The reverted `exploration_fraction = 0.1` matches slice-3 behavior, so the slice-4 ε trajectory is identical to slice-3's — no new defect introduced, only a pre-existing one named. |
| Major #3 — `learning_starts=10000` interaction with broken ε schedule | **Closed.** Reverted to `1_000`. With the ε plumbing unchanged from slice 3, slice 4's exploration profile is *byte-identical* to slice 3's (modulo reward magnitudes that affect Q-targets but not action sampling). The "no real ε-greedy phase at all" concern from R1 dissolves: same regime as the slice that produced the 50-mean baseline. |
| Minor — TD-008 title staleness | **Closed.** [docs/reference/tech-debt.md:88](../../docs/reference/tech-debt.md#L88) now reads `### TD-008: \`DinoEnv\` reward on no-op past-terminal step does not return 0.0` — magnitude-independent, will not re-stale on a future REWARD_TERMINAL retune. Body is consistent. |

### Wrap responsibility (R1 doc-sync row #7) — pinned by impl plan

R1 flagged the slice-4 wrap as required-not-yet-written. Confirmed pinned by the implementation plan (the operator does not need a separate review reminder):

- [phase-1-implementation.md:63](phase-1-implementation.md#L63) (§3.3): "slice-N wrap states the old value, the new value, the reason, and the slice-N-evidence that motivated the change."
- [phase-1-implementation.md:322](phase-1-implementation.md#L322) (§6 slice 4 task 2): "Document the change in slice-4 wrap with the rationale (citing the slice-3 evidence that motivated it). Exactly one change."
- [phase-1-implementation.md:325](phase-1-implementation.md#L325) (§6 slice 4 task 5): "Compute and record in slice-4 wrap: slice-3 → slice-4 eval-mean delta absolute and relative; slice-4 eval-mean vs slice-1 heuristic eval-mean."

The wrap will exist (or fail to exist) at phase-review time and is not a code-review surface for slice 4 source.

### New findings in R2

None. The two changed lines in `scripts/train.py` are scalar literal reverts; the new TD-011 entry is well-formed (priority, introduced/surfaced lineage, mechanism, accept-rationale, resolution path) and consistent in tone and depth with TD-007/TD-008/TD-010.

### Doc-sync delta since R1

| # | Item | Status |
|---|------|--------|
| 1 | Vision lock | ✓ unchanged. |
| 2 | Architecture overview | ✓ unchanged. |
| 3 | README | ✓ unchanged. |
| 4 | Open questions | ✓ unchanged. |
| 5 | Tech debt | ✓ TD-008 title fixed; TD-011 added with High priority and full resolution path. |
| 6 | Glossary | ✓ unchanged. |

### Tests

Per the prompt: 50 passed, 1 skipped, 2 deselected after the revert. No source change between the test surface and R1 (R1 had already accepted `tests/test_env.py::test_reward_per_step_then_terminal` retuned to 0.1 / -1.0).

## R2 Verdict

Review Verdict: pass
Critical Findings: 0
Major Findings: 0

