# ADR-006 — Singleton-infrastructure rule, operationalized

**Date**: 2026-04-17
**Status**: Accepted
**Phase**: 1 (introduced in slice 1)
**Anchors**: [phase-1 design plan § AC-SINGLETON](../../../roadmap/phases/phase-1-design.md), [vision lock § binding constraint 3](../../vision/VISION-LOCK.md), [project history § post-mortem](../../../project-history.md)

## Context

Vision-lock binding constraint 3: "One environment, one training script, one
eval script. Any second instance of any of these — or any other piece of agent
infrastructure that already exists once — requires an ADR justifying the
duplication *before* the duplicate is created."

The v1 post-mortem identified slice-by-slice file proliferation as the
dominant scaffolding failure: 3,072 lines of Python implementing roughly 500
lines of ideas three ways, because every slice locally justified one more
file and nobody asked whether the repo cohered as a whole.

## Decision

AC-SINGLETON in the phase-1 design plan extends the vision-lock rule to cover
**policy modules** as well: the repo at end of phase contains exactly:

- one Gymnasium-style environment module (`src/env.py`, slice 2),
- one training script (`scripts/train.py`, slice 3),
- one evaluation script (`scripts/eval.py`, slice 1),
- one learned-policy module (`src/policy.py`, slice 3),
- one fixed-policy module (`src/heuristic.py`, slice 1).

Both policy modules are invoked through the single eval script via its
`--policy {heuristic, learned}` flag. The browser-interface module
(`src/browser.py`, slice 1) is *not* counted as one of the five — it is a
stateless adapter to the page, not an agent surface.

**Enforcement at slice review.** The reviewer confirms, by `ls src/`,
`ls scripts/`, and `grep` for duplicated normalization constants:

1. No new file in `src/` or `scripts/` duplicates an existing role.
2. Observation normalization constants exist only in `src/env.py`.
3. Any duplication that genuinely needs to exist has an ADR landed *before*
   the duplicate file is added.

## Consequences

- The reviewer agent has a deterministic check, not a judgment call.
- `train_v2.py`, `eval_fast.py`, `env_for_testing.py`, etc. are blocked by
  default — adding any requires a new ADR explaining why the existing module
  cannot be extended in place.
- The heuristic module is preserved past slice 1 because AC-STOP-GATE's
  beat-baseline sub-gate needs it re-runnable through `scripts/eval.py`.
