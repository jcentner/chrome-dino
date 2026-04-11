# chrome-dino — Open Questions

Questions that need resolution before or during implementation. Use this to track uncertainty explicitly.

## Format

```
### OQ-NNN: Question title

**Status**: Open / Resolved / Deferred
**Priority**: High / Medium / Low
**Context**: Why this question matters.
**Current thinking**: Best guess or leading option (if any).
**Resolution**: (filled in when resolved, with reference to ADR if applicable)
```

## Open Questions

### OQ-001: Frame skip vs. action delay — which is more important?

**Status**: Resolved
**Priority**: High
**Context**: Both simulate deployment latency. Frame skip (N game frames per step) and action delay (action buffered for D frames) address different aspects of the timing mismatch. Training time increases with frame skip.
**Resolution**: Use both — `action_delay=1` + `frame_skip=2` models a realistic 2-3 frame observation-to-effect latency. Implemented in ADR-001.

### OQ-002: JS frame-stepping as alternative to latency training

**Status**: Resolved
**Priority**: Medium
**Context**: Instead of training with latency, we could step Chrome's game frame-by-frame via JS injection, giving frame-perfect control. This would make the browser environment match the headless one exactly.
**Resolution**: Implemented and validated. JS frame-stepping overrides `performance.now()` and `requestAnimationFrame` to step Chrome's game loop deterministically. Results: browser mean=1757 (10 ep) vs 256 real-time, 74% transfer from headless (2365). Beats 2023 DQN (555) by 3.2x. See ADR-002.

### OQ-003: Domain randomization scope

**Status**: Deferred
**Priority**: Low
**Context**: Randomizing action delay (0-3 frames), speed jitter, and gap variance during training would produce a more robust policy. But it's more complex and takes longer to converge.
**Current thinking**: Frame-stepping (OQ-002) solved the transfer problem for deterministic validation. Domain randomization would only matter if real-time play (without frame-stepping) becomes a goal.
