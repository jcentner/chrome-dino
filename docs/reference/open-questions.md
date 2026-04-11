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

**Status**: Open
**Priority**: High
**Context**: Both simulate deployment latency. Frame skip (N game frames per step) and action delay (action buffered for D frames) address different aspects of the timing mismatch. Training time increases with frame skip.
**Current thinking**: Use both — action_delay=1 + frame_skip=2 models a realistic 2-3 frame observation-to-effect latency. Test each independently to measure contribution.

### OQ-002: JS frame-stepping as alternative to latency training

**Status**: Open
**Priority**: Medium
**Context**: Instead of training with latency, we could step Chrome's game frame-by-frame via JS injection, giving frame-perfect control. This would make the browser environment match the headless one exactly.
**Current thinking**: Implement this as a separate validation mode. If it works, it proves the policy transfers when timing matches. But doesn't solve the "real-time play" narrative for the blog.

### OQ-003: Domain randomization scope

**Status**: Open
**Priority**: Low
**Context**: Randomizing action delay (0-3 frames), speed jitter, and gap variance during training would produce a more robust policy. But it's more complex and takes longer to converge.
**Current thinking**: Try the simple fixes first (fixed delay + frame skip). Only add randomization if the fixed approach doesn't transfer well enough.
