# 2023 Implementation — DQN + OCR + Selenium

Archived implementation from 2023. Used Deep Q-Network (DQN) with Stable-Baselines3, screen capture via `mss`, Tesseract OCR for game-over detection, and Selenium ChromeDriver to control `chrome://dino/`.

## Approach

- **Algorithm**: DQN with CNN policy (Stable-Baselines3)
- **Environment**: Custom Gym env wrapping Chrome browser via Selenium
- **Observation**: Grayscale screen capture (75×135), preprocessed with OpenCV
- **Game-over detection**: Tesseract OCR on cropped region with binarization
- **Actions**: 2 discrete (jump / no-op)
- **Platform**: Windows (pydirectinput, hardcoded paths)

## Results

Training reached ~170k of 360k target timesteps. Best checkpoint saved at step 170,280. The approach was functional but limited by:

- Slow training (real-time browser interaction, ~1 FPS effective)
- Fragile OCR-based game-over detection
- Windows-only dependencies
- No ducking action (missed pterodactyl avoidance)

## Files

- `chrome-dino.ipynb` — Complete notebook (environment, training, inference)
- `conda.md` — Environment setup notes
- `models/` — Saved model checkpoints
- `train/` — Training checkpoints
- `logs/` — TensorBoard logs
- `chromedriver/` — ChromeDriver binary and license
