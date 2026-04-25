# Slice 3 — Source-Code Review (Authoring Half)

**Phase**: 1 — Real-time browser-native agent to MET
**Slice**: 3 (SB3 DQN training entry point + learned-policy wrapper + ADR-007)
**Scope**: Authoring only. The actual training run, eval-mean trajectory, and beat-baseline gate evaluation are operator-launched evidence covered in a follow-up review (slice-3 evidence half).
**Reviewer**: Copilot (reviewer mode)
**Date**: 2026-04-25

## Summary

The slice-3 authoring is in good shape. `LearnedPolicy` is a thin, correct wrapper around `DQN.load` with an honest type-coercion to a builtin `int`. `scripts/train.py` is well-structured and lazy-imports SB3 so `--help` and the import-time test stay fast. ADR-007 is unusually thorough — it surfaces the slice-3 hyperparameter trim *as* a deviation from impl §3.1 rather than rewriting history, and pins the swap criterion. The eval-side adapter for the dict→14-dim mismatch is the right side of the boundary. **One Major finding**: the wall-clock-cap polling is only checked between SB3 `learn()` chunks of up to 25,000 env-steps, which at the slice-1-measured ~5 samples/sec can let the run blow past the 4-hour cap by ~80 minutes plus the cost of a periodic-eval subprocess. Three Minor and one Nit; none of them block the training run.

## Per-focus walkthrough

### 1. Spec compliance — ADR-007 vs impl §3.1

ADR-007 documents three trims from impl §3.1 defaults: `buffer_size` 1M→100k, `target_update_interval` 10k→1k, `learning_starts` 50k→1k. The justification is tight and the math is right: at ~5 samples/sec × 4h = ~72k samples, a 1M buffer is mostly empty, a 10k target-update interval gives ~7 syncs, and a 50k learning-starts is 70% of the run on uniform-random exploration. The ADR is explicit that these are **slice-3-scoped trims, not phase-permanent** ("If the operator extends the cap past the 4-hour budget, the trims must be revisited in the same slice wrap that records the extension"). That's the right framing — it doesn't pretend §3.1 was wrong, it records that §3.1's defaults were calibrated for the 3-day cap and the 4h cap needs different numbers.

The dueling-DQN paragraph hedges ("if SB3's vanilla `DQN` does not expose dueling on the MLP policy in the installed version, dueling is **dropped** for slice 3 (recorded as a slice-3-wrap deviation)"). That's an honest hedge — SB3's stock `DQN` does not expose dueling on `MlpPolicy` without a custom policy class, and the configured `_DQN_KWARGS` block does not enable it. The wrap should record "dueling dropped" cleanly; the title of ADR-007 should *probably* be amended to "DQN (double, MLP `[64, 64]`)" and either drop the "dueling" promise or land a custom dueling-MLP policy. Logging here as Minor — the algorithm-class choice is not affected.

### 2. Contract reconciliation in eval.py

The slice-3 tester surfaced a real contract gap: `_resolve_policy` returned a callable that takes a state dict (`policy_act(state)`), but `LearnedPolicy.act` takes a 14-dim numpy observation. The shipped fix wraps the load call:

```python
def _learned_act(state: dict) -> int:
    obs = _observation_from_state(state)
    return loaded.act(obs)
```

This is the **right** side of the boundary. The alternative — make `LearnedPolicy.act` accept dicts — would push DOM-shape knowledge (canvas width, type-id table, sentinel encoding) into `src/policy.py`, which would (a) violate AC-SINGLETON's normalization-constants-live-only-in-`src/env.py` clause, (b) duplicate the §3.4 mapping that `_observation_from_state` owns, and (c) make `LearnedPolicy.act` env-coupled where today it's a clean numpy→int function that any future env reuse (sim, fixture replay, transfer experiment) can call directly. Heuristic continues to consume the dict because it's a hand-coded rule, not an SB3 model with a fixed input dim — that asymmetry is the right one. The ADR-007 "Consequences" section now records this routing explicitly.

The one Minor here: `_observation_from_state` is a leading-underscore name (intent-private) but is exported in `src/env.py::__all__` and imported by `scripts/eval.py`. If the privacy intent is real, drop the underscore (and the stale "private" connotation in tests/imports); if the export intent is real, drop the underscore. Today's state is "private but used by a sibling script," which is the worst of both. Logged as Minor.

### 3. AC-SINGLETON for hyperparameters

Grep confirms hyperparameter literals live only in `scripts/train.py::_DQN_KWARGS` (and ADR-007). The matches in `tests/test_policy.py` are a self-contained `DQN(...)` construction for a tiny in-process dummy env (`learning_starts=0, buffer_size=100`) — these are test-fixture values, not the slice-3 production hyperparameters, and SB3 requires them at construction time. They cannot live in `_DQN_KWARGS` because the test must not import `scripts.train` for this (training-Chrome side-effects, slow import). Acceptable. AC-SINGLETON satisfied.

### 4. Wall-clock cap mechanics — **Major**

The cap is enforced by polling `time.monotonic() - wall_start >= wall_cap_seconds` at the *top* of the outer `while` loop, between SB3 `learn()` chunks. Chunk size is `min(next_ckpt_at, next_eval_at, args.total_steps) - steps_done`, with default `--ckpt-every=25_000`. At the slice-1-measured ~5 samples/sec, **a single 25k-step chunk takes ~83 minutes**. If the wall-clock counter is at e.g. 3h 10m when a chunk starts, the chunk completes at 4h 33m — 33 minutes past the 4h cap — and only *then* does the next loop iteration see the wall-cap and break. Add a periodic-eval subprocess (up to the hardcoded 60-minute timeout) that may also fire inside the same chunk window, and the worst-case overrun is ~80 minutes plus subprocess time.

Recommendation: cap the chunk size to a wall-clock-bounded value. Two cheap options:

- **Time-bounded chunk**: `chunk = min(next_event - steps_done, max_chunk_steps_per_wall_minute * remaining_minutes)` using a conservative samples/sec estimate (e.g., 10 samples/sec → 600 steps/min; a 30-minute remaining window caps the chunk at 18,000 steps).
- **SB3 callback**: pass an `BaseCallback` to `model.learn(...)` that returns `False` from `_on_step` once `time.monotonic() - wall_start >= wall_cap_seconds`. SB3's `learn` honours `False` returns and exits the chunk early. This is the cleaner of the two — keeps the outer loop unchanged and stops mid-chunk on the next env-step.

The current behavior is *bounded* (the outer loop will see the cap and break before the next chunk), so this is Major rather than Critical — the operator running the 4h cap will know to budget for the chunk-size overrun, but the cap as advertised is not the cap as enforced.

### 5. Subprocess eval reliability

The flow: `browser.close()` → ensure-checkpoint-on-disk → `subprocess.run(scripts/eval.py)` → `_make_env_and_browser()` → `model.set_env(env)` → continue training.

`model.set_env(env)` is sufficient for SB3 DQN's continuity needs: SB3's `OffPolicyAlgorithm.set_env` swaps the rollout-collection env but **preserves the replay buffer, the Q-network weights, the target network, and `num_timesteps`**. The replay buffer is owned by the model (not the env), so an env swap doesn't touch it. Reference: SB3 source — `OffPolicyAlgorithm.set_env` calls `BaseAlgorithm.set_env` which only re-wires the `VecEnv` reference and re-runs observation-space compatibility checks; nothing in the buffer or learner state is reset. This pattern is the documented way to do periodic env-swap during training.

Two minor caveats worth noting (both non-blocking):

- After `set_env`, SB3 will raise on the next `learn` call if the new env's `observation_space` or `action_space` doesn't match the model's. `_make_env_and_browser()` always returns the same `DinoEnv` shape, so this is safe — but a defensive `assert env.observation_space == model.observation_space` after `set_env` would surface a Chrome-version-induced shape skew (e.g., a future ADR-003 amendment widening to window=3) immediately rather than at next `learn()`.
- The eval subprocess writes a sidecar JSON checkpoint via `train.py` (`<step>.json`) but the *training-side* checkpoint write happens in the `if steps_done >= next_ckpt_at:` branch which fires *before* the eval branch in the same iteration. Good — eval always loads from a freshly-saved checkpoint. The "force a checkpoint right now" fallback inside the eval branch handles the case where eval fires before ckpt would naturally fire (i.e., `--eval-every < --ckpt-every`).

No finding here — call this verified.

### 6. Test quality

`tests/test_policy.py` (5 tests) — every assertion ties to a real spec property:

| Test | Pinned contract |
|---|---|
| `test_load_round_trip_returns_valid_action` | `LearnedPolicy.load` accepts an SB3-`DQN.save`-produced zip; `act` returns one of `{0, 1, 2}` (ADR-004 action space) |
| `test_act_returns_int_not_numpy_scalar` | `type(action) is int` (strict) and `not isinstance(action, bool)` — defends against `Browser.send_action(int)` receiving `np.int64`, which the docstring of `LearnedPolicy.act` explicitly calls out |
| `test_act_is_deterministic` | Greedy eval (impl §3.1 / ADR-007); two `act` calls on the same obs return the same int |
| `test_load_missing_file_raises_informatively` | Missing checkpoint raises with a message that mentions the path or one of `{checkpoint, not found, missing, no such file}` |
| `test_load_non_sb3_zip_raises_informatively` | Junk-bytes-at-zip-path → load raises with a message containing one of `{checkpoint, load, sb3, zip, invalid}` |

The dummy env (14-dim Box, `Discrete(3)`, terminate-after-1-step) is the right shape and trains a real SB3 DQN for `total_timesteps=10` — so the round-trip is exercised against a real `DQN.save`/`DQN.load` pair, not a mock. No tautology. No live browser. Good.

`tests/test_train_cli.py` (5 tests, one of which is the in-process `main(['--help'])` import test) — every assertion ties to an impl §6 slice 3 task 6 contract:

| Test | Pinned contract |
|---|---|
| `test_help_exits_zero_and_mentions_required_flags` | `--help` exits 0; mentions `--total-steps`, `--eval-every`, `--ckpt-every` (impl §6 slice 3 task 6) |
| `test_help_mentions_wall_clock_cap_flag` | A wall-clock cap flag is documented (name not pinned — implementation-defined per the tester's resolved-ambiguity note) |
| `test_missing_required_flag_exits_nonzero` | Argparse-style missing-required exit code in `{1, 2}` |
| `test_unknown_flag_exits_nonzero` | Argparse rejects unknown flags |
| `test_main_callable_imports_cleanly` | `from scripts.train import main` works; `main(['--help'])` raises `SystemExit(0)` — pins that `--help` short-circuits before any browser/SB3 setup, so import-time tests don't pay Chrome-launch cost |

All five subprocess tests carry a 30-second timeout per the tester's resolved-ambiguity note — guards against an accidental Chrome launch at module load hanging the suite. Good defensive choice.

No test exercises a live training run. That's intentional: the live training run is the slice-3 *evidence*, not a test. Logged as a positive — no over-reach into the operator-evidence half.

### 7. Security

- No new secrets, no hardcoded credentials.
- `subprocess.run([sys.executable, str(_REPO_ROOT / "scripts" / "eval.py"), ...], check=True, timeout=...)` uses list-form + no `shell=True`. No injection surface even if `args.checkpoint` contained shell metacharacters (the operator owns checkpoint paths, but the list-form invocation closes the surface anyway).
- `DQN.load(checkpoint_path)` is `pickle`-based (SB3 wraps a torch zip-with-pickle archive). This is a known unsafe-deserialization surface for arbitrary attacker-controlled checkpoints. **Acceptable here**: the operator owns every checkpoint path passed to `LearnedPolicy.load` (slice-3 training writes them; eval-from-checkpoint loads them; no untrusted source). If a future slice introduces operator-uploaded or downloaded checkpoints, this becomes a real concern and `LearnedPolicy.load` should grow a path-allowlist or signature-verification step. Logging here as zero-finding for slice 3 because the trust boundary is correctly closed; the SB3-pickle surface should be tracked as a phase-end note in the slice-3 wrap or as a `TD-NNN` if later phases broaden the trust boundary.
- `_git_sha()` swallows all exceptions and returns `"unknown"` — informational metadata only, no security relevance.

### 8. Doc-sync

| Item | Status | Notes |
|---|---|---|
| **Vision lock** | Accurate | No scope drift; AC-STOP-GATE intact |
| **ADR-007** | New, present, thorough | See §1 above |
| **ADR-003** | Already updated in slice 2 | The "eval.py owns the dict→obs transform" line in ADR-007 Consequences is the right cross-reference |
| **Architecture overview** | Stale (was already a draft template before slice 3) | Not slice-3's regression — this was already empty at slice 1. Logged as a phase-end task, not a slice-3 finding |
| **README** | Acceptable | Project README is intentionally bot-workflow-focused; no need to document `scripts/train.py` here |
| **Glossary** | No new project-specific terms in this slice (DQN, replay buffer, target network are SB3-standard, not project-coined) | Pass |
| **Open questions** | None resolved or opened by this slice | Pass |
| **Tech debt** | Nothing new accepted in this slice | Pass — but the dueling-or-not call (§1 Minor) and the SB3-pickle trust-boundary note (§7) belong in the slice-3 wrap |

### 9. Code style + anti-slop

- Type hints present on all public surfaces.
- Module + class + public-function docstrings present and earn their keep (each one names the spec/ADR anchor).
- Inline comments cite ADR-007 / impl §3.6 / impl §6 — no slop comments restating obvious code.
- Lazy imports (SB3, `Browser`, `DinoEnv`) keep `--help` and the import-time test fast — explicitly noted in the docstring of `_make_env_and_browser` and `_build_argparser`.
- `_DQN_KWARGS` is a single audit-trail block with a comment header explaining "edits here are the audit trail; keep them in this single block, not split across files." Good.
- `_git_sha()` is duplicated between `scripts/train.py` and `scripts/eval.py`. This is minor (5-line function, two implementations diverge negligibly), but it's a borderline AC-SINGLETON-flavored duplication: the next module that wants the git SHA will copy-paste a third time. Logged as Nit.

## Findings

| Severity | File | Finding | Recommendation |
|----------|------|---------|----------------|
| Major | [scripts/train.py](../../scripts/train.py#L233-L262) | Wall-clock cap is only checked between `learn()` chunks of up to `--ckpt-every` (default 25,000) env-steps. At slice-1-measured ~5 samples/sec, a single chunk is ~83 minutes; worst-case overrun of the 4-hour cap is ~80 min + the periodic-eval subprocess time | Add an SB3 `BaseCallback` whose `_on_step` returns `False` once `time.monotonic() - wall_start >= wall_cap_seconds`. SB3 `learn()` honours `False` and exits the chunk on the next env-step. Keep the existing outer-loop check as the backstop. |
| Minor | [docs/architecture/decisions/ADR-007-algorithm-choice.md](../../docs/architecture/decisions/ADR-007-algorithm-choice.md#L51-L57) | Title and decision paragraph promise "Double + Dueling," but `_DQN_KWARGS` does not enable dueling and the ADR's own hedge admits SB3's stock `DQN` `MlpPolicy` doesn't expose it. Operator will read "dueling enabled" and grep the code for it | Either (a) amend the ADR title to "DQN (double, MLP [64,64])" and rewrite the dueling paragraph as "explicitly dropped for slice 3, see slice-3 wrap"; or (b) land a custom dueling-MLP policy class. (a) is the slice-3-scoped fix; (b) is a slice-3 deviation that should be its own commit. |
| Minor | [src/env.py](../../src/env.py#L21-L27), [scripts/eval.py](../../scripts/eval.py#L255) | `_observation_from_state` is leading-underscore (intent-private) but exported in `src/env.py::__all__` and imported by `scripts/eval.py`. The privacy convention and the export contradict each other | Drop the underscore: rename to `observation_from_state`. Update `__all__`, the eval.py import, and the test that asserts the private name. Done in one commit; trivially mechanical. |
| Minor | [scripts/train.py](../../scripts/train.py#L161-L162) | `subprocess.run(..., timeout=60 * 60)` — periodic-eval subprocess timeout is hardcoded to 1 hour. At 20 episodes × 300s `max-episode-seconds` cap (eval.py default), worst case is 100 minutes; cold Chrome launch + 20 cap-hitting episodes could legitimately exceed 60 min | Either (a) compute the timeout from `args.eval_episodes × eval_max_episode_seconds + startup_pad`; or (b) raise to `2 * 60 * 60` and document why. (a) is honest; (b) is the cheap fix. |
| Nit | [scripts/train.py](../../scripts/train.py#L60-L72), [scripts/eval.py](../../scripts/eval.py#L132-L139) | `_git_sha()` is duplicated across `scripts/train.py` and `scripts/eval.py`. Two divergent 5-line implementations today; the next caller will copy-paste a third | Extract to `scripts/_git.py` or `src/_git.py` and import from both. Borderline — the function is small enough that "rule of three" hasn't fired yet. Defer if the wrap is short on context. |

## Verdict

Review Verdict: needs-fixes
Critical Findings: 0
Major Findings: 1

The Major (wall-clock cap chunk-size guard) should be fixed before the operator launches the 4-hour training run — the cap as advertised is not the cap as enforced, and the slice-3 budget-floor exit branch in impl §3.6 was designed assuming the cap fires on time. The three Minor and one Nit are non-blocking and can be folded into either this slice or the slice-3 evidence wrap.

The slice-3 *evidence* half (training run, eval-mean trajectory, beat-baseline gate decision) is explicitly out of scope for this review and will be reviewed separately when the operator's run completes.

## Re-review (round 2)

**Date**: 2026-04-25
**Reviewer**: Copilot (reviewer mode)
**Scope**: Verify round-1 fixes for the Major + 3 Minors + 1 Nit.

### Verification

| Round-1 finding | Resolution | Verified |
|---|---|---|
| **Major** — wall-clock cap polled per-chunk (~83 min worst-case overrun) | New `_WallClockCallback(BaseCallback)` in [scripts/train.py](../../scripts/train.py#L139-L156) returns `False` from `_on_step` once `time.monotonic() >= deadline`. SB3's `OffPolicyAlgorithm.collect_rollouts` invokes the callback per env-step and exits the rollout on `False`, so the cap is now polled per env-step (~200ms granularity) instead of per chunk. The deadline is computed once as `wall_start + wall_cap_seconds` and a fresh callback is constructed per chunk with the same absolute deadline ([train.py L267-L276](../../scripts/train.py#L267-L276)). The outer-loop `wall_elapsed >= wall_cap_seconds` check is preserved as a backstop. The lazy `__new__` factory is unconventional but works (returns the inner `_Impl` instance, which IS-A `BaseCallback`) and keeps SB3 out of top-level imports — the `--help`-without-SB3 contract pinned by `test_main_callable_imports_cleanly` is preserved. | ✅ closed |
| **Minor** — ADR-007 title promised "dueling" but `_DQN_KWARGS` doesn't enable it | [ADR-007](../../docs/architecture/decisions/ADR-007-algorithm-choice.md) title is now "(Double-DQN, MLP `[64, 64]`)"; the Decision body explicitly records dueling was dropped because SB3's vanilla `DQN` MLP policy doesn't expose a dueling toggle without a custom policy class. Title↔code agreement holds. **However**: the *Alternatives Considered* section ([L139-L141](../../docs/architecture/decisions/ADR-007-algorithm-choice.md#L139-L141)) was not updated and still says "Plain DQN (no double, no dueling) — rejected because both extensions are zero-marginal-cost on top of vanilla DQN in SB3 (just different flags)." This now contradicts the Decision section. **NEW Minor — see "New finding" below.** | ⚠ partially closed (Decision section fixed, Alternatives section newly stale) |
| **Minor** — periodic-eval subprocess timeout 60min < worst-case 100min | [train.py L196-L199](../../scripts/train.py#L196-L199): `eval_timeout_s = max(30 * 60, eval_episodes * 360)`. At default `eval_episodes=20`: `max(1800, 7200) = 7200s = 2h`, exceeds worst-case ~100min. The 30-min floor protects edge cases (e.g. `eval_episodes=1` would otherwise yield 360s, possibly insufficient against cold Chrome + capped episode). Math correct. | ✅ closed |
| **Minor** — `_observation_from_state` leading-underscore but cross-imported | Deferred to [TD-009](../../docs/reference/tech-debt.md). Why-accepted cites real test-contract pinning ripples into `tests/test_env.py` (slice 2 deliberately pinned the underscored name). Resolution path is concrete. Acceptable defer. | ✅ deferred soundly |
| **Nit** — `_git_sha` duplicated | Deferred to [TD-010](../../docs/reference/tech-debt.md). Why-accepted notes the function has no tunable behavior so drift is unlikely, and abstracting is a larger architectural change than the duplication. Round-1 explicitly classed it as Nit. Acceptable defer. | ✅ deferred soundly |

### New finding (round-2-introduced)

| Severity | File | Finding | Recommendation |
|---|---|---|---|
| Minor | [docs/architecture/decisions/ADR-007-algorithm-choice.md](../../docs/architecture/decisions/ADR-007-algorithm-choice.md#L139-L141) | The Decision section now correctly records that dueling was dropped (and is *not* zero-marginal-cost — it requires a custom policy class). The *Alternatives Considered* section still claims "both extensions are zero-marginal-cost on top of vanilla DQN in SB3 (just different flags)." Internal contradiction; an operator skimming Alternatives will read "dueling is just a flag" and grep `_DQN_KWARGS` for the flag that doesn't exist | Rewrite the bullet so only double-DQN is described as zero-marginal-cost, and cross-reference the Decision section for why dueling was dropped. Concrete diff in the round-2 reviewer message. |

### Test + CLI verification

**Not verified in this re-review session** — the available tool surface in this session does not include a terminal-execution tool, so `python -m pytest tests/ -m "not browser" -q` and `python scripts/train.py --help` were not run. Based on the diffs:

- The `--help` path imports argparse only; no module-level SB3/Browser/DinoEnv import was added. `_WallClockCallback.__new__` does the SB3 import lazily inside `__new__`, so it only fires when an instance is constructed (which only happens inside the `main()` training loop, after argparse has accepted the args). The `test_main_callable_imports_cleanly` and `test_help_*` tests should still pass.
- The `eval_timeout_s` change is an internal computation; no API surface change.
- The `model.learn(callback=cap_callback, ...)` change is an additive kwarg.

The operator should run both checks before the 4h training launch to confirm. Expected: pytest 45 passed, 1 skipped, 2 deselected; `--help` exits 0 and lists `--total-steps`, `--eval-every`, `--ckpt-every`, `--max-wall-hours`.

### Verdict (round 2)

Review Verdict: pass
Critical Findings: 0
Major Findings: 0

The round-1 Major is closed cleanly (not silenced — the per-step polling is real and SB3 honors the `False` return). The round-1 Minor and Nit deferrals are sound. The newly-introduced ADR-007-Alternatives Minor is non-blocking by reviewer policy (zero Critical, zero Major → pass; Minor/Nit non-blocking) and can be folded into the slice-3 evidence wrap or fixed inline. Untested-by-this-reviewer items (pytest + `--help`) should be confirmed by the operator before the training launch.
