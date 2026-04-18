# ADR-005 — Validation harness shape

**Date**: 2026-04-17
**Status**: Accepted
**Phase**: 1 (introduced in slice 1)
**Anchors**: [phase-1 design plan § AC-HARNESS, AC-MET, AC-DEPLOYABILITY](../../../roadmap/phases/phase-1-design.md), [project history § post-mortem](../../../project-history.md)

## Context

The post-mortem's first named failure was "headline metric drifts away from
deliverable" — frame-stepped scores reported as the result while the real-time
agent scored mean 64. The validation harness is the single mechanism that
prevents that recurrence.

## Decision

The validation harness is `scripts/eval.py`, the **only** eval script in the
repo (AC-SINGLETON). It has the following shape, frozen for the phase:

- **One entry point**: `python -m scripts.eval --policy {heuristic, learned}
  [--checkpoint <path>] --episodes 20 --out <artifact-path>`.
- **Real-time only**: no flag combination disables real-time play. The agent
  observes, decides, and dispatches actions while the page advances on its own
  `requestAnimationFrame` clock.
- **Pinned versions enforced at run-time**: `Browser.version_check()` runs
  before any episode and raises `VersionMismatchError` on mismatch with
  `PINNED_CHROME_MAJOR`. The eval script propagates the error rather than
  catching and continuing.
- **Pinned artifact schema**: the JSON shape is locked by
  `tests/test_eval_artifact_schema.py` and validated by
  `scripts.eval.validate_artifact` before being written. Slices 3, 4, 5, 6 all
  read this shape; the MET claim in slice 6 is one of these artifacts.
- **Deterministic episode boundary**: an episode ends when the page reports
  `Runner.instance_.crashed === true`. Wall-clock and page-clock are both
  logged per-episode so any drift between them is visible in the artifact.
- **Score readout**: `Math.floor(Runner.instance_.distanceRan *
  Runner.config.COEFFICIENT)` — the same formula the page uses to render its
  on-screen score. AC-HARNESS requires the harness's reported per-episode
  score to exact-match the page's displayed final score (with at most a
  one-score-tick gap allowed if game-over preempts the last sample).

## Consequences

- Frame-stepped scores cannot be cited toward MET — there is no entry point
  that produces them.
- Slice 6's MET claim is a single committed artifact file that anyone with the
  pinned runtime can re-run.
- AC-HARNESS is verified once in slice 1 by an independent manual count; no
  learned model may be claimed against MET until that gate passes.
