# Slice 2 — Source-Code Review

Canonical review artifact for the SubagentStop verdict-check hook. Full
review content lives at [docs/wraps/slice-2-review.md](../../docs/wraps/slice-2-review.md);
this file is a thin pointer that satisfies the hook's expected-artifact
path (`roadmap/phases/phase-N-review-slice-M.md`).

**Phase**: 1 — Real-time browser-native agent to MET
**Slice**: 2 (gymnasium env contract: 14-dim observation, `Discrete(3)` action, `+1`/`-100` reward, ADR-003 + ADR-004)

## Verdict

**Review Verdict: needs-fixes**
**Critical Findings: 0**
**Major Findings: 1**
**Minor Findings: 4**
**Nit Findings: 1**

See [docs/wraps/slice-2-review.md](../../docs/wraps/slice-2-review.md) for:

- File-by-file finding list with severity, location, and recommendation.
- Per-focus checklist (spec compliance, AC-SINGLETON, architecture, security, ADR quality, test-quality per-test walk, doc-sync, code style, held-jump conflict resolution).
- Per-test contract walk for all 16 tests in [tests/test_env.py](../../tests/test_env.py).
- Suggested non-blocking follow-ups.

## One-line summary of the blocking finding

ADR-003's "Normalization constants are read once at env construction from `Runner.config` / `Runner.instance_.dimensions`" paragraph does not match the as-shipped code (module-level literals for `CANVAS_HEIGHT` / `MAX_SPEED` / `TREX_XPOS` + per-step `raw_state["canvasWidth"]` lookup with a silent `or 600.0` fallback). Functional outcome is correct for the pinned Chrome (PINNED_CHROME_MAJOR=148); ADR text and code must agree before slice-2 lands. Cheapest fix: amend ADR-003 to record the actual mechanism + the Chrome-version-pinning working assumption that justifies it (mirrors the existing window=2 amendment-record pattern in the same ADR).
