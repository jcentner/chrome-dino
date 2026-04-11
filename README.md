# chrome-dino

Multiple approaches to playing Chrome's offline dinosaur game, all built by an autonomous AI agent. The narrative: when autonomous dev makes implementation cheap, developers learn at the strategic level — which approach works best? — and the cost of failure is low.

Five implementations spanning 2018–2026 — from supervised learning to autonomous-agent-built RL and heuristics.

## Current Version (2026)

Three approaches under a unified iteration, each built autonomously:

| Approach | Description | Browser Mean | Browser Max |
|----------|-------------|-------------|-------------|
| **Headless PPO** | Physics clone + PPO, frame-stepped validation | 439 | 1,045 |
| **Heuristic** | Speed-adaptive reactive rules, no ML | 559 | 675 |
| **Browser-native PPO** | PPO trained directly in Chrome via frame-stepping | TBD | TBD |

*Scores are frame-stepped (deterministic 60fps). Real-time Selenium scores are ~50–64 for all approaches due to browser FPS limitations.*

### Headless PPO
- **Algorithm**: PPO via Stable-Baselines3, MlpPolicy [256,256]
- **Environment**: Headless Python recreation of Chrome Dino physics
- **Training**: 16 parallel envs, ~3k FPS, converges in ~40 min
- **Browser validation**: JS frame-stepping gives deterministic 60fps control

### Heuristic
- **Zero learning**: Speed-adaptive trigger distances, pterodactyl height detection
- **Frame-stepped mean: 559** — beats PPO frame-stepped (439) by 27%
- **Insight**: Rule-based approach outperforms ML at pure decision quality; the obstacle patterns in Chrome Dino are regular enough that simple rules suffice

### Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Train headless PPO
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
scripts/heuristic_agent.py    # Heuristic (rule-based) browser agent
scripts/validate_browser.py   # Real-time browser validation (Selenium)
scripts/validate_browser_framestepped.py  # Frame-stepped validation (deterministic)
models/                       # Saved model checkpoints
logs/                         # TensorBoard training logs
project-history.md            # Narrative development history
```

## Blog Post

See [project-history.md](project-history.md) for the full narrative — multiple approaches to the same problem, built autonomously, with strategic insights about when ML beats engineering and vice versa.
