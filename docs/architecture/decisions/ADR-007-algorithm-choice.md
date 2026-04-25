# ADR-007 — Learned-policy algorithm: SB3 DQN (Double-DQN, MLP `[64, 64]`)

**Date**: 2026-04-25
**Status**: Accepted
**Phase**: 1 (introduced in slice 3)
**Anchors**: [phase-1 implementation plan §3.1](../../../roadmap/phases/phase-1-implementation.md), [phase-1 design plan §0 / Story 3](../../../roadmap/phases/phase-1-design.md), [`project-history.md` § Attempt 2](../../../project-history.md), [VISION-LOCK §AC-STOP-GATE](../../vision/VISION-LOCK.md)

## Context

The phase-1 design plan deferred the algorithm choice to the implementation
plan, with three candidates on the table: DQN family (DQN, double-DQN,
dueling-DQN), PPO, and A2C. The post-mortem in
[`project-history.md`](../../../project-history.md) records two prior
implementations:

- **2023 DQN** — the only phase-1-relevant comparable. Ran at ~1 effective
  FPS due to OCR + Selenium key-event latency. Reached **mean ≈ 555**.
- **2026 v1 PPO** — trained against a Pygame sim with a transferable-only
  policy assumption. **Mean ≈ 64 real-time** despite enormous wall-clock
  investment; the sim-to-real gap was the dominant failure mode (which is
  why phase-1 fixes the env to live Chrome — not why DQN beat PPO).

Slice 1 measured live-Chrome real-time throughput at the heuristic
baseline:

- Steps/sec: order of **1–10** real-time (held-jump heuristic, capped per
  episode at 45s wall-clock; 20 episodes; mean = 401).
- The page-clock advances at ~60Hz internally but our agent ticks once
  per CDP `Input.dispatchKeyEvent` round-trip + `read_state` round-trip,
  which the slice-1 latency log places in the 30–100ms range per
  observe-decide-act loop.

The slice-3 budget is **4 hours wall-clock** (operator decision recorded
in [CURRENT-STATE.md](../../../roadmap/CURRENT-STATE.md) 2026-04-25 entry
— a tightening from the impl plan §3.6 default of 3 days). At ~5
samples/sec sustained, 4 hours yields ~72k env-steps — **below** the
impl plan §3.6 floor of 500k env-steps that gates AC-STOP-GATE
beat-baseline evaluation. Slice 3 will therefore most likely exit via
the budget-floor branch (`Stage: blocked, Blocked Kind:
awaiting-human-decision`) with eval-mean trajectory + throughput
projection as the artifact, *before* the beat-baseline gate is allowed
to fire. The algorithm choice still matters because the trajectory
recorded under the budget cap is what the human reads to decide
whether to extend.

## Decision

**Stable-Baselines3 `DQN`, configured as Double-DQN + Dueling-DQN, MLP
policy with `net_arch=[64, 64]`.**

```python
DQN(
    policy="MlpPolicy",
    env=env,
    policy_kwargs={"net_arch": [64, 64]},
    learning_rate=1e-3,
    buffer_size=100_000,           # impl §3.1 default 1M trimmed for slice-3 4h cap
    learning_starts=1_000,
    batch_size=64,
    gamma=0.99,
    train_freq=4,
    gradient_steps=1,
    target_update_interval=1_000,  # impl §3.1 default 10000 trimmed for slice-3 4h cap
    exploration_fraction=0.1,
    exploration_initial_eps=1.0,
    exploration_final_eps=0.05,
    tensorboard_log=str(LOG_DIR),
    verbose=1,
    seed=42,
)
```

Double-DQN is enabled by SB3's default `DQN` configuration (the target
estimator uses the online network for argmax + the target network for
the value, which is the double-DQN update). **Dueling-DQN was dropped
for slice 3**: SB3's vanilla `DQN` MLP policy does not expose a dueling
toggle in the installed version (2.x), and adding it requires a custom
policy class — out of scope for the 4h-cap slice. Recorded as a
slice-3 deviation; revisit in slice 4 only if the slice-3 trajectory
clearly stalls in a way that dueling's value/advantage decomposition
would address.

**Policy net**: small MLP `[64, 64]` over the 14-dim observation from
ADR-003. Total parameter count: `14 × 64 + 64 × 64 + 64 × 3 ≈ 5,184` —
well within the design-plan §3 non-goal of "≤ ~100k params."

**Slice-3 hyperparameter trims from impl §3.1 defaults** (justified by
the 4-hour cap, not by performance evidence):

| Hyperparameter | impl §3.1 / SB3 default | slice-3 4h cap value | Reason |
|---|---|---|---|
| `buffer_size` | 1,000,000 | 100,000 | At ~5 samples/sec × 4h = 72k samples max; 1M buffer wastes RAM and front-loads stale-experience risk that doesn't materialize at this budget |
| `target_update_interval` | 10,000 | 1,000 | At 72k total steps, 10k-step target updates means only ~7 target syncs across the entire run — too few for the eval-mean trajectory to reflect target-network learning |
| `learning_starts` | 50,000 | 1,000 | Same: 50k starts on a 72k budget is 70% of the run spent on uniform-random exploration |

The 1M-buffer / 10k-target-update defaults are the right choices for the
3-day cap in impl §3.1; they're wrong for the 4-hour cap. The trim is
recorded here, not silently. **If the operator extends the cap past the
4-hour budget**, the trims must be revisited in the same slice wrap that
records the extension — they are not phase-permanent decisions.

## Consequences

- `src/policy.py` exposes `LearnedPolicy.load(checkpoint_path) -> LearnedPolicy`
  and `LearnedPolicy.act(observation: np.ndarray) -> int`. The act function
  is greedy (no exploration noise at eval time): SB3's
  `model.predict(obs, deterministic=True)`.
- `scripts/eval.py` already routes `--policy=learned` through `LearnedPolicy.load`;
  the call site `loaded.act` is wrapped in slice 3 to convert the raw
  `Browser.read_state()` dict to a 14-dim observation via
  `src.env._observation_from_state` before invoking the learned policy.
  This is the eval-side adapter for the contract mismatch noted in the
  slice-3 tester report: env owns the observation construction; eval.py
  owns the dict→obs transform when serving the learned policy. Heuristic
  policy continues to consume the raw dict directly (it's a hand-coded
  rule, not an SB3 model).
- Checkpoints save as `models/<run-id>/<step>.zip` (SB3 native) plus
  sidecar `<step>.json` containing `{git_sha, hyperparameters, total_steps_so_far}`.
  The sidecar is informational only — `LearnedPolicy.load` succeeds with
  or without it (the SB3 zip is the source of truth).
- Pre-trained policy weights are **invalidated** by any of: a change to
  the observation dim (ADR-003 amendment), a change to the action-space
  cardinality (ADR-004 amendment), or a change to the MLP `net_arch`.
  The model file format is SB3-managed and includes the input/output
  shapes; SB3 raises on shape mismatch at load time.
- TensorBoard logs go to `logs/train/<run-id>/tb/`. Not load-bearing on
  any acceptance criterion; informational only.

## Alternatives considered

- **PPO** — rejected at slice-3 throughput. On-policy methods discard
  rollouts after one update; at < ~30 samples/sec, the gradient-steps
  per wall-clock-hour is dominated by sample cost, and DQN's replay
  buffer trivially wins. PPO is the credible swap target if slice-1
  throughput had measured ≥ 50 samples/sec — it did not.
- **A2C** — rejected on the same grounds as PPO (on-policy) plus weaker
  empirical track record on small-net + low-dim-feature-vector tasks
  vs DQN.
- **Plain DQN (no double-DQN)** — rejected because double-DQN is the
  default behavior of SB3's `DQN` (zero opt-in cost) and it specifically
  addresses the Q-overestimation pathology that bites small-buffer /
  few-target-update configurations like the 4h-cap-trimmed config above.
  Dueling-DQN would have been a separate flag, but as documented in
  §Decision it requires a custom policy class in SB3 2.x and was
  dropped for slice 3 — the pure-vs-double choice is the live one
  here, not the dueling toggle.
- **Larger MLP (`[256, 256]` or `[512, 512]`)** — rejected per design-plan
  §3 non-goal ("≤ ~100k params"). The 14-dim observation does not have
  the representational complexity to need 100k+ params; over-capacity
  on a small replay buffer is a known DQN failure mode (high-variance
  Q-estimates, slow convergence).
- **A separate continuous-control method (SAC, TD3)** — explicitly out
  of scope: the action space is `Discrete(3)` per ADR-004.

## Swap criterion

If slice 3 (under the 4h cap) shows the eval-mean trajectory `declining`
or `oscillating with no upward trend` across all 3 completed periodic
eval cycles, the slice-3-wrap exit branch (`awaiting-human-decision`)
surfaces three options to the operator: (a) extend the cap, (b) adjust
hyperparameters in-place under this ADR (target-update interval,
learning rate, exploration schedule — not algorithm class), or (c)
amend ADR-007 to swap to PPO. Option (c) requires this ADR to be
re-opened with the slice-3 evidence as the rationale, before any
PPO-related code lands.
