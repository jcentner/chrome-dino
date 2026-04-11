# ADR-001: Add action delay, frame skip, and speed-dependent jump to DinoEnv

## Status

Accepted

## Context

The v1 headless environment trained a PPO agent to mean score 2,247 but only achieved
mean 190 in real Chrome (8% transfer rate). Root cause analysis identified four
sources of sim-to-real divergence:

1. **Action latency**: trained with instant execution, deployed with 1-2 frame Selenium delay
2. **Constant jump height**: Chrome increases jump velocity with speed (+12-28%), our env didn't
3. **Observation Y mapping**: pterodactyl Y used wrong reference point in browser validation
4. **clearTime mismatch**: trained with 500ms, Chrome uses 3000ms

See `docs/reference/sim-to-real-analysis.md` for the full analysis.

## Decision

Add three configurable parameters to `DinoEnv`:

- **`action_delay`** (int, default 0): FIFO buffer that delays action execution by N frames.
  Pre-filled with noops on reset. Simulates Selenium round-trip latency.
- **`frame_skip`** (int, default 1): Each `env.step()` runs K internal game frames.
  First frame applies the action; remaining frames hold duck state or noop.
  Reward is summed across frames. Early termination returns immediately.
- **`clear_time_ms`** (float, default 500): Configurable obstacle-free window.

Additionally, jump velocity is now speed-dependent:
`trex_vy = INITIAL_JUMP_VELOCITY + speed / 10.0` (from Chromium `trex.ts:469`).

Observation velocity normalization updated to account for higher max velocity:
`obs[2] = clip(trex_vy / (INITIAL_JUMP_VELOCITY + MAX_SPEED / 10.0), -1, 1)`.

Training defaults: `action_delay=1, frame_skip=2, clear_time_ms=500`.

### endJump velocity cap (v3 addition)

Chrome applies a jump height limiter (`trex.ts:483-520`): once the dino rises above
`maxJumpHeight` (30 canvas px from top = 63px above ground in bottom-up coords),
`endJump()` caps upward velocity to `dropVelocity` (5.0). This prevents the dino
from reaching the full ballistic peak (~101px at speed 7), limiting it to ~87px.

Our env now implements this with two constants:
- **`MIN_JUMP_HEIGHT = 30`** — trex_y above which `reached_min_height` becomes True
- **`MAX_JUMP_HEIGHT = 63`** — trex_y above which upward velocity is capped to `DROP_VELOCITY`

Note: Chrome uses `Math.round()` on position updates; our float arithmetic gives
peak ~83 vs Chrome's ~87. The ~4px discrepancy is acceptable.

This was the root cause of v2's continued browser failure (mean=210): the model trained
with peak height 101 but Chrome only allows 87, so the dino hit cacti on descent.

## Consequences

- v1 defaults (`action_delay=0, frame_skip=1`) preserve backward compatibility
- Training with latency forces anticipatory rather than reactive policies
- Frame skip reduces effective decision rate to match browser ~30Hz
- Speed-dependent jump corrects height divergence at higher speeds
- Model must be retrained (v2) — existing v1 model was trained without these features
- Observation space bounds remain [-1, 1] with clipped velocity normalization
