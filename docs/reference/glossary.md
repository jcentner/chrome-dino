# chrome-dino — Glossary

Project-specific terms and their definitions.

<!-- Format: **Term** — Definition. -->

**AABB** — Axis-Aligned Bounding Box. Simplified collision detection used by the headless environment (Chromium uses a multi-box system).

**Runner API** — The global `Runner.getInstance()` interface exposed by Chrome's dino game JavaScript. Used by the browser validation script to read game state (speed, obstacles, T-Rex position) without OCR or screen capture.

**PPO** — Proximal Policy Optimization. The RL algorithm used in the 2026 implementation. More stable than DQN for environments with continuous speed ramps.

**Action delay** — A FIFO buffer in the environment that delays action execution by N frames, simulating the round-trip latency of browser automation via Selenium.

**Frame skip** — Multiple internal game frames per `env.step()` call. Reduces the effective decision rate to match browser polling frequency (~30Hz vs 60fps).

**Sim-to-real gap** — The difference between headless environment performance and real Chrome browser performance. v1 had a 12x gap (mean 2,247 headless vs 190 browser).

**endJump cap** — Chrome's jump height limiter (`trex.ts:483-520`). When the dino rises above `maxJumpHeight` (63px above ground), upward velocity is capped to `dropVelocity` (5.0). Reduces peak from ~101 (ballistic) to ~87. Implemented in env as `MAX_JUMP_HEIGHT`/`MIN_JUMP_HEIGHT` constants with `reached_min_height` state tracking.

**Frame-stepping** — JS injection technique that overrides Chrome's `performance.now()` and `requestAnimationFrame` to step the game deterministically from Python. Each step advances exactly N × 16.67ms, eliminating the timing mismatch that caused real-time validation to fail (~51fps vs trained 60fps). See ADR-002.
