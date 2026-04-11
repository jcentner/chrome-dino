# Sim-to-Real Gap Analysis

**Date**: 2026-04-10
**Context**: PPO agent scores mean=562 in headless env but only mean=48 in real Chrome Dino (8% transfer). This is worse than both the 2018 supervised approach (peak 1,810) and the 2023 DQN (~555 mean).

## The Numbers

| Implementation | Environment | Best Score | Mean Score |
|---------------|-------------|-----------|------------|
| 2018 supervised CNN | Real browser (human data) | Unknown | 1,810 |
| 2023 DQN | Real browser (trained there) | ~555 | Unknown |
| 2026 PPO | Headless clone | 1,182 | 562 |
| 2026 PPO | **Real Chrome** | **51** | **48** |

The 2023 DQN trained at ~1 FPS *directly in Chrome*. It was slow but it learned the real game. Our 2026 PPO trained 3,000x faster but learned the *wrong* game.

## Root Cause Analysis

### 1. Action Latency (Primary — ~60% of gap)

**Training**: action takes effect instantly within the same frame.
**Browser**: Selenium round-trip adds 1-2 frame delay. Duck→jump transition requires 2 Selenium commands (~34ms = 2 frames).

**Evidence**: The model switches from duck to jump at dx=110px. With a 2-frame delay at speed 7, the effective dx when the jump starts is 110 - 14 = 96px. The model's timing margins were calibrated for instant execution.

**Key finding**: Doubling the polling rate (15Hz → 30Hz) produced zero score improvement (189 vs 190). This confirms the issue is *absolute latency* (action delay), not *sampling rate*. The model's just-in-time policy breaks with any delay.

### 2. Speed-Dependent Jump Velocity (Secondary — ~20% of gap)

**Chrome source** (`trex.ts:469`):
```javascript
this.jumpVelocity = this.config.initialJumpVelocity - (speed / 10);
```

**Our env**: `INITIAL_JUMP_VELOCITY = 10.0` (constant).

| Speed | Chrome Peak Height | Our Peak Height | Chrome Ahead By |
|-------|-------------------|----------------|-----------------|
| 6 | 93.6px | 83.3px | +12% |
| 8 | 97.2px | 83.3px | +17% |
| 10 | 100.8px | 83.3px | +21% |
| 13 | 106.4px | 83.3px | +28% |

Chrome compensates for faster obstacles with higher jumps. Our agent trained without this compensation, learning timing that only works at constant jump height. In Chrome, the agent overshoots because it jumps higher than expected, spending more time airborne with potentially wrong timing for the next obstacle.

### 3. Observation Mapping Bugs (validate_browser.py)

**Pterodactyl Y position uses wrong reference**:
```python
# Current (WRONG):
obstacle_y_bottomup = max(0, ground_y - o["y"] - o["h"])
# ground_y = 93 (T-Rex groundYPos, NOT ground line)

# Correct:
ground_line = ground_y + TREX_HEIGHT  # 93 + 47 = 140
obstacle_y_bottomup = max(0, ground_line - o["y"] - o["h"])
```

Result: pterodactyl at mid-height (yPos=75 in Chrome) maps to y=0 instead of y=25. The agent can't distinguish ground-level from mid-height pterodactyls. This doesn't explain dying at score 190 (no pterodactyls at speed 6-7), but would cap scores at speed 8.5+.

### 4. clearTime Mismatch (Minor)

**Chrome**: 3,000ms (obstacles start spawning after 3 seconds).
**Our env**: 500ms (reduced for training density).

The agent was trained with early obstacles; Chrome gives a longer runway. Not directly harmful but changes the speed at which the first obstacle encounter occurs.

### 5. What's NOT the Problem

- **Collision model**: Our single AABB is 1.3-1.8x larger than Chrome's multi-box collision. Agent trained with *stricter* hitboxes → more caution in Chrome (helps, doesn't hurt).
- **Canvas dimensions**: Game logic uses internal coordinates regardless of visual canvas size.
- **Jump velocity magnitude**: Chrome's `initialJumpVelocity = -10` in normalJumpConfig matches our 10.0 (sign flip is coordinate system, not a bug).
- **Gravity**: 0.6 in both. Confirmed from source.

## Recommended Fixes (Priority Order)

### Fix 1: Action Delay in Training Env

Add a configurable action buffer. The agent's action at step N takes effect at step N+D where D is the delay (1-2 frames). Forces the agent to learn anticipatory timing.

```python
# In env.py step():
self._action_buffer.append(action)
effective_action = self._action_buffer.pop(0)  # FIFO
```

**Expected impact**: HIGH. This directly addresses the primary cause.

### Fix 2: Frame Skip / Action Repeat

Each `env.step()` advances the game by K internal frames (e.g., K=2-3). The agent's action is applied on frame 1, then frames 2-K run with the same action. Matches the effective decision rate of the browser loop.

Can combine with action delay: action from step N applied on frame 2 of step N (1 frame delay within 3-frame skip = realistic).

**Expected impact**: HIGH. This + action delay together model the deployment conditions.

### Fix 3: Speed-Dependent Jump Velocity

```python
# In env.py step(), when starting jump:
self.trex_vy = INITIAL_JUMP_VELOCITY + self.speed / 10
```

**Expected impact**: MEDIUM. Required for high-score performance. Without this, jump timing diverges increasingly at higher speeds.

### Fix 4: Fix Observation Y Mapping

In `validate_browser.py`, change:
```python
ground_line = ground_y + 47  # groundYPos + TREX_HEIGHT
obstacle_y_bottomup = max(0, ground_line - o["y"] - o["h"])
```

**Expected impact**: MEDIUM. Required for pterodactyl survival at speed 8.5+.

### Fix 5: Match clearTime

Use 3000ms or make it configurable. Minor impact but eliminates a known difference.

### Fix 6: Domain Randomization (Optional)

Randomize action delay (0-3 frames), speed jitter, obstacle gap variance during training. Produces a more robust policy at the cost of slightly longer training.

## Alternative Approach: JS Frame-Stepping

Instead of adapting the training env to match browser latency, run Chrome's game frame-by-frame via JS injection:

```javascript
Runner.getInstance().stop();        // pause
Runner.getInstance().update(16.67); // advance exactly one frame
```

This gives frame-perfect control in Chrome, eliminating ALL timing issues. The agent trained at 1:1 frame ratio would deploy at 1:1 frame ratio. More complex to implement but sidesteps the latency problem entirely.

## Target

**Browser mean score > 555** to beat the 2023 DQN. Stretch goal: > 1000.
