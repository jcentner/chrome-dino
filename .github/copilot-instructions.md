# chrome-dino — Copilot Instructions

You are working on **chrome-dino**, a PPO-based reinforcement learning agent that plays Chrome's offline dinosaur game.

## Project Context

- **Implementation language**: Python 3.12
- **Key dependencies**: PyTorch, Stable-Baselines3, Gymnasium, NumPy
- **Hardware target**: i7-12700K, 32GB RAM, RTX 3070 Ti (CUDA 13.0)
- **Description**: Headless Dino game environment + PPO training pipeline. Third iteration of this project (2018 supervised, 2023 DQN+browser, 2026 PPO+headless).

## Architecture

- `src/env.py` — `DinoEnv`: Gymnasium environment implementing Chrome Dino physics from Chromium source constants. 20-dim observation vector, 3 discrete actions (noop/jump/duck), AABB collision.
- `scripts/train.py` — PPO training with SubprocVecEnv parallelism, eval callbacks, checkpointing.
- `scripts/evaluate.py` — Model evaluation with score statistics.
- `2018-implementation/` — Archived: supervised CNN (TensorFlow).
- `2023-implementation/` — Archived: DQN + Selenium + OCR.

## Key Architecture Decisions

Before making design choices, check existing [ADRs](docs/architecture/decisions/). Record new significant decisions as ADRs.

## Documentation

- Vision lock: [docs/vision/VISION-LOCK.md](docs/vision/VISION-LOCK.md) — versioned in place; scope changes require human approval
- Architecture: [docs/architecture/overview.md](docs/architecture/overview.md)
- Open questions: [docs/reference/open-questions.md](docs/reference/open-questions.md)
- Tech debt: [docs/reference/tech-debt.md](docs/reference/tech-debt.md)
- Glossary: [docs/reference/glossary.md](docs/reference/glossary.md)
- Stack skills: [.github/skills/](.github/skills/) — technology-specific docs grounding

## Coding Conventions

- Check [open questions](docs/reference/open-questions.md) before making decisions that aren't covered by ADRs. If a question is relevant, resolve it and record the decision.
- New significant design choices should be recorded as ADRs in `docs/architecture/decisions/`.
- Use the [tech debt tracker](docs/reference/tech-debt.md) for known compromises.
- When introducing new terms, add them to the [glossary](docs/reference/glossary.md).
- Prefer simple, well-tested code over clever abstractions.
- Every design choice should have a reason.

## Quality Standards

- Test coverage should include both happy paths and edge cases.
- All external actions should require explicit human approval.
<!-- TODO: Add project-specific quality standards -->
