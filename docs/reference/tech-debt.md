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

