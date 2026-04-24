# chrome-dino — Tech Debt Tracker

Known compromises, shortcuts, and deferred improvements. Each item should have a reason it was accepted and a rough priority for resolution.

## Format

```
### TD-NNN: Title

**Priority**: High / Medium / Low
**Introduced**: Phase/session where this was introduced
**Description**: What the shortcut is.
**Why accepted**: Why this was OK for now.
**Resolution path**: What it would take to fix properly.
```

## Tech Debt Items

<!-- Add items as shortcuts are taken. The autonomous builder records tech debt here. -->

### TD-001: `Browser` held-key invariant is best-effort under CDP failure

**Priority**: Low
**Introduced**: Phase 1, slice 1 (reviewer finding #3)
**Description**: `src/browser.py::Browser.send_action` and `_release_held_keys` set `_arrow_down_held = False` only when the CDP `keyUp` dispatch succeeds (or in the inner `finally`). If `_dispatch_key(keyDown, ArrowDown)` raises during a DUCK action, `_arrow_down_held` is never set to `True`, so a subsequent non-DUCK action will not attempt to release a key the page may or may not actually have received. The §3.5 invariant ("episode-ending transitions release all held keys") is met on the happy path; the failure path is best-effort.
**Why accepted**: CDP dispatch failures are rare (driver-disconnect-class events) and a disconnected browser is unrecoverable for the current episode anyway. The blast radius is one stuck modifier key on the next episode at worst, recoverable by `reset_episode()` (which now always dispatches `keyUp ArrowDown` if the held flag is True).
**Resolution path**: wrap each `_dispatch_key` call in `send_action`'s DUCK branch with `try/except` that sets `_arrow_down_held` based on whether the dispatch raised; or escalate dispatch failures to an exception that tears the browser down rather than continuing.

### TD-002: `validate_artifact` mixes raise vs. return-with-errors

**Priority**: Low
**Introduced**: Phase 1, slice 1 (reviewer finding #4)
**Description**: `scripts/eval.py::validate_artifact` raises `ArtifactValidationError` on top-level type / missing-top-level-key violations, and returns `{"valid": False, "errors": [...]}` on everything else (extra top-level keys, metadata problems, episode field problems). Tests accept either rejection mechanism, but the dual-path API is easier to misuse downstream.
**Why accepted**: The slice-1 test contract pins behaviour ("rejection happens"), not mechanism. The eval loop itself raises on `valid: False`, so callers in this repo see a uniform raise-on-bad-artifact contract. A future caller that calls `validate_artifact` directly could be surprised.
**Resolution path**: pick one mechanism (preferably "always return result, never raise") and add a unit test pinning the "extra top-level key" branch so the exact-schema contract for top-level is locked.

### TD-003: `src/heuristic.py` baseline far weaker than design assumed

**Priority**: HIGH — affects AC-STOP-GATE binding constraint
**Introduced**: Phase 1, slice 1 (measured against live Chrome 148.0.7778.56)
**Description**: The frozen heuristic was authored "by inspection from the 2018 implementation" and was never empirically tested before being baked into the design plan as the slice-3 baseline. Measured 20-episode mean = **48.3** (min 48, max 52) — versus the design plan's "~1500" assumption. Cause: the speed-adaptive jump threshold (`60 + 12 * speed`) fires too **early** at current speeds; the dino reaches its jump apex while the cactus is still ~70 px away, then is on the descending side of the arc by the time the cactus passes the dino's x-position, landing on the cactus's tail. Heuristic also never sees a pterodactyl (crashes on first cactus), so the duck branch is untested in live runtime.
**Why accepted (for slice 1)**: AC-SINGLETON freezes the heuristic for phase 1. Phase 1 cannot retune it without breaking the singleton constraint. The number is the number — slice 3 will train against this baseline.
**Critical downstream effect**: VISION-LOCK v1.1.0 binding-constraint 2 requires `(≥+10% relative AND ≥+50 absolute)` improvement to clear AC-STOP-GATE. Against baseline=48, the absolute gate of +50 means score 98 — trivially achievable by *any* policy that jumps once. The stop-gate provides essentially **no signal** with this baseline. This needs explicit human attention before slice 3 commits training time.
**Resolution path**: human decision required between (a) accept the weak baseline and tighten AC-STOP-GATE numerics in a v1.2.0 vision-lock amendment; (b) replace the heuristic baseline with a stronger frozen reference (would require a vision/AC amendment because it changes AC-SINGLETON's "single fixed-policy" identity); (c) accept that slice 3 will trivially clear the gate and let the MET = 2000 mean-score gate carry the real evaluation weight. Surface to user at end of slice 1.

### TD-004: `scripts/capture_fixtures.py` only captures 5/7 scenarios live

**Priority**: Low (slice 2 will redo)
**Introduced**: Phase 1, slice 1
**Description**: With the frozen heuristic crashing on the first cactus (~score 48), the `mid_duck` and `near_crash` fixture scenarios cannot be reached in real gameplay. Only 5 of 7 target labels are captured: `no_obstacles`, `mid_jump`, `normal_mid_episode`, `both_obstacle_slots_populated`, `terminal`.
**Why accepted**: Slice-2 work (env contract) needs fixtures of every scenario, but slice 2 will inevitably re-drive trajectories with finer control — easier to capture the remaining two there than to hand-craft them now.
**Resolution path**: in slice 2, run capture with a manual driver (forced JUMP/DUCK schedule) to hit `mid_duck` and `near_crash`.

