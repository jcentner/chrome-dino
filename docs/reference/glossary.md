# chrome-dino — Glossary

Project-specific terms and their definitions.

<!-- Format: **Term** — Definition. -->

**AABB** — Axis-Aligned Bounding Box. Simplified collision detection used by the headless environment (Chromium uses a multi-box system).

**Runner API** — The global `Runner.getInstance()` interface exposed by Chrome's dino game JavaScript. Used by the browser validation script to read game state (speed, obstacles, T-Rex position) without OCR or screen capture.

**PPO** — Proximal Policy Optimization. The RL algorithm used in the 2026 implementation. More stable than DQN for environments with continuous speed ramps.
