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

**Priority**: High
**Introduced**: Phase 1 (initial env build)
**Description**: The headless env executes actions instantly within the same frame. Real-world deployment via Selenium has 1-2 frame action delay. The trained policy assumes frame-perfect execution.
**Why accepted**: Wasn't discovered until browser validation revealed 8% transfer ratio.
**Resolution path**: Add configurable action delay buffer to `DinoEnv`. Default to 1-2 frames.

### TD-002: Missing speed-dependent jump velocity

**Priority**: High
**Introduced**: Phase 1 (initial env build)
**Description**: Chrome's `jumpVelocity = initialJumpVelocity - (speed / 10)` makes jumps 12-28% higher as speed increases. Our env uses constant jump velocity. Agent timing breaks at high speeds.
**Why accepted**: The constant was read from `normalJumpConfig.initialJumpVelocity = -10`, missing the speed adjustment in `startJump()`.
**Resolution path**: Change jump start in env.py: `self.trex_vy = INITIAL_JUMP_VELOCITY + self.speed / 10`.

### TD-003: Pterodactyl Y mapping bug in validate_browser.py

**Priority**: Medium
**Introduced**: Browser validation script
**Description**: Uses `groundYPos` (93) instead of `ground_line` (140) for obstacle Y conversion. All pterodactyl heights map to 0 instead of their actual elevation.
**Why accepted**: Not caught because initial testing only encountered cacti (pterodactyls appear at speed 8.5+, agent dies at speed 7).
**Resolution path**: `ground_line = ground_y + 47` in `game_state_to_obs()`.

### TD-004: clearTime 500ms vs Chrome's 3000ms

**Priority**: Low
**Introduced**: Phase 1 (training iteration 2 — reduced for denser signal)
**Description**: Training uses 500ms clear time, Chrome uses 3000ms. Agent encounters obstacles at slightly different speeds than in Chrome.
**Why accepted**: Intentional for training efficiency. Minor impact on transfer.
**Resolution path**: Make clearTime configurable. Use 3000ms for evaluation/validation.

### TD-005: No frame skip / action repeat

**Priority**: High
**Introduced**: Phase 1
**Description**: Each env step = 1 game frame. Browser deployment operates at ~30Hz with 60fps game = 2 game frames per action. Agent was never trained for multi-frame action persistence.
**Why accepted**: Standard env design. The mismatch wasn't obvious until browser testing.
**Resolution path**: Add frame_skip parameter to DinoEnv. Train with frame_skip=2-3.
