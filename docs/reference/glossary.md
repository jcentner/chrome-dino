# chrome-dino — Glossary

Project-specific terms and their definitions.

<!-- Format: **Term** — Definition. -->

**AABB** — Axis-Aligned Bounding Box. Simplified collision detection used by the headless environment (Chromium uses a multi-box system).

**Runner API** — The global `Runner.getInstance()` interface exposed by Chrome's dino game JavaScript. Used by the browser validation script to read game state (speed, obstacles, T-Rex position) without OCR or screen capture.

**PPO** — Proximal Policy Optimization. The RL algorithm used in the 2026 implementation. More stable than DQN for environments with continuous speed ramps.

**Action delay** — A FIFO buffer in the environment that delays action execution by N frames, simulating the round-trip latency of browser automation via Selenium.

**Frame skip** — Multiple internal game frames per `env.step()` call. Reduces the effective decision rate to match browser polling frequency (~30Hz vs 60fps).

**Sim-to-real gap** — The difference between headless environment performance and real Chrome browser performance. v1 had a 12x gap (mean 2,247 headless vs 190 browser).
