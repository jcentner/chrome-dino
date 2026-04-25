# Slice 3 — Source-Code Review (Authoring Half)

Canonical review artifact for the SubagentStop verdict-check hook. Full
review content lives at [docs/wraps/slice-3-authoring-review.md](../../docs/wraps/slice-3-authoring-review.md);
this file is a thin pointer that satisfies the hook's expected-artifact
path (`roadmap/phases/phase-N-review-slice-M.md`).

**Phase**: 1 — Real-time browser-native agent to MET
**Slice**: 3 (SB3 DQN training entry point + `LearnedPolicy` wrapper + ADR-007; authoring half only)

## Verdict

**Review Verdict: needs-fixes**
**Critical Findings: 0**
**Major Findings: 1**
**Minor Findings: 3**
**Nit Findings: 1**

See [docs/wraps/slice-3-authoring-review.md](../../docs/wraps/slice-3-authoring-review.md) for:

- File-by-file finding list with severity, location, and recommendation.
- Per-focus walkthrough (ADR-007 vs impl §3.1 trims, eval-side adapter for the dict→obs contract gap, AC-SINGLETON grep for hyperparameter literals, wall-clock cap mechanics, SB3 `set_env` continuity, per-test contract walk for both new test files, security incl. SB3-pickle trust boundary, doc-sync, anti-slop walkthrough).
- Out-of-scope note: the slice-3 *evidence* half (training run, eval-mean trajectory, beat-baseline gate decision) is reviewed separately when the operator's 4h run completes.

## One-line summary of the blocking finding

`scripts/train.py` polls the wall-clock cap only between SB3 `learn()` chunks of up to `--ckpt-every` (default 25,000) env-steps. At the slice-1-measured ~5 samples/sec, a single chunk is ~83 minutes; worst-case overrun of the 4-hour cap is ~80 minutes plus periodic-eval subprocess time. Cheapest fix: add an SB3 `BaseCallback` whose `_on_step` returns `False` once `time.monotonic() - wall_start >= wall_cap_seconds`, exiting the chunk on the next env-step. Keep the outer-loop check as the backstop.
