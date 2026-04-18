# chrome-dino — Narrative State

> **Machine-readable workflow state lives in [state.md](state.md).** Hooks
> parse that file. This file holds narrative context that humans read and
> agents append to.
>
> **Per-session activity logs live in [sessions/](sessions/).**

## Active Session

- **Log**: sessions/7dd453f7-2bb8-4433-b879-03869ef58bba.md

## Waivers

(Human-approved exceptions to the normal flow. None yet.)

## Proposed Workflow Improvements

(Builder writes improvement suggestions here. Humans review and apply manually
between phases — the builder does not self-modify hooks, agents, or prompts.)

## Context

The builder appends a short narrative summary here at significant transitions
(stage advances, phase completion, blocked reasons). Per-tool-call logging
goes to `sessions/<id>.md` automatically.

- 2026-04-17 bootstrap: greenfield-redux. Human-led deep interview pinned the
  scope: real-time agent in unmodified Chrome on Windows-native, MET = mean
  >= 2000 over 20 consecutive episodes (max 2645 is informational stretch).
  Vision lock v1.0.0 written at [docs/vision/VISION-LOCK.md](../docs/vision/VISION-LOCK.md)
  with four binding constraints derived from `project-history.md`
  § "Post-Mortem: How the 2026 Run Went Off the Rails" (real-time-only
  metric, two-iteration stop gate, single-implementation rule, vision is
  defended). Phase 1 design plan drafted at
  [phases/phase-1-design.md](phases/phase-1-design.md); approach committed:
  browser-native online RL on a hand-engineered feature-vector observation,
  single Chrome instance, no headless simulator at any point. Tech stack
  is Python on Windows-native, hardware-capped to one RTX 3070 Ti.
  Catalog activated: deep-interview (skill), anti-slop (skill), clarify
  (prompt), commit-trailers (pattern). v1-era `src/` and `scripts/` are
  out of scope for reuse; old code is reference only. Stage advanced to
  `design-critique` for the next session.
