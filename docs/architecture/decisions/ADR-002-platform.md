# ADR-002 — Windows-native runtime for training and evaluation

**Date**: 2026-04-17
**Status**: Accepted
**Phase**: 1 (introduced in slice 1)
**Anchors**: [vision lock § MET operational definitions](../../vision/VISION-LOCK.md), [project history § post-mortem](../../../project-history.md)

## Context

The MET claim is conditioned on "Windows-native — Windows host OS, Windows
Chrome, Windows Python. Not WSL2. Not a Linux VM forwarding X." (vision lock).
That phrasing exists because the v1 post-mortem identified Windows-native vs
Linux-VM as a non-trivial source of behavioural divergence in Chrome's render
loop, and because Windows is the only environment in which the agent can be
demonstrated to run unmodified Chrome end-to-end.

## Decision

Both training and evaluation run **Windows-native**:

- Host OS: Windows (10 / 11).
- Chrome: a pinned `chrome-for-testing` `chrome-win64` build installed
  side-by-side at `C:\chrome-dino-runtime\` (NOT the user's auto-updating
  Chrome).
- ChromeDriver: matching `chromedriver-win64` from the same `chrome-for-testing`
  version row, committed to `chromedriver/`.
- Python: standard CPython on Windows; `.venv` in repo root.

## Consequences

- No WSL2 / Linux VM / macOS path is supported in phase 1. Cross-platform is a
  future-phase concern.
- Chrome auto-updates are non-events: the runtime install is a frozen binary in
  a dedicated directory. `Browser.version_check` enforces the pin and refuses
  to run on mismatch (see ADR-005).
- Operator setup is one-time per workstation. Documented in
  [`docs/setup/windows-chrome-pinning.md`](../../setup/windows-chrome-pinning.md).
