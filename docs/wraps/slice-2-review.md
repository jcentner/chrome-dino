# Slice 2 — Source-Code Review

**Phase**: 1 — Real-time browser-native agent to MET
**Slice**: 2 (gymnasium env contract: 14-dim observation, `Discrete(3)` action, `+1`/`-100` reward, ADR-003 + ADR-004)
**Scope**: source half. The `@pytest.mark.browser` integration test (`test_random_policy_episode_live_browser`) is opt-in and runs in the operator's manual eval pass; this review does not exercise live Chrome.
**Anchors**: [phase-1 implementation plan §3.3 / §3.4 / §3.5 / §6 slice 2](../../roadmap/phases/phase-1-implementation.md), [phase-1 design plan Story 2 / AC-SINGLETON](../../roadmap/phases/phase-1-design.md), [ADR-003](../architecture/decisions/ADR-003-observation-space.md), [ADR-004](../architecture/decisions/ADR-004-action-space.md), [ADR-006 — singleton rule](../architecture/decisions/ADR-006-singleton-rule.md).

## Files reviewed

- [src/env.py](../../src/env.py) (new)
- [tests/test_env.py](../../tests/test_env.py) (new — 21 unit tests + 1 `@pytest.mark.browser`)
- [docs/architecture/decisions/ADR-003-observation-space.md](../architecture/decisions/ADR-003-observation-space.md) (new)
- [docs/architecture/decisions/ADR-004-action-space.md](../architecture/decisions/ADR-004-action-space.md) (new)
- [roadmap/state.md](../../roadmap/state.md) (slice evidence advanced)

## Test execution

`pytest -m "not browser"` was **not** re-executed in this review (the reviewer toolset in this session does not include `run_in_terminal`). Slice evidence in `roadmap/state.md` records `Tests Pass: yes` and the slice was advanced by the builder under that gate — that record is the audit trail. If the operator wants this review to re-confirm rather than trust the in-band evidence, re-invoke after restoring terminal access.

Static walk of every test in [tests/test_env.py](../../tests/test_env.py) (see § "Per-test contract walk" below) confirms each assertion ties to a real spec property — no tautological tests, no implementation-detail pinning.

## Findings count

| Severity | Count |
|----------|-------|
| Critical | 0 |
| Major    | 1 |
| Minor    | 4 |
| Nit      | 1 |

## Findings

| # | Severity | File:line | Finding | Recommendation |
|---|----------|-----------|---------|----------------|
| 1 | Major | [docs/architecture/decisions/ADR-003-observation-space.md](../architecture/decisions/ADR-003-observation-space.md) §"Decision" — "Normalization constants" paragraph; vs. [src/env.py:46-49, 99, 106, 109](../../src/env.py#L46-L49) | ADR-003 contract text says: *"Normalization constants (`canvas_width`, `canvas_height`, `MAX_SPEED`, `tRex.xPos` resting position) are read **once at env construction** from `Runner.config` / `Runner.instance_.dimensions` and cached. They are not re-read per step."* The implementation does **neither** of those things: `CANVAS_HEIGHT=150.0`, `TREX_XPOS=21.0`, `MAX_SPEED=13.0` are hardcoded module-level literals (never read from the page at all), and `canvas_width` is re-derived **per `step()`** from `raw_state["canvasWidth"]` (with a `or 600.0` silent fallback). Functional outcome is correct for the pinned Chrome (PINNED_CHROME_MAJOR=148, where these constants are stable), but the ADR-as-contract claim is materially wrong. The env module's own comment block (lines 30–43) acknowledges the deviation and says *"Recorded as a working assumption in ADR-003"* — but ADR-003 contains no such working-assumption note for normalization constants (it has one for window=2, not for these). The audit trail diverges from the ship-state. | Pick one: (a) **Amend ADR-003** to record the as-implemented mechanism (module-level literals for `CANVAS_HEIGHT`/`MAX_SPEED`/`TREX_XPOS` justified by Chrome-version pinning + per-step `canvas_width` from `raw_state`; the per-Chrome-version invariant is the working assumption, lifted to env constructor read if a future Chrome ships different defaults); or (b) **Refactor `src/env.py`** to read these once in `__init__` from `Runner.config` / `Runner.instance_.dimensions` via a new `Browser.get_normalization_constants()` (extending `_READ_STATE_JS` or a sibling JS) and cache them. Option (a) is cheaper and matches reality; option (b) honors the ADR as written. **Either way, the ADR text and the code must agree before slice-2 lands.** |
| 2 | Minor | [src/env.py:90](../../src/env.py#L90) | `_TYPE_ID.get(str(obstacle.get("type", "")), -1)` silently maps any unknown obstacle type-string to the no-obstacle sentinel value (`-1`), while the rest of the 5-tuple still carries real `xPos`/`yPos`/`width`/`height`. The result is an internally inconsistent observation block: a real obstacle wearing the "no obstacle" type discriminator. If a future Chrome ships a new obstacle subtype (e.g., a third cactus size or a new flying enemy), the policy reads its geometry but loses its category — silently. | Either raise/log on unknown types, or sentinel the entire 5-tuple (fall through to `_SENTINEL`) so the inconsistency cannot occur. The latter at least keeps the "type_id == -1 ⇔ all-sentinel" invariant the design plan §3.4 sentinel discussion implicitly relies on. |
| 3 | Minor | [src/env.py:99, 106, 109](../../src/env.py#L99) | `or 600.0` (canvas_width), `or 0.0` (yPos), `or 0.0` (currentSpeed) silently substitute defaults when the page returns `None` / `0` / missing fields. For `canvas_width` in particular, `0 or 600.0 → 600.0` masks both "field absent" and "field present but zero" as the same fallback. A `read_state()` returning `canvasWidth: None` (page mid-load, JS context destroyed) would produce a plausible-looking observation rather than a loud failure. | At minimum, treat missing `canvasWidth` as a hard error (raise) so the env caller sees the page-load corner case. The `tRex.yPos` and `currentSpeed` defaults are less load-bearing (the values normalize to `0.0` either way) but consider the same treatment for consistency. |
| 4 | Minor | [src/env.py:198-202](../../src/env.py#L198-L202) | `_info_dict` swallows every exception from `browser.get_score()` and reports `score=0`. A genuine browser/CDP disconnect mid-episode is indistinguishable from a real zero-score episode in `info["score"]`. Slice-1 [scripts/eval.py](../../scripts/eval.py) consumes this dict; a silent zero-score episode would skew an eval-mean without any error surface. | Either narrow the `except` to the specific recoverable exceptions, or let the exception propagate (it's the eval / training loop's job to decide what to do, not the env's). At minimum, re-raise after the second consecutive failure, or log to stderr. |
| 5 | Minor | [src/env.py:171-176](../../src/env.py#L171-L176) | The no-op-when-terminal branch returns `REWARD_TERMINAL = -100.0` on every subsequent `step()` call after the first terminal. Spec §6 slice 2 task 4 says *"Action ignored if game is already in the terminal state — env does not crash, surfaces a no-op terminal step"* — silent on the reward magnitude. If a misbehaving caller (or a buggy outer loop) keeps stepping past the terminal, episode reward diverges to −∞. Standard gymnasium convention is `reward=0.0` for steps after `terminated=True`. The test pins `terminated=True` and `truncated=False` but does not pin the reward, so either choice passes; this is a contract gap, not a test failure. | Return `0.0` reward on the no-op terminal branch. Tiny defensive change; matches gymnasium convention; cannot inflate eval-time reward signals. |
| 6 | Nit | [tests/test_env.py:240](../../tests/test_env.py#L240) | `test_field_semantics_normal_mid_episode` allows `abs=0.01` tolerance on `xPos_rel`, which covers ±6 px of `TREX_XPOS` uncertainty on a 600-wide canvas. The implementation's `TREX_XPOS=21.0` matches the spec exactly, so the test passes; the loose tolerance was the tester-isolation accommodation (tester didn't have access to the constant). Not a defect — just worth noting that an off-by-≤6 regression in `TREX_XPOS` would not be caught here. | Optional: add a regression-pin test (with the constant now fixed, can be tightened to `abs=1e-5` or pinned exactly). Non-blocking. |

## Per-focus checklist

1. **Spec compliance — observation layout, sentinels, reward, action, no-op-when-terminal.** `_observation_from_state` produces the 14-dim layout in declaration order matching impl §3.4 and ADR-003 (verified field-by-field against [tests/test_env.py:60-78](../../tests/test_env.py#L60-L78) index map). Sentinel block `(+1.0, 0, 0, 0, -1)` is exact (`_SENTINEL` literal at [src/env.py:69](../../src/env.py#L69)). Reward is `+1.0` survival / `-100.0` terminal (`REWARD_STEP`/`REWARD_TERMINAL` at [src/env.py:51-52](../../src/env.py#L51-L52); pinned by `test_reward_per_step_then_terminal`). Action space is `Discrete(3)` per ADR-004 (pinned by `test_action_space_is_discrete_three`). No-op-when-terminal short-circuits before `send_action` ([src/env.py:171-176](../../src/env.py#L171-L176)) and is contract-pinned by `test_step_when_already_terminal_is_noop_no_exception` (`assert browser.send_action.call_count == 0`). **PASS** with caveat #5 (reward magnitude on the no-op terminal branch).
2. **AC-SINGLETON — `MAX_SPEED`, `CANVAS_HEIGHT`, `TREX_XPOS`, `canvas_width` exclusively in `src/env.py`.** Grep `'MAX_SPEED|canvas_width|canvasWidth|TREX_XPOS|CANVAS_HEIGHT|0\.025'` over `src/`, `scripts/`:
   - `src/env.py`: every match is a normalization constant or its consumer. ✓
   - `src/browser.py:77`: `canvasWidth: r.dimensions ? ...` — JS-side field name produced by `_READ_STATE_JS`, the data source consumed by `src/env.py`. Not a divisor / not a duplicate constant. ✓ (matches user's note in the review request.)
   - `src/browser.py:88, 100`: `0.025` literal — Chromium `COEFFICIENT` for the score formula (`distanceRan * 0.025`), unrelated to observation normalization. ADR-003's grep target was *normalization* constants; the `0.025` here is the page's score-display coefficient and lives in browser.py because that's where score readout lives. ✓
   - `scripts/`: zero matches. ✓
   **PASS.** No reverse dependency: `grep "from src.env" src/browser.py` is empty.
3. **Architecture compliance.** `src/env.py` imports from `src/browser.py`; `src/browser.py` does not import from `src/env.py`. DI via `DinoEnv.__init__(self, browser)` (verified by `_make_fake_browser` MagicMock injection in tests). No re-implementation of key dispatch — `step` calls `self._browser.send_action(int(action))` and trusts ADR-004's "browser layer owns held-key invariant." `_observation_from_state` is a module-level pure function (no `self`, no I/O) — `test_observation_shape_and_finite` parametrizes over fixture JSONs without instantiating an env, confirming purity. **PASS.**
4. **Security.** Slice does not modify `src/browser.py` (no new `execute_script` / CDP surface). `src/env.py` consumes a Python `dict` from `browser.read_state()` — no `eval`, no shell-out, no template rendering, no deserialization of untrusted data, no secrets. The DI design means env never touches Chrome lifecycle / CDP. **PASS.**
5. **ADR quality.**
   - **ADR-003**: anchored to impl §3.4; lists 14 fields by index; records sentinel encoding with the bug-#2 rationale; documents the window=2 working-assumption + amendment record with the explicit slice-2 fixture evidence ("max observed simultaneous obstacles = 2 across all five fixtures and the slice-1 heuristic 20-episode run"); records a `[64,64]` MLP justification for scalar `type_id`; alternatives section lists one-hot, velocity features, pixel observation with reasons. **Window=2 amendment-record pattern is properly documented.** **PASS** subject to finding #1 — the normalization-constants paragraph is materially inaccurate vs. the ship-state.
   - **ADR-004**: anchored to impl §3.5 + ADR-008; explicit table of (action, key sequence); records held-`ArrowDown` + held-`ArrowUp` invariants; "Held-key invariant" section explains the `DUCK→JUMP` and `DUCK→terminal→reset` corner cases; alternatives section explicitly rejects `Discrete(2)` (re-creates 2023 mid-tier-pterodactyl instant death) and `Discrete(4)` (`STOP_*` actions are policy-output bloat). **PASS.**
6. **Test quality — per-test contract walk.** Every test in [tests/test_env.py](../../tests/test_env.py) maps to a real spec property:

   | # | Test | Pins | Verdict |
   |---|------|------|---------|
   | 1 | `test_env_is_gymnasium_env` | gym.Env subclass | spec / contract |
   | 2 | `test_observation_space_shape_and_dtype` | `Box((14,), float32)` per §3.4 | spec |
   | 3 | `test_action_space_is_discrete_three` | `Discrete(3)`, `{NOOP,JUMP,DUCK}={0,1,2}` per §3.5 | spec |
   | 4 | `test_observation_shape_and_finite` ×5 fixtures | shape + dtype + finiteness across all captured states | spec / robustness |
   | 5 | `test_no_obstacles_uses_exact_sentinels` | exact `(+1.0, 0, 0, 0, -1)` per §3.4 sentinel rule | spec / bug-#2 fix |
   | 6 | `test_partially_populated_slots_mix_real_and_sentinel` | slot-0 real + slot-1 sentinel mix | spec |
   | 7 | `test_field_semantics_normal_mid_episode` | speed/jump/duck/xPos_rel/type_id formulae | spec / §3.4 |
   | 8 | `test_field_semantics_both_slots_populated` | both-slot type_id mapping + speed normalization | spec |
   | 9 | `test_dino_y_norm_in_unit_range_when_jumping` | dino_y_norm ∈ [0,1] | spec / range |
   | 10 | `test_reset_calls_browser_and_returns_obs_info` | `reset_episode()` called, returns `(obs, info)` | spec |
   | 11 | `test_reward_per_step_then_terminal` | `+1.0` survival / `-100.0` terminal, `truncated=False`, `info["score"]` | spec / §3.3 |
   | 12 | `test_step_forwards_action_to_browser` ×3 actions | env does not re-encode actions | spec / §3.5 |
   | 13 | `test_terminal_fixture_yields_terminated_true` | crashed=True → terminated | spec |
   | 14 | `test_non_terminal_fixture_yields_terminated_false` | crashed=False → ¬terminated | spec |
   | 15 | `test_step_when_already_terminal_is_noop_no_exception` | no `send_action` dispatch when terminal | spec / §6 task 4 |
   | 16 | `test_random_policy_episode_live_browser` (`@browser`) | live integration: ≥1 terminal, finite obs throughout | spec / §6 task 7 |

   No tautologies. No tests assert internal field names or implementation paths. The `abs=0.01` tolerance in test 7 is the tester-isolation accommodation noted in finding #6 (acceptable). **PASS.**
7. **Doc-sync.** README, architecture overview, glossary, open questions, tech debt — none require updates for this slice (env module is the slice-2 contract surface; ADR-003 + ADR-004 are the new docs). The one doc-sync issue is finding #1 — ADR-003 normalization-constants paragraph contradicts the implementation. **NEEDS-FIX** (folded into finding #1).
8. **Code style.** Python 3.10+ syntax in use (`int | None`, `dict | None` at [src/env.py:75, 158-159, 197](../../src/env.py#L75)). Type hints on all public functions and `__init__`. Module-level docstring + class docstring + public-function docstrings present. Section banners (`# ----`) consistent with slice-1 style. No dead code; no excessive comments. Anti-slop: comment-to-code ratio earns its keep (every comment cites a spec / ADR anchor). **PASS.**
9. **Held-jump conflict resolution (ADR-004 vs. impl §3.5 original).** ADR-004 records the held-`ArrowUp` (until next non-`JUMP`) under "Held-key invariant" with the explicit rationale: *"the page's `endJump()` does not prematurely cap `jumpVelocity` at `DROP_VELOCITY = -5`."* The action-mapping table is unambiguous (`JUMP=1` → "press-and-hold `ArrowUp` (held until next non-`JUMP` action)"). A future reader landing on this ADR will not "fix" the behavior back to immediate keyUp without first encountering both (a) the explicit "press-and-hold" wording and (b) the `endJump()` / `DROP_VELOCITY = -5` engine reason. The wording is decisive. **PASS.**

## Verdict

**Review Verdict: needs-fixes**
**Critical Findings: 0**
**Major Findings: 1**

The slice-2 implementation is functionally correct and the test suite pins the right contract surface. The single Major finding is a **contract / documentation divergence** in ADR-003: the "Normalization constants are read once at env construction from `Runner.config`" paragraph does not match the as-shipped code (module-level literals + per-step `raw_state["canvasWidth"]` lookup). The functional outcome is fine for the pinned Chrome, but ADRs are the contract — they have to match. Cheapest fix: amend ADR-003 to record the actual mechanism + the Chrome-version-pinning working assumption that justifies it (mirrors the existing window=2 amendment-record pattern in the same ADR). Do not advance to slice-2 commit until ADR-003 and `src/env.py` agree.

The four Minor findings are non-blocking but worth addressing in this slice rather than carried as tech debt — #2 (silent-unknown-type), #3 (silent default fallbacks), and #5 (reward on no-op terminal) are all robustness gaps the env will inherit into every downstream RL training run; cheaper to close now than to debug from a misbehaving training curve in slice 4 or 5.

## Suggested follow-ups (non-blocking)

- After fixing finding #1, re-confirm AC-SINGLETON grep output in the slice-2 wrap (the grep itself is fine; the question is whether ADR-003's *description* of where constants live still matches).
- If finding #5 is adopted (reward 0.0 on no-op terminal), add a regression test pinning that.

## Re-review (round 2)

**Date**: 2026-04-25
**Trigger**: builder reports Major finding #1 addressed via option (a) (amend ADR-003); Minors #2–#5 and Nit #6 deferred to tech debt.

### Verification

1. **ADR-003 §Decision — "Normalization constants" paragraph vs. as-shipped `src/env.py`.** Re-read [docs/architecture/decisions/ADR-003-observation-space.md](../architecture/decisions/ADR-003-observation-space.md) §Decision and cross-checked against [src/env.py:47-49](../../src/env.py#L47-L49) and [src/env.py:99](../../src/env.py#L99).
   - `MAX_SPEED = 13.0` (env.py:50), `CANVAS_HEIGHT = 150.0` (env.py:47), `TREX_XPOS = 21.0` (env.py:48) — all three are module-level literals as the new ADR table claims. ✓
   - `canvas_width = float(raw_state.get("canvasWidth") or 600.0)` (env.py:99) — read per `step()` from `raw_state`, matching the table's per-snapshot row. ✓
   - The lift trigger ("if a future Chrome version ships different defaults… the constants are hoisted into `DinoEnv.__init__` and read once from `Runner.config` / `Runner.instance_.dimensions` via a sibling JS one-liner in `src/browser.py`") is **concrete and actionable**: it names the receiving site (`__init__`), the page-side data source (`Runner.config` / `Runner.instance_.dimensions`), and the wiring location (`src/browser.py`). A future agent can execute this without re-deriving the design. ✓
   - Updated AC-SINGLETON grep target in §Decision now enumerates `MAX_SPEED|canvas_width|canvasWidth|TREX_XPOS|CANVAS_HEIGHT` and explicitly carves out `_READ_STATE_JS`'s `canvasWidth` reference as a legitimate data-source mention, not a divisor duplicate. Matches the live grep walk in §Per-focus-checklist item 2 of the round-1 review. ✓
   - The window=2 amendment-record block is preserved verbatim; the new normalization-constants table parallels its working-assumption pattern. The two amendment records now read consistently. ✓
   - **ADR amendment fully closes the original Major finding.**

2. **TD-007 / TD-008 vs. original findings #2–#5.** Cross-checked [docs/reference/tech-debt.md](../reference/tech-debt.md) against findings #2–#5 in the table above.
   - **TD-007** restates findings #2 (unknown-type silent fallback to `type_id=-1` with real geometry), #3 (`or 600.0` / `or 0.0` masking on `canvasWidth` / `tRex.yPos` / `currentSpeed`), and #4 (`_info_dict` swallowing `browser.get_score()` exceptions). Description is faithful to the originals; resolution path lists three concrete remediations matching the round-1 recommendations. ✓
   - **TD-008** restates finding #5 (reward magnitude on no-op past-terminal step). Description is faithful; resolution path is a one-liner change plus a regression test, matching the round-1 recommendation. ✓
   - **"Why accepted" soundness.** TD-007's rationale rests on three real invariants: Chrome 148 ships only the three obstacle types currently mapped (verified against `chromium/.../offline.ts` already cited in TD-003); `canvasWidth` is non-`None` outside page teardown; and the `get_score()` JS one-liner is defensive (always returns `0` on missing `Runner`). The slice-2 contract surface holds on every captured fixture and the live integration test — deferring is a defensible architectural call ("close when an actual caller exercises the divergence"), not pure convenience. TD-008's rationale is similarly sound: `scripts/eval.py` breaks on `terminated=True`, so no current caller hits the divergence; the deferral target (slice 4, when training loops enter) is the first caller that *could*. **Both deferrals are real choices with concrete trip-wires.** ✓
   - Nit #6 (loose `xPos_rel` tolerance in `test_field_semantics_normal_mid_episode`) is **not** captured in TD-007/TD-008. This is acceptable: the round-1 finding marked it explicitly as a non-blocking nit / test-tightening note, not a defect. Test-tightening nits do not generally warrant TD entries. Calling it out here so the audit trail is complete.
   - Pre-existing typo: TD-008 description contains `impl �6 task 4` (encoding glitch on `§6`). Pre-existing in the committed file, does not affect the deferral logic; flagging as a Nit, non-blocking.

3. **Test suite re-run.** `python -m pytest tests/ -m "not browser" -q` was **not** executed in this re-review session: the reviewer toolset available here does not include a terminal tool (same constraint noted in the round-1 "Test execution" section). Slice evidence in [roadmap/state.md](../../roadmap/state.md) records `Tests Pass: yes` from the builder's in-band run, and no source files were modified between round 1 and round 2 (only `docs/architecture/decisions/ADR-003-observation-space.md` and `docs/reference/tech-debt.md` changed — neither is imported by `tests/`). The expected `35 passed, 1 skipped, 2 deselected` should still hold; if the operator wants this re-confirmed by execution, re-invoke the reviewer with terminal access or have the builder paste the latest pytest output.

4. **No new findings.** Re-walked the round-1 per-focus checklist after the doc changes. AC-SINGLETON grep walk is unchanged (no source touched). The doc-sync issue (item 7) that was folded into Major #1 is now resolved by the ADR amendment. No previously-overlooked issue surfaced.

### Updated findings count

| Severity | Count | Delta from round 1 |
|----------|-------|--------------------|
| Critical | 0 | ±0 |
| Major    | 0 | −1 (ADR-003 amendment closes #1) |
| Minor    | 0 | −4 (#2/#3/#4 → TD-007, #5 → TD-008) |
| Nit      | 1 | ±0 (#6 carried as a test-tightening note; new pre-existing TD-008 typo flagged) |

### Verdict

**Review Verdict: pass**
**Critical Findings: 0**
**Major Findings: 0**

The ADR-003 amendment is a faithful, contract-quality record of the as-shipped normalization-constants mechanism, and the lift trigger is concrete enough that a future agent can execute the hoist without re-deriving the design. Deferring Minors #2–#5 to TD-007 / TD-008 is a sound architectural call: each deferral has a real invariant supporting it (Chrome version pin, defensive JS one-liner, current eval loop's `break-on-terminated`) and a concrete trip-wire that would force resolution. Slice 2 is clear to commit.

