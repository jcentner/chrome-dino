# ADR-004 — Action space: `Discrete(3)`

**Date**: 2026-04-25
**Status**: Accepted
**Phase**: 1 (introduced in slice 2)
**Anchors**: [phase-1 implementation plan § 3.5](../../../roadmap/phases/phase-1-implementation.md), [ADR-008 — Action dispatch](ADR-008-action-dispatch.md)

## Context

The Chromium dino game responds to three meaningful keyboard inputs:
no-input (run), `ArrowUp` / `Space` (jump), `ArrowDown` (duck). Two prior
choices in this repo's history bear on the decision:

- **2023 implementation** used a 2-action space (NOOP, JUMP). Pterodactyl
  obstacles spawn at three vertical tiers; the low tier (y = 100 px)
  overlaps both the standing and ducking dino bounding boxes, so JUMP is
  the only safe action. The mid tier (y = 75 px) clears the duck box but
  hits standing — DUCK is required. Without a DUCK action, mid-tier
  pterodactyls are an instant-death obstacle the policy cannot avoid.
- **2018 implementation** had a richer action space (separate
  ArrowUp-press / ArrowUp-release / ArrowDown-press / ArrowDown-release
  events) which inflated the action set without adding policy expressivity:
  jump-release is a no-op, duck-release is identical to "switch to NOOP."

## Decision

**`gymnasium.spaces.Discrete(3)`** with the mapping:

| Action id | Name | Browser key sequence |
|---|---|---|
| `0` | `NOOP` | release `ArrowDown` if held, release `ArrowUp` if held; nothing else |
| `1` | `JUMP` | release `ArrowDown` if held; press-and-hold `ArrowUp` (held until next non-`JUMP` action) |
| `2` | `DUCK` | release `ArrowUp` if held; press-and-hold `ArrowDown` (held until next non-`DUCK` action) |

The constants `NOOP=0`, `JUMP=1`, `DUCK=2` are defined in `src/browser.py`
and re-exported by `src/env.py` (used by tests, by `src/heuristic.py`, and
by `scripts/eval.py`). A single source of truth — AC-SINGLETON.

**Held-key invariant** (recorded in implementation plan §3.5 and exercised
by `tests/test_browser.py`):

> Any state transition that ends an episode (terminal step,
> `reset_episode()`, env teardown, exception in `step()`/`reset()`) AND any
> action transition that does not match the currently-held key MUST release
> all held keys before the new keys are dispatched.

This closes two state-machine corner cases:

1. **`DUCK → JUMP`** with `ArrowDown` still held — page reads `ArrowUp` as
   "exit duck" rather than "jump," producing a degraded or null jump.
2. **`DUCK → terminal → reset`** with `ArrowDown` still held — new episode's
   first observed steps are silently in a ducking pose, skewing the
   training distribution exactly the way the post-mortem warns about.

The slice-1 held-jump fix added the symmetric case for `ArrowUp`: `JUMP`
holds the key (do not auto-release) so the page's `endJump()` does not
prematurely cap `jumpVelocity` at `DROP_VELOCITY = -5`. The held-key flag
is cleared on the next non-`JUMP` action and on `reset_episode()`.

## Consequences

- Action dispatch latency is paid once per `step()`, not three times per
  step (no separate press/release events on the policy hot path except
  the held-key release of the *previous* action's key, which is a single
  CDP call).
- The env's `action_space.n == 3` is part of the contract; adding a fourth
  action requires an ADR-004 amendment AND invalidates pre-trained policy
  output heads (output dim changes).
- The 2023 mistake is not re-introduced: pterodactyl-mid-tier handling is
  representable in the action space.
- The held-key invariant is a `src/browser.py` test obligation; `src/env.py`
  trusts the browser layer to honor it. Any env-level held-key-leak bug is
  a `src/browser.py` regression by definition.

## Alternatives considered

- **`Discrete(2)` (NOOP, JUMP)** — rejected. Re-creates the 2023 instant-
  death failure on mid-tier pterodactyls.
- **`Discrete(4)` with explicit `STOP_DUCK` / `STOP_JUMP`** — rejected. The
  release semantics are derivable from the next action; an explicit stop
  action is policy-output bloat that adds no expressivity. The held-key
  invariant in `src/browser.py` makes the release a side effect of the
  *next* action choice, which is where the policy is already deciding.
- **Continuous action space (jump force, duck duration)** — rejected. The
  page's input layer is binary (key down / key up); a continuous action
  would have to be discretized at the boundary, reintroducing the
  discretization arbitrariness without measurable expressivity gain.
