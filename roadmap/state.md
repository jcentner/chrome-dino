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

- **Stage**: implementation-planning
- **Blocked Kind**: n/a
- **Phase**: 1
- **Phase Title**: Real-time browser-native agent to MET
- **Source Root**: src/
- **Test Path Globs**: **/test/**, **/tests/**, **/test_*, **/*_test.*, **/*.test.*, **/*.spec.*, **/__tests__/**, **/__test__/**, **/spec/**, **/specs/**
- **Config File Globs**: package.json, tsconfig.json, tsconfig*.json, pyproject.toml, setup.cfg, setup.py, Cargo.toml, go.mod, pnpm-workspace.yaml, yarn.lock, pnpm-lock.yaml, package-lock.json, jest.config.*, vitest.config.*, pytest.ini, tox.ini, karma.conf.*, mocha.opts, .mocharc.*, conftest.py, *.config.*, *.config
- **Design Plan**: roadmap/phases/phase-1-design.md
- **Design Status**: approved
- **Design Critique Rounds**: 2
- **Implementation Plan**: n/a
- **Implementation Status**: n/a
- **Implementation Critique Rounds**: 0
- **Active Slice**: n/a
- **Slice Total**: n/a
- **Blocked Reason**: n/a

## Slice Evidence

- **Evidence For Slice**: n/a
- **Tests Written**: n/a
- **Tests Pass**: n/a
- **Reviewer Invoked**: n/a
- **Review Verdict**: n/a
- **Critical Findings**: 0
- **Major Findings**: 0
- **Strategic Review**: n/a
- **Committed**: n/a

## Phase Completion Checklist

- [ ] All acceptance criteria verified
- [ ] ADRs recorded for new decisions
- [ ] Open questions resolved or flagged
- [ ] Tech debt documented
- [ ] Docs synced (README, architecture, instructions)
- [ ] Wrap summary written
- [ ] Context notes saved to /memories/repo/
- [ ] CURRENT-STATE updated for next phase
