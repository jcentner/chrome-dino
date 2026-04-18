# ADR-008 — Action dispatch via Chrome DevTools Protocol

**Date**: 2026-04-17
**Status**: Accepted (default; subject to slice-1 latency measurement)
**Phase**: 1 (introduced in slice 1)
**Anchors**: [phase-1 implementation plan § 3.2](../../../roadmap/phases/phase-1-implementation.md), [vision lock § MET operational definitions](../../vision/VISION-LOCK.md)

## Context

The agent must dispatch keyboard actions ({jump, duck, no-op}) to the
unmodified Chrome window in real time. Three mechanisms were considered:

| Option | Pros | Cons |
|---|---|---|
| Selenium `send_keys` on a focused element | Standard Selenium API. | Round-trip latency through the WebDriver wire protocol; requires the canvas element to hold focus, which is fragile across window-state changes. |
| Chrome DevTools Protocol `Input.dispatchKeyEvent` | Lower latency than Selenium key events; does not require an in-page focused element; observed on the page identically to a real keyboard event. | Requires a CDP session; `webdriver` exposes this via `driver.execute_cdp_cmd`. |
| `pydirectinput` / WinAPI `SendInput` | OS-level keystroke; bypasses Chrome's event loop entirely. | Re-introduces focus fragility (window must be foreground); requires a stack-skill before adoption; out-of-band relative to "the page sees it as a keyboard event." |

The vision lock permits read-only DOM/JS observation and does not prohibit
keyboard event dispatch via the automation driver. CDP `Input.dispatchKeyEvent`
is event dispatch on the page's own keyboard input pathway — it does not
mutate game state directly, it lets the page's event handlers do so, exactly
as a real keypress would.

## Decision

**Default: CDP `Input.dispatchKeyEvent`** via `driver.execute_cdp_cmd`. Mapped
in `src/browser.py::Browser.send_action` per the §3.5 invariant (any non-DUCK
action releases held `ArrowDown` first; episode-ending transitions release all
held keys before returning).

## Swap criterion

Slice 1 measures end-to-end observe-decide-act latency. If the measured CDP
key-dispatch round-trip p99 exceeds **16 ms** (one frame at 60fps) sustained
over the 20-episode heuristic run, this ADR is **amended** (not silently
overridden) to evaluate fallbacks in order of preference:

1. Selenium `send_keys` (likely worse latency, retained for completeness).
2. `pydirectinput` (would require a stack skill under
   `.github/skills/pydirectinput/` before adoption).
3. WinAPI `SendInput` via `ctypes` (last resort).

The slice-1 latency exit branch routes mismatch to `Stage: blocked,
Blocked Kind: awaiting-human-decision` with the per-step latency log as
artifact. No auto-switch.

## Consequences

- `src/browser.py` depends on the CDP session being available, which Selenium
  exposes by default.
- The action mapping is stateful (it tracks whether `ArrowDown` is held).
  Tests in `tests/test_browser.py` exercise the state machine across DUCK →
  JUMP → DUCK, NOOP, reset, and teardown transitions.
- If the swap criterion fires, the swap target is a Tier-1 architectural
  decision and must land its own ADR amendment before the swap is implemented.
