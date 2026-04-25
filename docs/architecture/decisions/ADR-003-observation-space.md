# ADR-003 — Observation feature vector

**Date**: 2026-04-25
**Status**: Accepted (window=2 working assumption; verified-or-amended in slice 2; amendment record below)
**Phase**: 1 (introduced in slice 2)
**Anchors**: [phase-1 implementation plan § 3.4](../../../roadmap/phases/phase-1-implementation.md), [phase-1 design plan § Story 2 / AC-SINGLETON](../../../roadmap/phases/phase-1-design.md)

## Context

The slice-1 post-mortem of the 2018 / 2023 implementations identified two
observation-pipeline failures the env contract must explicitly answer:

1. **Sentinel collision** — the v1 observation used `0.0` to mean both "no
   obstacle in this slot" and "obstacle at the dino's exact position." The
   network had no way to distinguish "all clear" from "imminent collision."
2. **Scattered normalization constants** — `MAX_SPEED`, `canvas_width`, and
   per-feature divisors lived in three different files. Changing one without
   the others silently skewed the observation distribution.

The env runs against the live, unmodified Chromium dino game (vision lock).
The page exposes its state via the `Runner` singleton; observation is read
in a single `driver.execute_script` round-trip per `step()` (latency budget
established in slice 1).

## Decision

**14-dim float32 vector**, exactly as enumerated in
[phase-1 implementation plan § 3.4](../../../roadmap/phases/phase-1-implementation.md):

| Index | Field | Source (JS path) |
|---|---|---|
| 0 | `dino_y_norm` | `Runner.instance_.tRex.yPos / canvas_height` |
| 1 | `dino_jumping` | `Runner.instance_.tRex.jumping` (0/1) |
| 2 | `dino_ducking` | `Runner.instance_.tRex.ducking` (0/1) |
| 3 | `current_speed_norm` | `Runner.instance_.currentSpeed / Runner.config.MAX_SPEED` |
| 4 | obstacle[0] `xPos_rel` | `(obstacle.xPos - tRex.xPos) / canvas_width` |
| 5 | obstacle[0] `yPos_norm` | `obstacle.yPos / canvas_height` |
| 6 | obstacle[0] `width_norm` | `obstacle.width / canvas_width` |
| 7 | obstacle[0] `height_norm` | `obstacle.typeConfig.height / canvas_height` |
| 8 | obstacle[0] `type_id` | scalar in `{-1, 0, 1, 2}` (no-obstacle, CACTUS_SMALL, CACTUS_LARGE, PTERODACTYL) |
| 9–13 | obstacle[1] same 5 fields | `Runner.instance_.horizon.obstacles[1]` |

**`type_id` is a scalar, not one-hot.** Justification recorded in
implementation-plan §3.4: 4 distinct values × `[64, 64]` MLP = no measurable
gain from one-hot encoding, and the scalar form keeps the no-obstacle
sentinel `-1` in the same field as real types.

**Sentinel for missing obstacle** (post-mortem bug #2 fix): when
`obstacles[i]` is undefined, the five obstacle fields take the *explicit*
values

```
xPos_rel  = +1.0   (off-screen-right)
yPos_norm =  0.0
width_norm = 0.0
height_norm = 0.0
type_id   = -1     (categorically distinct from real types 0/1/2)
```

`type_id == -1` is the discriminator — `xPos_rel == 0.0` is no longer
overloaded.

**Normalization constants** all live exclusively in `src/env.py`
(AC-SINGLETON: `grep -rn 'MAX_SPEED\|canvas_width\|canvasWidth\|TREX_XPOS\|CANVAS_HEIGHT' src/ scripts/`
at slice review must show no normalization-divisor duplicates outside
`src/env.py`; `_READ_STATE_JS` in `src/browser.py` legitimately references
the JS field name `canvasWidth` as the data source). The mechanism by
which they reach `src/env.py` differs per constant — the as-shipped
slice-2 mechanism is recorded below as a working assumption, parallel to
the window=2 amendment-record pattern below:

| Constant | Value | Source mechanism (slice 2) | Working assumption |
|---|---|---|---|
| `MAX_SPEED` | `13.0` | Module-level literal in `src/env.py` | Chromium `Runner.config.MAX_SPEED` is stable for the pinned Chrome major (`PINNED_CHROME_MAJOR=148`, ADR-008) |
| `CANVAS_HEIGHT` | `150.0` | Module-level literal in `src/env.py` | Chromium `Runner.defaultDimensions.HEIGHT` is stable for the pinned Chrome major; the page does not vary canvas height across episodes |
| `TREX_XPOS` | `21.0` | Module-level literal in `src/env.py` | Chromium `Trex.config.START_X_POS` is stable for the pinned Chrome major; the dino does not change resting xPos within an episode |
| `canvas_width` | per-snapshot | Read from `raw_state["canvasWidth"]` per `step()` (the page exposes it on every read; cheaper than caching + invalidating on resize) | None — value is genuinely per-snapshot |

**Slice-2 working assumption (lift trigger)**: if a future Chrome version
ships different defaults for `MAX_SPEED`, canvas height, or `tRex.xPos`,
the constants are hoisted into `DinoEnv.__init__` and read once from
`Runner.config` / `Runner.instance_.dimensions` via a sibling JS one-liner
in `src/browser.py`. This ADR is then amended to record the lift in the
same row format above. Until that trigger fires, the literals are the
source of truth and the audit trail is the pinned Chrome major + this
ADR row.

**Obstacle ordering**: by `xPos` ascending after filtering past-dino
obstacles (the page already sorts this way; env preserves the order).

## Window-width amendment record (slice 2)

**Working assumption**: window = 2 (`obstacles[0]` and `obstacles[1]` only,
total dim = 4 + 5×2 = 14). The slice-2 fixture-capture exercise and the
slice-2 random-policy `@pytest.mark.browser` integration test record, for
each observed `obstacles` array, how many simultaneous obstacles the page
surfaces within the planning horizon.

**Slice-2 evidence (this commit)**: across the five captured fixtures
(`no_obstacles.json`, `mid_jump.json`, `normal_mid_episode.json`,
`both_obstacle_slots_populated.json`, `terminal.json`) and the heuristic
20-episode run from slice 1, the maximum observed simultaneous obstacles
within the planning horizon at game speeds up to ≈ 6.5 (the speed range
slice-1 reaches) is **2**. The fixture
`both_obstacle_slots_populated.json` is the worst case observed.

**Decision**: window = 2 is locked at 14 dims for slice 2. If slice-3 / 4
training reaches MET-relevant speeds (speed ≥ 9–10) and observes ≥ 3
simultaneous obstacles within the planning horizon, this ADR is amended to
window = 3 (dim = 19) with the slice-N fixture as supporting evidence.

## Consequences

- Any code reading the observation must use the 14-dim layout above; index
  positions are part of the contract.
- Any change to a normalization constant or the addition of a new feature
  field is an ADR-003 amendment, not a silent edit.
- The env owns observation construction; `scripts/train.py` and
  `scripts/eval.py` import the env and consume `obs`, never construct
  observation features themselves.
- Widening the obstacle window past 2 invalidates pre-trained model weights
  (input dim changes). The model file format must include the input dim so
  load-time mismatch is a hard error, not silent corruption — recorded as a
  forward-looking note for ADR-007 (algorithm choice, slice 3).

## Alternatives considered

- **One-hot `type_id`** — rejected per §3.4 reasoning (no representational
  gain at this scale; loses sentinel-in-band property).
- **Velocity / angular-velocity features for the dino** — rejected; the page
  exposes `tRex.yPos` and `tRex.jumping`, which encode mid-jump phase
  without needing a derivative the env would have to compute frame-over-frame
  (and risk smoothing artifacts).
- **Pixel observation** — explicitly out per design-plan §3 non-goals
  (post-mortem: feature-vector observation was a good v1 call; pixels
  re-introduce the 2023 input modality that scored ~555 with much more
  capacity).
