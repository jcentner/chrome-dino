# chrome-dino — Current State

**Phase Status**: In Progress — v2 retraining done, browser validation pending

## What Exists

- `src/env.py` — Headless Dino game environment (Gymnasium), v2 with action_delay, frame_skip, speed-dependent jump
- `scripts/train.py` — PPO training pipeline with v2 env params via CLI
- `scripts/evaluate.py` — Model evaluation with v2 env params via CLI
- `scripts/validate_browser.py` — Browser validation with fixed obstacle Y mapping
- `models/ppo_dino_v2/` — Trained PPO v2 model (best + checkpoints, training ongoing)
- `models/ppo_dino_v1/` — Archived v1 model
- `logs/ppo_dino_v2/` — TensorBoard training logs
- `tests/test_env_v2.py` — 30 tests for v2 env features
- `2018-implementation/` — Archived: supervised CNN (TensorFlow)
- `2023-implementation/` — Archived: DQN + Selenium + OCR
- `project-history.md` — Development narrative for blog post adaptation
- `.github/` — Copilot agents, prompts, hooks, instructions
- `docs/` — Vision lock, architecture, ADRs, reference docs

## Results

### v2 Headless Evaluation (50 episodes, action_delay=1, frame_skip=2)

| Metric | Value |
|--------|-------|
| Mean score | 2,340 |
| Max score | 5,673 |
| Min score | 733 |
| Median score | 2,207 |
| 90th percentile | 2,991 |
| Training progress | 885K/2M steps (best model improving, training ongoing) |

### v1 Headless Evaluation (100 episodes, no delay/skip) — for comparison

| Metric | Value |
|--------|-------|
| Mean score | 2,247 |
| Max score | 4,729 |

### Browser Validation v1 (5 episodes, Chrome 147) — FAILED

| Metric | Value |
|--------|-------|
| Mean score | 190 |
| Max score | 204 |
| Verdict | **Worse than both prior implementations** |

### v2 Browser Validation — **NOT YET RUN**

## What Was Done This Session

1. **Implemented env v2 features** (ADR-001):
   - `action_delay`: FIFO buffer delays action by N frames
   - `frame_skip`: K internal frames per env step
   - Speed-dependent jump velocity: `vy = 10 + speed/10` (Chromium formula)
   - Configurable `clear_time_ms`
2. **Fixed bugs found in review**:
   - `_get_held_action()` now preserves speed_drop during frame skip
   - Observation velocity normalized to avoid exceeding [-1, 1] bounds
3. **Fixed pterodactyl Y mapping** in validate_browser.py
4. **30 tests** covering all v2 features (all pass)
5. **Updated documentation**: ADR-001, resolved TD-001-005, resolved OQ-001, updated architecture overview, glossary
6. **Trained v2 model**: 2M steps with action_delay=1, frame_skip=2 (training ongoing, best checkpoint at ~575K)
7. **Headless evaluation**: mean=1,710 (robust despite deliberate latency handicap)

## Success Target

**Browser mean score > 555** — must beat the 2023 DQN implementation.

## What's Next

1. **Browser validation** — Run validate_browser.py with v2 best model. Requires:
   - Start ChromeDriver: `/mnt/c/Temp/chromedriver.exe --port=9515`
   - `python scripts/validate_browser.py --model models/ppo_dino_v2/best/best_model.zip --episodes 10`
2. **Assess transfer ratio** — if headless 1,710 → browser target 555, need 32% transfer (vs v1's 8%)
3. **If still insufficient**: Consider domain randomization (OQ-003), JS frame-stepping (OQ-002), or longer training
4. **Update project-history.md** with v2 iteration story

## Decisions Made This Session

- ADR-001: action_delay=1, frame_skip=2, speed-dependent jump for v2
- Resolved OQ-001: use both action delay and frame skip together
- Training defaults: action_delay=1, frame_skip=2, clear_time_ms=500
- v2 velocity normalization: clip(vy / (10 + 1.3), -1, 1)

## Blocked / Unresolved

- Browser validation requires Chrome/ChromeDriver on Windows side (WSL2 setup)
- OQ-002: JS frame-stepping as alternative — deferred pending browser validation results
- OQ-003: Domain randomization — deferred pending browser validation results

## Files Modified This Session

- `src/env.py` — v2 features: action delay, frame skip, speed-dependent jump, configurable clear time
- `scripts/train.py` — v2 CLI args
- `scripts/evaluate.py` — v2 CLI args
- `scripts/validate_browser.py` — Fixed obstacle Y mapping (ground_line)
- `tests/__init__.py` — New: test package init
- `tests/test_env_v2.py` — New: 30 tests for v2 features
- `docs/architecture/decisions/001-env-v2-sim-to-real-fixes.md` — New: ADR
- `docs/architecture/decisions/README.md` — ADR index updated
- `docs/architecture/overview.md` — Updated for v2 features
- `docs/reference/tech-debt.md` — Resolved TD-001 through TD-005
- `docs/reference/open-questions.md` — Resolved OQ-001
- `docs/reference/glossary.md` — Added: action delay, frame skip, sim-to-real gap
