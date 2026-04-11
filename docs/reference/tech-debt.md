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

### TD-001: No action delay in training env

**Priority**: ~~High~~ → Resolved
**Introduced**: Phase 1 (initial env build)
**Resolution**: Added `action_delay` parameter to DinoEnv (ADR-001). Default training config uses `action_delay=1`.

### TD-002: Missing speed-dependent jump velocity

**Priority**: ~~High~~ → Resolved
**Introduced**: Phase 1 (initial env build)
**Resolution**: Jump velocity now uses `INITIAL_JUMP_VELOCITY + speed / 10.0` matching Chromium source (ADR-001).

### TD-003: Pterodactyl Y mapping bug in validate_browser.py

**Priority**: ~~Medium~~ → Resolved
**Introduced**: Browser validation script
**Resolution**: Fixed to use `ground_line = groundYPos + TREX_HEIGHT` for obstacle Y conversion (ADR-001).

### TD-004: clearTime 500ms vs Chrome's 3000ms

**Priority**: ~~Low~~ → Resolved
**Introduced**: Phase 1 (training iteration 2)
**Resolution**: `clear_time_ms` is now configurable. Training default remains 500ms for density (ADR-001).

### TD-005: No frame skip / action repeat

**Priority**: ~~High~~ → Resolved
**Introduced**: Phase 1
**Resolution**: Added `frame_skip` parameter to DinoEnv. Training default uses `frame_skip=2` (ADR-001).
