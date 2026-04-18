# chrome-dino — Vision Lock

> **Version**: 1.1.0
> **Updated**: 2026-04-17
> **Status**: Locked
> **Rules**: Single versioned document, updated in place. Patch (1.0.x) for typos/clarifications that do not move scope or MET. Minor (1.x.0) for within-scope additions. Major (x.0.0) for scope changes — these require human approval per binding constraint 4 below.

## Preamble

This vision lock is the greenfield-redux anchor for `chrome-dino`, written immediately after the 2026 v1 run was abandoned. It is grounded in [`project-history.md`](../../project-history.md) § **"Post-Mortem: How the 2026 Run Went Off the Rails"**. That post-mortem — not the tidier journal narrative above it — is the source of every binding constraint in this document. The journal narrative is the artifact of the failure; the post-mortem is the analysis of why it failed. Where the two disagree, the post-mortem wins. Prior implementations (`2018-implementation/`, `2023-implementation/`, and the v1-era `src/` referenced in the post-mortem but no longer present in the repo) are reference material only and are not synthesized into this vision.

## Vision

`chrome-dino` delivers a real-time autonomous agent that plays the unmodified `chrome://dino` game inside a normal Chrome window on Windows, at the game's natural 60fps. A blog writeup describing the autonomous-development experience is a secondary by-product; the bar is the agent itself, not the writeup about it.

## Success Metric (MET)

**Mean score ≥ 2000 across 20 consecutive evaluation episodes** in unmodified Chrome on Windows-native, with no clock manipulation, no JS frame-stepping, and no other non-deployable harness.

Operational definitions (binding):

- **Real-time** — the game's own `requestAnimationFrame` clock runs uninterrupted. No `chrome.debugger`-driven `Animation.setPlaybackRate`, no synchronous `rAF` step injection, no Python pauses that block the page event loop, no headless rendering. The agent observes and acts asynchronously while the page advances on its own clock.
- **Unmodified Chrome** — a current stable Chrome (or matching Chromium for ChromeDriver), launched with default flags except those required to reach `chrome://dino` and to attach an automation driver. No custom builds, no patched assets, no injected JavaScript that mutates game state. Read-only DOM/JS observation is permitted.
- **Episode** — one play-through from the dino's first jump-eligible frame to the game-over event raised by the page itself, scored using the page's own score readout.
- **20 consecutive** — twenty episodes run back-to-back in a single evaluation session, in order, with no cherry-picking. Mean is the arithmetic mean of those twenty scores. Re-running eval to chase a better mean is a protocol violation; the most recent eval session is the one of record.
- **Windows-native** — Windows host OS, Windows Chrome, Windows Python. Not WSL2. Not a Linux VM forwarding X.

If any of these conditions are violated, the resulting number is diagnostic, not a MET claim.

## Headline Stretch (informational, not a gate)

**Max ≥ 2645** on a single real-time episode, matching the 2018 reported best. This is a headline number for the eventual writeup; it is not part of MET and does not gate any phase.

## Binding Constraints

The four constraints below are derived directly from the post-mortem's "What the redux has to do differently" section. Each names the specific failure mode it prevents.

1. **Real-time browser score is the only success metric.** Frame-stepped scores, headless-sim scores, and sim-transfer-ratio scores are diagnostic and may not be cited as evidence that MET (or any per-phase acceptance criterion grounded in MET) is met.
   *Rationale:* the v1 run reported "mean 439" while the deployable agent scored mean 64; the metric drifted away from the deliverable until the deliverable was effectively redefined to fit the metric.

2. **Stopping is a first-class action.** If two consecutive iterations of the same approach do not move the real-time metric meaningfully — defined as **≥ +10% relative AND ≥ +50 absolute mean (both thresholds must be cleared; equivalently, whichever is larger)** — the next action is a strategic re-plan via the `critic` / `product-owner` / `strategic-review` flow, *not* a third iteration of the same approach.
   *Rationale:* v1 → v2 → v3 transfer ratios moved 8% → 9% → 11% over weeks; the autonomous loop had no mechanism to recognise that as a noise floor and stop.

3. **One environment, one training script, one eval script.** Any second instance of any of these — or any other piece of agent infrastructure that already exists once — requires an ADR justifying the duplication *before* the duplicate is created.
   *Rationale:* v1 ended with 3,072 lines of Python implementing roughly 500 lines of ideas three ways, because every slice locally justified one more file and nobody asked whether the repo cohered as a whole.

4. **The vision lock is written once and defended.** Scope or success-metric changes are not auto-accommodated by the autonomous loop. The builder transitions to `Stage: blocked, Blocked Kind: awaiting-vision-update` and a human decides. "We got a non-deployable result that resembles the goal" is explicitly *not* grounds for a scope change.
   *Rationale:* v1's vision drifted from "headless PPO that plays Chrome Dino" to "multiple approaches to Chrome Dino, as a writeup about autonomous development" — broadened each time a slice fell short, until what was achieved fit the rewritten scope.

(Post-mortem constraint #4 — the 559 heuristic as a hard baseline — is intentionally not promoted to a binding constraint here. The MET bar of mean 2000 sits well above 559, so the heuristic functions as a sanity check on the validation harness, not as a gate.)

## Out of Scope (v1)

- **JS frame-stepping as a deliverable code path.** A frame-stepped harness *may* exist as an explicitly-labelled diagnostic tool; it may not ship as the agent or be cited toward MET.
- **Reuse of v1-era source code** — `src/env.py`, `src/chrome_env.py`, `scripts/train.py`, `scripts/train_browser.py`, `scripts/validate_browser*.py`, `scripts/heuristic_agent.py`, and the v1 test files. Clean slate. Prior implementations are reference material only and are not synthesized into the design.
- **Multi-agent / multi-approach comparison.** v1 commits to a single approach and must hit MET with it before any second approach is scoped. Comparison phases are deferred.

## Technical Constraints

- **Language**: Python.
- **Hardware**: single workstation with one NVIDIA RTX 3070 Ti; no cloud compute.
- **OS**: Windows-native for both training and evaluation (see MET operational definitions).

## Authority

This vision lock is the highest-authority document in the repo (see [AGENTS.md](../../AGENTS.md) § Authority order). All ADRs, architecture docs, roadmap entries, and plans must conform to it. Per binding constraint 4, scope changes require human approval via `Stage: blocked, Blocked Kind: awaiting-vision-update` — proposed changes are drafted in [`roadmap/CURRENT-STATE.md`](../../roadmap/CURRENT-STATE.md) `## Proposed Vision Updates` and applied only after human sign-off.

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-04-17 | Initial lock (greenfield redux post-2026-v1 post-mortem). |
| 1.1.0 | 2026-04-17 | Binding constraint 2 threshold direction corrected from "whichever is smaller" to "both thresholds must be cleared" (whichever is larger). Raised by phase-1 design-critique R1 item 3; the smaller-of rule mathematically permitted the v1 48→53→64 sunk-cost spiral the constraint exists to prevent. Human-approved 2026-04-17. |
