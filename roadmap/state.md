# chrome-dino — Workflow State

<!--
  This file is MACHINE-READABLE. Hooks parse the fields below to enforce the
  stage pipeline. Use the exact vocabulary — do not paraphrase values.

  Narrative content (waivers, context, proposed improvements) lives in
  CURRENT-STATE.md. Per-session activity logs live in sessions/.

  Stage vocabulary:
    bootstrap | planning | design-critique | implementation-planning |
    implementation-critique | executing | reviewing | cleanup | blocked | complete

  Blocked Kind vocabulary (required when Stage = blocked, else n/a):
    awaiting-design-approval | awaiting-vision-update | awaiting-human-decision |
    error | vision-exhausted | n/a

  Status vocabulary (Design Status, Implementation Status):
    n/a | draft | in-critique | approved | revise | rethink | waived

  Slice Evidence value vocabulary:
    yes | no | pending | n/a

  Review Verdict vocabulary:
    pending | pass | needs-fixes | needs-rework | n/a

  Strategic Review vocabulary:
    pending | pass | replan | n/a
-->

## Workflow State

- **Stage**: blocked
- **Blocked Kind**: awaiting-human-decision
- **Phase**: 1
- **Phase Title**: Real-time browser-native agent to MET
- **Source Root**: src/
- **Test Path Globs**: **/test/**, **/tests/**, **/test_*, **/*_test.*, **/*.test.*, **/*.spec.*, **/__tests__/**, **/__test__/**, **/spec/**, **/specs/**
- **Config File Globs**: package.json, tsconfig.json, tsconfig*.json, pyproject.toml, setup.cfg, setup.py, Cargo.toml, go.mod, pnpm-workspace.yaml, yarn.lock, pnpm-lock.yaml, package-lock.json, jest.config.*, vitest.config.*, pytest.ini, tox.ini, karma.conf.*, mocha.opts, .mocharc.*, conftest.py, *.config.*, *.config
- **Design Plan**: roadmap/phases/phase-1-design.md
- **Design Status**: approved
- **Design Critique Rounds**: 2
- **Implementation Plan**: roadmap/phases/phase-1-implementation.md
- **Implementation Status**: approved
- **Implementation Critique Rounds**: 3
- **Active Slice**: 3
- **Slice Total**: 6
- **Blocked Reason**: Slice 2 shipped (commit 17b40fbd, reviewer pass). Slice 3 is the SB3 DQN training run (>=500k env-steps capped at 3 days wall-clock per impl plan §6 slice 3). Pausing for operator decision on whether to launch the long-running training in the next session, or whether to revisit AC-STOP-GATE / TD-003 first (heuristic baseline = 401, vision-lock v1.1.0 +50 absolute gate is trivially clearable from that floor). Resume with /resume to start slice 3 authoring (ADR-007, src/policy.py, scripts/train.py, tests) without launching training, or escalate the TD-003 disposition first.

## Slice Evidence

- **Evidence For Slice**: 3
- **Tests Written**: pending
- **Tests Pass**: pending
- **Reviewer Invoked**: pending
- **Review Verdict**: pending
- **Critical Findings**: 0
- **Major Findings**: 0
- **Strategic Review**: n/a
- **Committed**: pending

## Phase Completion Checklist

- [ ] All acceptance criteria verified
- [ ] ADRs recorded for new decisions
- [ ] Open questions resolved or flagged
- [ ] Tech debt documented
- [ ] Docs synced (README, architecture, instructions)
- [ ] Wrap summary written
- [ ] Context notes saved to /memories/repo/
- [ ] CURRENT-STATE updated for next phase
