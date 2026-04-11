# chrome-dino

PPO agent that plays Chrome's offline dinosaur game, trained on a headless physics clone with constants sourced directly from [Chromium](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/neterror/resources/dino_game/).

Three implementations spanning 2018–2026 — from supervised learning to autonomous-agent-built RL.

## Current Version (2026)

- **Algorithm**: PPO (Proximal Policy Optimization) via Stable-Baselines3
- **Environment**: Headless Python recreation of Chrome Dino game physics
- **Observations**: 20-dim feature vector (speed, T-Rex state, 3 nearest obstacles)
- **Actions**: Jump, Duck, Noop
- **Training**: 16 parallel environments, ~3k FPS on RTX 3070 Ti
- **Browser validation**: Selenium + JS Runner API confirms transfer to real Chrome Dino

### Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Train
python scripts/train.py --timesteps 2000000 --name my_run

# Evaluate
python scripts/evaluate.py --model models/my_run/best/best_model.zip
```

## Previous Versions

| Version | Approach | Directory |
|---------|----------|-----------|
| 2018 | Supervised CNN (TensorFlow, trained on human input) | `2018-implementation/` |
| 2023 | DQN + Selenium + OCR (Stable-Baselines3) | `2023-implementation/` |

## Project Structure

```
src/env.py                    # Headless Dino game environment (Gymnasium)
scripts/train.py              # PPO training with parallel envs + checkpointing
scripts/evaluate.py           # Model evaluation and statistics
scripts/validate_browser.py   # Browser validation via Selenium + JS Runner API
models/                       # Saved model checkpoints
logs/                         # TensorBoard training logs
project-history.md            # Narrative development history
```

## Blog Post

See [project-history.md](project-history.md) for the full narrative — three attempts at the same problem, eight years apart.
