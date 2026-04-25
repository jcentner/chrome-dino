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

### TD-003: `src/heuristic.py` baseline far weaker than design assumed (RESOLVED via debug-and-reset)

**Priority**: HIGH — affects AC-STOP-GATE binding constraint
**Introduced**: Phase 1, slice 1 (measured against live Chrome 148.0.7778.56)
**Description**: Initial 20-episode mean = **48.3** (first-cactus deaths every time). Investigation found three independent runtime bugs masquerading as policy weakness:

1. **`Browser.send_action(JUMP)` truncated the jump arc.** It dispatched `keyDown ArrowUp` immediately followed by `keyUp ArrowUp`. Once the dino reached `MIN_JUMP_HEIGHT` (~30 px above ground) the page's `endJump()` saw the keyUp and capped `jumpVelocity` at `DROP_VELOCITY = -5`, halving the in-air safe window from ~480 ms to ~280 ms. Fix: hold `ArrowUp` from JUMP entry until the next non-JUMP action; release in `_release_held_keys`.
2. **Pterodactyl thresholds were inverted.** Per `chromium/.../offline.ts` `Pterodactyl.config.Y_POS_HEIGHT = [100, 75, 50]`, low (y=100) overlaps both standing AND ducking collision boxes (must JUMP), mid (y=75) clears the duck box but hits standing (must DUCK), high (y=50) is overhead (NOOP). The original code did the opposite for low and mid pterodactyls.
3. **Trigger threshold did not account for read-loop latency.** `Browser.read_state` round-trips through `execute_script` and effectively suspends the page's RAF; obstacles can "tunnel" 30-50 px between consecutive Python reads. A bare physics-derived threshold (`14.5*speed - W/2`) left no slack for that. Bumped the latency pad to `+40 px`.

After all three fixes the heuristic reaches mean score ≈ **400** over 10 episodes with a 45 s wall cap (5/10 episodes hit the cap still alive at scores 624-745; 4/10 still die early — see TD-005). 8× the original baseline.

**Resolution status**: Fixed in `src/browser.py` (held-jump) and `src/heuristic.py` (pterodactyl tiers, latency pad). The frozen baseline now lives at this stronger value.
**Open question for human (carried forward)**: With baseline ≈ 400, AC-STOP-GATE's `+50 absolute` gate still under-bites; the `+10% relative` gate (= +40 from 400) is comparable. Decide whether to (a) keep AC-STOP-GATE as-is and rely on MET=2000 to carry the weight, (b) tighten AC-STOP-GATE in a v1.2.0 vision-lock amendment, or (c) something else.

### TD-005: heuristic still has a ~30-40% early-death tail

**Priority**: Medium
**Introduced**: Phase 1, slice 1
**Description**: With all three TD-003 fixes in place, ~3-4 of 10 episodes still die in the early game (score 60-75) on a particular obstacle pattern (likely back-to-back small-then-large cactus where the dino's apex doesn't have time to reset). The remaining 6-7 episodes either survive indefinitely (hit the 45 s wall cap at scores 600-745) or die at score 400-500.
**Why accepted**: AC-SINGLETON freezes the heuristic. Mean score 401 is plenty for slice 3's stop-gate role. Investigating the early-death pattern would mean unfreezing the singleton.
**Resolution path**: in a future phase, look at obstacle-spawn intervals at speed 6.x — the dino may be unable to recover from two cacti within one jump-cycle's distance under the current threshold.

### TD-006: eval reset shows recurring identical scores when wall-capped

**Priority**: Low
**Introduced**: Phase 1, slice 1 (after `reset_episode` was extended to call `r.gameOver()` if the dino was still running)
**Description**: A 10-episode 45-s-cap eval shows several wall-capped episodes ending on *exactly the same score* (e.g. four episodes at 624). Likely cause: the dino game's RNG state is reset by `restart()` to a deterministic seed and 45 s of identical play produces identical distance, since the heuristic is also deterministic. Not a bug per se — just noisy variance reporting.
**Why accepted**: Cosmetic. The mean is still informative; outliers (the early deaths) dominate the spread.
**Resolution path**: either widen the wall cap so all episodes terminate naturally (slow), or shuffle the gap-coefficient seed between episodes (would require modifying the page state via JS each reset).

### TD-004: `scripts/capture_fixtures.py` only captures 5/7 scenarios live

**Priority**: Low (slice 2 will redo)
**Introduced**: Phase 1, slice 1
**Description**: With the frozen heuristic crashing on the first cactus (~score 48), the `mid_duck` and `near_crash` fixture scenarios cannot be reached in real gameplay. Only 5 of 7 target labels are captured: `no_obstacles`, `mid_jump`, `normal_mid_episode`, `both_obstacle_slots_populated`, `terminal`.
**Why accepted**: Slice-2 work (env contract) needs fixtures of every scenario, but slice 2 will inevitably re-drive trajectories with finer control — easier to capture the remaining two there than to hand-craft them now.
**Resolution path**: in slice 2, run capture with a manual driver (forced JUMP/DUCK schedule) to hit `mid_duck` and `near_crash`.


### TD-007: `DinoEnv` silently absorbs three corner cases (slice 2 reviewer minors)

**Priority**: Low
**Introduced**: Phase 1, slice 2 (reviewer findings #2/#3/#4)
**Description**: Three robustness gaps in `src/env.py`:
  1. `_obstacle_block` maps unknown `obstacle["type"]` strings to `type_id=-1` while the rest of the 5-tuple stays real, producing an internally inconsistent block (real geometry, sentinel discriminator). A future Chrome obstacle subtype would be silently miscategorized.
  2. `or 600.0` / `or 0.0` fallbacks on `canvasWidth`, `tRex.yPos`, `currentSpeed` mask page-mid-load corner cases as plausible observations.
  3. `_info_dict` swallows every exception from `browser.get_score()` and reports `score=0`; a CDP disconnect is indistinguishable from a real zero-score episode.
**Why accepted**: All three are robustness gaps, not contract violations. The pinned Chrome major (148) ships only the three obstacle types currently mapped, never returns `None` for `canvasWidth` outside teardown, and the `get_score()` JS one-liner is defensive (always returns 0 on missing Runner). The slice-2 contract surface (observation/action/reward/terminal) is correct on every captured fixture and on the live integration test; these are pre-emptive hardening items.
**Resolution path**: (1) sentinel the entire 5-tuple on unknown type; (2) raise on `canvasWidth in (None, 0)`; (3) narrow the `except` in `_info_dict` or let it propagate so the eval/training loop sees the disconnect. Cheap to do; deferred to keep slice 2 minimal.

### TD-008: `DinoEnv` reward on no-op past-terminal step diverges to -8

**Priority**: Low
**Introduced**: Phase 1, slice 2 (reviewer finding #5)
**Description**: `DinoEnv.step` returns `REWARD_TERMINAL = -100.0` on every call after the first terminal, instead of the gymnasium convention of `0.0`. A misbehaving outer loop that keeps stepping past `terminated=True` would see episode reward diverge.
**Why accepted**: Slice 2 spec (impl §6 task 4) is silent on the magnitude; the test pins `terminated=True` / `truncated=False` but not the reward value. `scripts/eval.py` (slice 1) breaks on `terminated=True`, so the divergence cannot occur in this repo today. Pre-emptive; deferred to slice 4 when training loops enter the picture.
**Resolution path**: change the no-op-when-terminal branch to return `0.0`; add a regression test pinning the value.
