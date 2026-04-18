# Slice 1 — Source-Code Review

**Phase**: 1 — Real-time browser-native agent to MET
**Slice**: 1 (browser adapter + heuristic + eval skeleton + schema)
**Scope**: source half only. Live-Chrome runtime install + 20-episode eval + AC-HARNESS manual count are out of scope (blocked on operator runtime install).
**Anchors**: `roadmap/phases/phase-1-design.md` §2/§5/§7-1, `roadmap/phases/phase-1-implementation.md` §3.4/§3.5/§3.7/§4/§6-1, `docs/architecture/decisions/ADR-005-validation-harness.md`, `docs/architecture/decisions/ADR-006-singleton-rule.md`, `docs/architecture/decisions/ADR-008-action-dispatch.md`.

## Files reviewed

- [src/__init__.py](../../src/__init__.py), [src/browser.py](../../src/browser.py), [src/heuristic.py](../../src/heuristic.py)
- [scripts/__init__.py](../../scripts/__init__.py), [scripts/eval.py](../../scripts/eval.py), [scripts/capture_fixtures.py](../../scripts/capture_fixtures.py)
- [tests/conftest.py](../../tests/conftest.py), [tests/test_browser.py](../../tests/test_browser.py), [tests/test_eval_artifact_schema.py](../../tests/test_eval_artifact_schema.py)
- [pytest.ini](../../pytest.ini), [requirements.txt](../../requirements.txt)
- ADR-001/002/005/006/008, [docs/setup/windows-chrome-pinning.md](../../docs/setup/windows-chrome-pinning.md), `chromedriver/.gitkeep`, `.gitignore`

## Findings count

| Severity | Count |
|----------|-------|
| Critical | 0 |
| Major    | 0 |
| Minor    | 4 |
| Nit      | 2 |

## Findings

| # | Severity | File:line | Finding | Recommendation | Status |
|---|----------|-----------|---------|----------------|--------|
| 1 | Minor | [scripts/eval.py:151-156](../../scripts/eval.py#L151-L156) | The "wait until playing" loop is dead — `for _ in range(20): if browser.is_game_over(): break; <unconditional> break` exits on the first iteration regardless. The intent (per the inline comment "Bounded polling. … re-press if it didn't take") is not implemented; the comment lies about the behavior. The downstream `while True` does pump on `state is None`, so this isn't broken in practice, just misleading dead code. | Either delete the loop entirely (it's redundant with the `state is None` retry below) or replace with a real `is_game_over`/`read_state is None`-poll-and-re-`reset_episode` retry. Update the comment to match. | open |
| 2 | Minor | [scripts/eval.py:158-187](../../scripts/eval.py#L158-L187) | `_run_one_episode` `while True` only exits on `state.crashed`. If `read_state` returns `None` indefinitely (page never loads, navigation failed silently, JS context destroyed) the loop spins on `time.sleep(0.005)` forever. Slice-1 manual run will hang rather than fail loudly. | Add a wall-clock cap (e.g. 5 minutes per episode, generous vs. the design plan's "free-run") and raise/return an error episode if exceeded. Optional: also cap consecutive `None`-reads (e.g. 200 → bail). | open |
| 3 | Minor | [src/browser.py:212-220](../../src/browser.py#L212-L220) | Held-key invariant has a small consistency gap: if `_dispatch_key(_KEYDOWN, _KEY_ARROW_DOWN)` raises during DUCK, `_arrow_down_held` is never set to `True`, so a subsequent non-DUCK action will not attempt to release. Mirror gap on `__exit__`: `_release_held_keys` swallows nothing, so a CDP failure on the keyup propagates and `driver.quit()` still runs (good — protected by `try/finally`), but the held-flag is reset in the inner `finally` regardless of whether the dispatch succeeded. The spec ("episode-ending transitions release all held keys") is met on the happy path; the failure path is best-effort. | Document the best-effort guarantee in the `Browser` docstring, or wrap `_dispatch_key` in `send_action`'s DUCK branch with a `try/except` that explicitly leaves `_arrow_down_held = False` on raise. Acceptable as-is for slice 1 — flag in tech debt if not fixed inline. | open |
| 4 | Minor | [scripts/eval.py:55-117](../../scripts/eval.py#L55-L117) | `validate_artifact` uses two rejection mechanisms inconsistently: top-level type and missing top-level keys *raise* `ArtifactValidationError`; everything else (extra top-level keys, metadata problems, episode problems) goes into `errors` and returns `{"valid": False, ...}`. The schema-extra-fields cases are silently downgraded to "non-success result" — fine for the test (`_is_rejection` accepts both), but two paths are easier to misuse downstream. Also: extra top-level keys (e.g. `summary`) are added to `errors` but no test pins this; the schema-is-exact contract is only test-pinned for episode fields. | Pick one mechanism (preferably "always return result, never raise" — easier for callers). At minimum, add a unit test covering the "extra top-level key" branch so the exact-schema contract for top-level is locked. Defer to slice 2 acceptable. | open |
| 5 | Nit | [scripts/eval.py:194-207](../../scripts/eval.py#L194-L207) | `_resolve_policy`'s final `raise SystemExit(f"unknown policy: {name!r}")` is unreachable because `argparse` enforces `choices=sorted(_VALID_POLICIES)` at parse time. | Drop the unreachable branch, or add a comment "// argparse-enforced; defensive only." Cosmetic. | open |
| 6 | Nit | [src/browser.py](../../src/browser.py), [scripts/eval.py](../../scripts/eval.py) | `# ----` section banners and verbose docstrings are slightly heavier than warranted for ~250-line files, but every comment carries information (anchors back to plan §3.5, ADR refs). On the AI-slop scale this is at the "polished" end, not the "bloated" end. No action required. | None. | n/a |

## Per-focus checklist

1. **AC-SINGLETON compliance** — `src/` has `browser.py` + `heuristic.py` (one browser interface, one fixed-policy). `scripts/` has `eval.py` + `capture_fixtures.py` (one eval entry point; capture-fixtures explicitly documented as a fixture utility per impl plan §4 / ADR-006). No env / train / learned-policy yet (correct — slices 2/3). **PASS.**
2. **§3.5 action-mapping invariant** — `send_action` releases held `ArrowDown` on every non-DUCK action; `reset_episode` releases-then-Space; `__exit__`/`close` release-then-quit; DUCK is idempotent (no double keyDown). **PASS** with the caveat in finding #3.
3. **CDP dispatch shape** — implementation calls `execute_cdp_cmd(_CDP_DISPATCH, params)` positionally; tests parse positional `args[0]/args[1]` first. Match is real, not accidental. **PASS.**
4. **Score readout formula** — `_GET_SCORE_JS` is `Math.floor(r.distanceRan * (r.config.COEFFICIENT || 0.025))`. Matches ADR-005 / AC-HARNESS. The mocked test would have passed against any int return, but the actual JS is correct. **PASS.**
5. **Artifact schema exactness** — episode extras rejected (`unexpected fields:` error). Metadata extras rejected. Top-level extras added to errors but not test-pinned (see finding #4). **PASS** with note.
6. **Reward / pacing / observation leakage** — `src/browser.py` returns the raw DOM dict from `_READ_STATE_JS`. No reward constants, no step-time constants, no Gym-shape conversion. Slice-1 stays out of slice-2/3 territory. **PASS.**
7. **Security** — `_git_sha` uses `subprocess.check_output(["git","rev-parse","HEAD"])` with a list and no `shell=True` (not injectable). No hardcoded credentials. `chrome_binary` is built from env var `CHROME_DINO_RUNTIME` and passed to selenium as `binary_location` (selenium spawns the binary directly, no shell). Acceptable for a single-developer Windows runtime; document the env-var-trust assumption if the project ever broadens. **PASS.**
8. **Doc/code consistency** — `src/browser.read_state` returns the raw dict; the 14-dim conversion is correctly absent. `scripts/capture_fixtures.py` dumps raw DOM dicts (`json.dump(state, ...)`), not Gym observations. Slice 1 does not pretend to deliver the slice-2 contract. **PASS.**
9. **Anti-slop** — see finding #1 (dead loop), finding #5 (unreachable branch). Otherwise comments are anchored to plan/ADR refs and earn their keep. **PASS** with notes.
10. **Unbounded loop** — finding #2. The `state.crashed` exit is meaningful in the happy path but the hang-on-`None` case is unguarded.
11. **Test coverage gaps** — `Browser.read_state`, `Browser.is_game_over`, `Browser.close` (non-CM path), and `_parse_chrome_major` have no direct unit test (covered implicitly by the skipped live test). `validate_artifact` has no test for non-dict input or missing top-level keys (the raising branch). All slice-2-deferable. Logged here; not blocking.

## Verdict

**Review Verdict: pass**
**Critical Findings: 0**
**Major Findings: 0**

Slice-1 source can land as-is. The four Minor findings are non-blocking and addressable in slice 2 or as small follow-ups (recommend at least addressing finding #1, since dead code with a misleading comment is a future-confusion hazard, and finding #2, since it's a genuine hang risk during the operator's manual eval). Findings #3 and #4 are acceptable as tech debt. Operator may proceed with the runtime install and the 20-episode heuristic baseline.

## Suggested follow-ups (non-blocking)

- Fix finding #1 (delete the dead "wait for playing" loop in `scripts/eval.py`) and finding #2 (add a wall-clock cap in `_run_one_episode`) before the operator runs the manual 20-episode eval. These two are the cheapest wins and the most likely to surface during the live run.
- Log findings #3 and #4 in [docs/reference/tech-debt.md](../../docs/reference/tech-debt.md) if not fixed inline.
- Slice 2 should add direct unit tests for `Browser.read_state`, `Browser.is_game_over`, `Browser.close`, and `_parse_chrome_major`, plus the `validate_artifact` non-dict / missing-top-level-key branches.
