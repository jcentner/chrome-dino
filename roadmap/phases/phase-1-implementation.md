# Phase 1 — Implementation Plan

**Phase Title**: Real-time browser-native agent to MET (or honest stop)
**Status**: in-critique
**Design Plan**: [`phase-1-design.md`](phase-1-design.md) (Design Status: approved)
**Vision anchor**: [`docs/vision/VISION-LOCK.md`](../../docs/vision/VISION-LOCK.md) v1.1.0
**Post-mortem anchor**: [`project-history.md`](../../project-history.md) § "Post-Mortem: How the 2026 Run Went Off the Rails"

## 1. Overview

This plan locks the *how* for the six slices defined in [`phase-1-design.md`](phase-1-design.md) §7. The design plan locked the *what* (browser-native online RL, single Chrome instance, hand-engineered feature-vector observation, validation harness before any learning, AC-STOP-GATE at slice 5, conditional MET evaluation at slice 6). This document fixes algorithm choice, action-dispatch mechanism, the observation feature vector, action space, reward signal, module/file layout, ADR ownership, per-slice tasks and tests, and the exit branches each slice owns. Where the design plan deferred a decision, this plan either locks it now or explicitly defers it to an ADR landed during the slice that introduces the surface — never silently. No code is written by this plan; it is a binding plan for the executing stage.

## 2. Tech stack & dependencies

Pinned in [`requirements.txt`](../../requirements.txt) at slice 1; specific versions are deferred to first-write rather than guessed here.

| Dependency | Choice | Justification | ADR? |
|---|---|---|---|
| **Python** | 3.11 (CPython, Windows-native) | Matches SB3 ≥ 2.3 wheel availability and current PyTorch wheels for CUDA 12.x. 3.12 has known SB3 wheel gaps as of 2026-Q1; 3.10 is end-of-life path. | No (within tech-debt tracker if revised) |
| **Browser driver** | Selenium 4.x with the underlying CDP session reached via `driver.execute_cdp_cmd(...)`. Action dispatch uses CDP `Input.dispatchKeyEvent` (see §3); DOM read uses `driver.execute_script`. | Selenium gives us the lifecycle/launch flags; CDP gives us low-latency input that bypasses the Selenium command/HTTP round-trip for the per-step action. Vision lock permits "automation driver attached" and "read-only DOM/JS observation." | ADR-008 |
| **RL framework** | Stable-Baselines3 ≥ 2.3, Gymnasium ≥ 0.29 | DQN-family is locked (§3); SB3's DQN is the most-deployed reference implementation against this version of the Gym API. Avoids reinventing the algorithm — anti-slop. | No |
| **Numerics** | NumPy, PyTorch (CUDA 12.x, single 3070 Ti) | Required by SB3. | No |
| **Test** | `pytest` ≥ 8, `pytest-mock` | Standard. Browser-bearing tests use a `@pytest.mark.browser` marker (§7). | No |
| **Chrome** | A single pinned stable Chrome version, recorded in [`docs/setup/windows-chrome-pinning.md`](../../docs/setup/windows-chrome-pinning.md) at slice 1. Pinning mechanism: download a versioned Chrome installer to a dedicated `C:\chrome-dino-runtime\` (not the user's auto-updating Chrome); record version + SHA256 in the setup doc; eval refuses to run if the binary's reported version doesn't match. | The post-mortem and vision lock both require a reproducible `unmodified Chrome` runtime; the user's auto-updating Chrome is not reproducible. Pinning to a side-by-side install is the simplest mechanism that meets the AC-DEPLOYABILITY "fresh Windows machine" reproduction step. | No (mechanism is documented in setup doc, not an architecture decision) |
| **ChromeDriver** | Matched-major-version ChromeDriver, downloaded by URL + SHA256 verified at setup time, stored under [`chromedriver/`](../../2023-implementation/chromedriver/) (new path at repo root, not the 2023-implementation subtree). | Required to drive the pinned Chrome. | No |

Nothing in this stack requires a new stack-skill file under `.github/skills/`; SB3/Selenium/Gymnasium are not new technologies for this codebase. If slice 1 measurement forces the action-dispatch swap to `pydirectinput` or WinAPI, **that** would warrant a stack-skill before adoption (see §3 swap criterion).

## 3. Locked decisions (resolve design-plan deferrals)

### 3.1 Algorithm: DQN-family (SB3 DQN, Double + Dueling enabled)

**Locked.** Reasoning grounded in post-mortem evidence and the slice-1 throughput regime:

- Sample-throughput regime is the binding constraint. The 2023 DQN (the only deployable real-time agent in the project's history, mean ~555 per [`project-history.md`](../../project-history.md) § Attempt 2 and design plan §0) ran at ~1 effective FPS per `project-history.md`. The 2026 v1 PPO scored mean 64 real-time despite enormous wall-clock investment because its samples came from a sim that didn't transfer. Our slice-1 throughput will fall somewhere in the 1–30 FPS band depending on Selenium/CDP latency. **At < ~30 samples/sec, off-policy methods (DQN family) trivially beat on-policy methods (PPO) because they reuse experience; on-policy methods discard each rollout after one update.** PPO's headline appeal — sample efficiency *per gradient step* — is irrelevant when the limit is samples-per-wall-clock-hour, not gradient-steps-per-sample.
- Action space is discrete (§3.4) — DQN's natural fit; using PPO/A2C here means picking a continuous-friendly algorithm for a discrete problem.
- Replay-buffer-based training is friendlier to the periodic-pause-for-eval pattern (§7 risk 3) than rollout-buffer-based.
- Post-mortem doesn't argue against DQN as an algorithm class. It argues against the v1's *observation pipeline* (sim transfer collapse). DQN-on-this-env is not a re-run of v1.

Policy net: small MLP `[64, 64]` over the 14-dim observation (§3.4). Well within the §3 design non-goal of "≤ ~100k params." Captured in ADR-007.

**Swap criterion**: if slice 1 measures sustained throughput ≥ ~50 samples/sec (e.g., CDP latency under ~5ms and the page advances at 60fps and the agent ticks every 2nd frame), PPO becomes a credible alternative — at that point, on-policy pays off because gradient-step variance dominates over sample cost. Reopen via ADR-007 amendment before slice 3 begins; do not silently switch.

### 3.2 Action dispatch: CDP `Input.dispatchKeyEvent`

**Locked as the default.** Reasoning:

- The 2023 implementation explicitly cited Selenium key-event latency as a contributor to the ~1 effective FPS bottleneck (`project-history.md` § Attempt 2: "the OCR game-over detection was fragile […] every step required a browser screenshot, OCR processing, and a Selenium keyboard command"). 2023 used `pydirectinput` to bypass Selenium for input; we cannot use OS-level synthetic input because it requires window focus and breaks the moment the user alt-tabs.
- Selenium `send_keys` round-trips through the WebDriver HTTP server before reaching the page — multiple ms minimum. CDP `Input.dispatchKeyEvent`, dispatched via `driver.execute_cdp_cmd("Input.dispatchKeyEvent", {...})`, hits the same in-process page that DOM reads come from and avoids the extra hop.
- Vision lock permits attached automation drivers and read-only DOM/JS observation; CDP key dispatch is functionally equivalent to a synthetic keypress on the page (the page sees a real `KeyboardEvent`), which is what the page would receive from a human keyboard.
- Captured in **ADR-008** (slice 1).

**Swap criterion**: slice 1 measures end-to-end observe-decide-act latency. If measured CDP key-dispatch round-trip exceeds **16 ms** (one frame at 60fps) with no clear cause to mitigate, ADR-008 is amended to evaluate: (a) Selenium `send_keys` (likely worse), (b) `pydirectinput` (re-introduces the focus-fragility we're avoiding; would require a stack-skill), (c) raw WinAPI `SendInput` via `ctypes` (last resort). The §7 latency exit branch on slice 1 routes via `awaiting-human-decision`, not auto-switch.

### 3.3 Reward signal: baseline only (`+1 per step`, terminal `-100`)

**Locked as design-plan baseline. No shaping.** The design plan §3 non-goal forbids shaping beyond baseline without an ADR; this plan explicitly does not introduce one. Reasoning:

- Post-mortem identified reward shaping based on game-internal physics as a v1 over-engineering vector.
- Per-step `+1` already correlates monotonically with the page's score (the page increments score on a clock that ticks once per N frames; the agent ticks once per env-step; over an episode they're proportional up to a constant). Shaping would add tunable knobs that AC-STOP-GATE doesn't catch.
- Terminal `-100` (single-step, applied on the game-over `step()` return) provides a credit-assignment signal stronger than the per-step bonus so that bootstrapping discriminates "the action that crashed" from "the actions that survived."

The terminal `-100` magnitude is chosen so that a typical episode's cumulative reward is dominated by the survival signal (a slice-1 heuristic episode of ~500 steps yields +500 vs. one terminal -100), keeping the loss landscape scale-reasonable for the small MLP. The credit-assignment regime that matters most for DQN is *early* training, where episodes are 50–200 steps and the `-100` terminal is a strongly discriminative signal vs. the cumulative `+50`–`+200` survival reward; as the policy improves, the terminal-vs-cumulative ratio naturally drifts toward "terminal is small," which is the right shape (the policy already knows when to jump and the per-step survival signal carries the marginal improvement). If slice 4 or 5 telemetry shows the magnitude is wrong, it's tuned in-place under existing config — magnitude tuning is not "shaping" and is not ADR-gated. **Any magnitude change is recorded in the slice wrap that introduces it** (slice-N wrap states the old value, the new value, the reason, and the slice-N-evidence that motivated the change), so the audit trail is complete even without an ADR.

### 3.4 Observation feature vector (becomes ADR-003)

**Locked.** All fields are read in a single `driver.execute_script` returning a JSON-serializable dict, sourced from the Chromium dino game's globals. The game exposes its state via `Runner.instance_` (the `Runner` singleton constructed at `chrome://dino` load time); fields below are paths into that object.

| # | Feature | Source (JS path) | Purpose |
|---|---|---|---|
| 1 | `dino_y_norm` | `Runner.instance_.tRex.yPos` / canvas height | Vertical position; encodes "in the middle of a jump" without needing a velocity term. |
| 2 | `dino_jumping` | `Runner.instance_.tRex.jumping` (bool → 0/1) | Action-availability signal: jump is generally a no-op while already mid-jump. |
| 3 | `dino_ducking` | `Runner.instance_.tRex.ducking` (bool → 0/1) | Symmetric to (2) for duck. |
| 4 | `current_speed_norm` | `Runner.instance_.currentSpeed` / `Runner.config.MAX_SPEED` | Game speed; primary determinant of "when to jump." |
| 5–9 | nearest obstacle (5 fields) | `Runner.instance_.horizon.obstacles[0]` | `xPos_rel = (obstacle.xPos - tRex.xPos) / canvas_width`, `yPos_norm`, `width_norm`, `height_norm = obstacle.typeConfig.height / canvas_height`, `type_id` ∈ `{-1, 0, 1, 2}` (scalar; CACTUS_SMALL=0, CACTUS_LARGE=1, PTERODACTYL=2, no-obstacle sentinel=-1). |
| 10–14 | second-nearest obstacle (5 fields) | `Runner.instance_.horizon.obstacles[1]` | Same fields as (5–9). |

**Total: 14-dim float32 vector.** `type_id` is fed to the MLP as a **scalar**, not one-hot. Justification: with only 4 distinct values (-1, 0, 1, 2) and a 5,000-parameter MLP, one-hot encoding inflates the obstacle block from 5 to 7+ fields per obstacle (18–20 total dims) without measurable representational gain — a `[64, 64]` MLP with ReLU activations learns the categorical-not-ordinal distinction over 4 buckets in the first hidden layer. The scalar form also keeps the no-obstacle sentinel (`-1`) in the same field as the real types, avoiding a separate "obstacle present" bit. ADR-003 records the scalar choice and the 14-dim contract.

**Obstacle window width = 2 (working assumption, verified-or-amended in slice 2):** the locked window covers `obstacles[0]` and `obstacles[1]` only. The width was picked because (a) widening to 3 would add 5 mostly-sentinel dims (the 3rd slot is empty in the common case for a `[64, 64]` MLP whose capacity is already small), and (b) the post-mortem-style risk that "we narrowed something and the narrowing was the binding gap" is mitigated by the fact that the v1 narrowing failure was on the *sim's* obstacle density (which had a separate density bug), not on policy-input width — the 2023 DQN that scored ~555 had no obstacle-list at all (image input).

The planner does **not** independently verify the Chromium dino game's per-spawn gap formula here (any reference to `gap = obstacle.width * speed + minGap * gapCoefficient` in this repo traces back to [`project-history.md`](../../project-history.md) line 65, which is itself a secondary post-mortem note, not a primary Chromium source). The window-width choice is therefore explicitly **deferred to ADR-003 amendment-on-first-use during slice 2**: the slice-2 fixture-capture exercise (§6 slice 1 task 5 captures (e) and (f) — the both-slots-populated and near-crash states) is required to record, for each captured `obstacles` array, how many simultaneous obstacles the page surfaces within the planning horizon at the speeds observed. If the slice-2 fixtures (or the slice-2 random-policy `@pytest.mark.browser` integration test in §6 slice 2 task 7) observe the page surfacing ≥ 3 simultaneous obstacles within the planning horizon at game speeds, the window widens to 3 with a recompute of the observation dim (4 dino + 5 × 3 = 19) and an ADR-003 amendment landed in the same slice. If the observed maximum is consistently ≤ 2 at MET-relevant speeds, ADR-003 records width=2 with the slice-2 fixture evidence as its supporting citation. Slice 3 / 4 evidence retains the ability to widen to 3 later if the policy fails on dense clusters, but the *initial* lock is now evidence-driven, not formula-cited.

**Sentinel for "no obstacle" (post-mortem bug #2 fix, codified):** when `obstacles[i]` is undefined, the five obstacle fields take the explicit values `xPos_rel = +1.0` (off-screen-right), `yPos_norm = 0.0`, `width_norm = 0.0`, `height_norm = 0.0`, `type_id = -1` (categorically distinct from any real type, only valid in the scalar encoding above). The agent sees "no obstacle at +1.0 with type=-1" as different from "obstacle at the dino's position (xPos_rel ≈ 0.0, type ∈ {0,1,2})." This is the explicit fix for the v1 bug where 0.0 meant both "no obstacle" and "imminent collision."

**Normalization constants** (canvas dimensions, `MAX_SPEED`, etc.) are read from `Runner.config` and `Runner.instance_.dimensions` *once* at env construction, then used for every `step()` — not re-read per step (post-mortem: scattered constants were a v1 anti-pattern). They live exclusively in `src/env.py`. `grep -r` for the numeric literals is part of the slice-2 reviewer-briefed singleton check.

ADR-003 is written in slice 2 (when `src/env.py` introduces the contract). It must record the exact JS paths above, the sentinel choice, where normalization constants live, and that obstacle ordering is "by xPos ascending after filtering past-dino obstacles."

### 3.5 Action space: `Discrete(3)` — `{NOOP=0, JUMP=1, DUCK=2}`

**Locked.** Reasoning:

- Matches the game's three meaningful inputs (no-op, ArrowUp, ArrowDown).
- Avoids the 2023 implementation's two-action mistake (no duck → pterodactyls = instant death).
- Minimal — fewer actions = smaller Q-table or policy output, faster convergence for DQN.
- Captured in **ADR-004** (slice 2).

**Action → CDP key event mapping** (lives in `src/browser.py`):

**Invariant**: any state transition that ends an episode (terminal step, `reset_episode()`, env teardown, exception in `step()`/`reset()`) AND any non-`DUCK` action MUST release every held key (currently only `ArrowDown`) and clear the adapter's held-key flags *before* the transition completes or the new keys are dispatched.

This closes two related state-machine corner cases: (1) the `DUCK → JUMP` case where leaving `ArrowDown` held while pressing `ArrowUp` causes the page's input handler to interpret the press as "exit duck," producing a degraded jump (or no jump at all, depending on frame timing); and (2) the `DUCK → terminal → reset` case where a held `ArrowDown` survives across the episode boundary, leaving the new episode's first observed steps in a ducking pose the agent did not request — a silent state-distribution skew identical in shape to the post-mortem's "every file had a local justification" failure mode. Concretely, the invariant requires: the terminal `step()` releases held keys *before* returning the terminal tuple; `reset_episode()` releases held keys *before* dispatching `Space`; env teardown / exception paths release held keys in a `finally` block so a browser disconnect or assertion failure mid-action cannot leave the page in an unrecoverable held-key state.

| Action | CDP key event sequence | Notes |
|---|---|---|
| `NOOP=0` | If `ArrowDown` currently held (from prior `DUCK`), dispatch `keyUp` `ArrowDown`. Otherwise nothing. | Releases held duck. |
| `JUMP=1` | If `ArrowDown` currently held (from prior `DUCK`), dispatch `keyUp` `ArrowDown` first. Then `keyDown` `ArrowUp`, then immediately `keyUp` `ArrowUp` (within the same `step()`). | The page only needs the press edge to trigger a jump; the duck-release-first ensures the jump is read as a clean `ArrowUp` press, not as a duck exit. |
| `DUCK=2` | If `ArrowDown` not currently held, dispatch `keyDown` `ArrowDown`. Do **not** release until a non-`DUCK` action is sent. | Duck must be *held* per the Chromium game's input handling. |

This mapping means `step()` is stateful in `src/browser.py` (it remembers whether `ArrowDown` is currently held). That state is internal to the browser adapter and never appears in the observation vector — observation reflects the page's view of the world, not the adapter's internal bookkeeping. The state-machine test in slice 1 task 7 explicitly exercises the `DUCK → JUMP → DUCK` action sequence and asserts that the second `DUCK` re-presses `ArrowDown` (i.e., that the intermediate `JUMP` released it).

### 3.6 Wall-clock budget per iteration: 3 days for slice 3, 7 days each for slices 4 and 5

**Slice 3: 3 days wall-clock floor + minimum 500k env-steps OR 3 completed periodic eval cycles, whichever is greater.** Below either floor the AC-STOP-GATE beat-baseline sub-gate is **not** evaluated against slice-3 evidence — the run continues until both floors are cleared. Justification: at the §3.2 target ~30 steps/sec real-time throughput, 500k env-steps ≈ 4.6 hours of pure training; against typical SB3 DQN learning curves on small-MLP-on-low-dim-feature-vector tasks (see SB3's documented Atari/CartPole runs for order-of-magnitude reference), 50k steps is in the noise floor where even a converging agent looks indistinguishable from random initialization. 500k is the smallest round number where a `[64, 64]` MLP DQN on a 14-dim observation has had enough replay-buffer fill (default 1M, so ~50% full) and target-network updates (at default `target_update_interval=10000`, ~50 target syncs) to produce an eval-mean that is *meaningful evidence* about the algorithm rather than about under-training. The 3-eval-cycles floor (at the locked `--eval-every=50000`, that's a minimum 150k env-steps but consumes ≥3 subprocess-eval cycles' worth of trajectory data) ensures the slice-3 wrap can show an eval-mean *trend*, not a single point — necessary to distinguish "plateaued below baseline" (gate fires) from "still rising when the floor was cleared" (extend, do not fire). The 3-day wall-clock cap exists so an unrelated slowness pathology (Chrome leak, OS scheduler thrash) cannot run unbounded; if 500k steps have not been reached at 3 days wall-clock, the slice exits via the same `awaiting-human-decision` shape as the slice-1 throughput exit (artifact: per-checkpoint eval-means CSV, training-reward CSV, throughput-vs-time log, conservative projection to 500k steps).

**Slices 4 and 5: 7 days each, 14 days combined**, per the design plan §4b and §7 slice-1 throughput exit. Soft cap, revisable by the human at the §7 slice-1 throughput-exit block point. Not pinned in the vision lock; not load-bearing on AC-STOP-GATE (separate from the metric-movement gate).

### 3.7 Env step pacing: free-run, paced by the page's own clock

**Locked.** `Env.step()` is **free-run**: it dispatches the action, reads the next page state via one `execute_script` call, builds the observation, and returns. Wall-clock interval between consecutive `step()` calls = whatever observe-decide-act latency adds up to (target p99 < 16 ms per §3.2). No `time.sleep`. No frame-rate pin. No fixed-Δt pacing.

**Reasoning** (this is the live descendant of the post-mortem's central failure mode — the 60fps-train vs 51fps-deploy timing mismatch — in a no-sim world):

- **Vision-lock alignment.** "Real-time only" (binding constraint 1) means the page advances on its own clock; the agent reads, decides, acts, and the page has already advanced by whatever time the loop took. Pacing the env to a fixed rate inserts a `sleep` between the agent's action and the page's response — the opposite of "real-time." Free-run *is* the deployment condition: there is no other condition to match.
- **Robustness to jitter.** A free-run policy learns to be timing-jitter-tolerant by construction: each transition is sampled at whatever interval the loop happened to run at, so the policy's learned mapping `(observation → action)` cannot encode a hidden assumption about "obstacle displacement per step." A frame-rate-paced or fixed-Δt-paced policy can encode such an assumption — and silently break the moment a GC pause or Chrome tab-throttle slips the cadence.
- **Cost transparency.** Observe-decide-act latency is recorded per-step in slice 1 (p50/p99 in `heuristic_eval.json`). The slice-1 latency exit (§3.2) catches pathologically slow loops. Free-run keeps the latency *visible* in the eval artifact rather than buried inside `sleep` calls.
- **Cost: the agent does not see every page frame.** At ~30 steps/sec wall-clock and a 60fps page, the agent samples roughly every other frame. This is fine: the page's `currentSpeed` and obstacle positions vary continuously and predictably between frames, and the post-mortem's bug list does not include "agent missed a frame," it includes "agent learned a per-frame timing assumption that didn't hold at deploy." Free-run prevents the latter.

**Recorded in ADR-003** alongside the observation contract — "what does one step mean in real-time?" is part of the same contract as "what is in the observation vector?". ADR-003's scope explicitly covers: feature vector contents, sentinel encoding, normalization-constant location, obstacle ordering, **and step pacing (free-run)**.

## 4. Module / file layout

Locked to satisfy AC-SINGLETON's extension (one env, one train, one eval, one learned-policy, one fixed-policy). All paths are repo-relative.

```
chrome-dino/
├── src/
│   ├── __init__.py
│   ├── browser.py        # slice 1 — Selenium + CDP adapter; DOM read, key dispatch, game-over, score, episode reset, version-check. NO Gym contract.
│   ├── env.py            # slice 2 — single Gymnasium Env. Owns observation construction, normalization constants, reward, action encoding, episode-boundary logic.
│   ├── heuristic.py      # slice 1 — single fixed-policy module. Frozen speed-adaptive rule. Used by eval as sanity baseline.
│   └── policy.py         # slice 3 — single learned-policy module. Wraps SB3 DQN model load + .act(obs).
├── scripts/
│   ├── eval.py           # slice 1 — single eval entry point. CLI flags select policy {heuristic, learned} and checkpoint. Refuses on Chrome/ChromeDriver version mismatch.
│   ├── train.py          # slice 3 — single training script. Periodically subprocess-invokes scripts/eval.py.
│   └── capture_fixtures.py  # slice 1 — utility to dump DOM-state JSON snapshots for slice-2 unit tests. NOT a second eval entry point.
├── tests/
│   ├── conftest.py       # slice 1 — shared fixtures, browser marker registration.
│   ├── fixtures/
│   │   └── dom_state/    # slice 1 captures, slice 2 consumes — committed JSON snapshots.
│   ├── test_browser.py   # slice 1
│   ├── test_eval_artifact_schema.py  # slice 1
│   ├── test_env.py       # slice 2
│   ├── test_policy.py    # slice 3
│   └── test_train_cli.py # slice 3
├── chromedriver/
│   └── (binary + sha256, gitignored if too large; URL pinned in setup doc)
├── docs/
│   ├── setup/
│   │   └── windows-chrome-pinning.md  # slice 1
│   └── architecture/decisions/
│       ├── ADR-001-approach.md
│       ├── ADR-002-platform.md
│       ├── ADR-003-observation-space.md
│       ├── ADR-004-action-space.md
│       ├── ADR-005-validation-harness.md
│       ├── ADR-006-singleton-rule.md
│       ├── ADR-007-algorithm-choice.md
│       └── ADR-008-action-dispatch.md
├── logs/
│   ├── slice1/heuristic_eval.json
│   ├── slice1/manual_count.md
│   ├── slice3/learned_eval.json
│   ├── slice4/learned_eval.json
│   ├── slice5/learned_eval.json
│   └── slice6/met_eval.json
├── models/
│   └── .gitkeep          # slice 3
└── pytest.ini            # slice 1 — registers `browser` marker, default `-m "not browser"`.
```

**Module ownership boundaries:**

- `src/browser.py` owns Chrome lifecycle, CDP/key dispatch, raw DOM read, game-over detection, score read, episode reset (page reload + game start), version verification. It has **no** Gymnasium dependency and **no** observation construction.
- `src/env.py` owns the Gymnasium `Env` contract. It calls into `src/browser.py` for raw page state and translates that to the locked 14-dim observation. It owns reward computation, action encoding (which forwards to `browser.send_action()`), terminal detection, and *all* normalization constants. No other module hard-codes a normalization constant.
- `src/heuristic.py` owns the frozen speed-adaptive rule. Single function-shaped surface: `act(observation: np.ndarray) -> int` returning a `Discrete(3)` action. No internal state.
- `src/policy.py` owns the learned-policy surface: `LearnedPolicy.load(path: str) -> LearnedPolicy` plus `act(observation: np.ndarray) -> int`. Wraps an SB3 model; `eval.py` and `train.py` both go through this surface, never through `stable_baselines3` directly.
- `scripts/eval.py` owns evaluation. Selects policy by CLI flag (`--policy {heuristic, learned}`); produces the canonical raw-per-episode-score artifact.
- `scripts/train.py` owns training. Calls `scripts/eval.py` as a subprocess for periodic evaluation (does **not** import or duplicate eval logic).
- `scripts/capture_fixtures.py` owns fixture capture. It drives `src/browser.py` (NOT `src/env.py`, which doesn't exist yet at slice 1) and writes raw DOM-state snapshots.

**What this layout deliberately excludes** (post-mortem-anchored):

- No `src/utils.py` / `src/common.py` grab-bag. If a helper is needed by multiple modules, name what it does and put it where it belongs.
- No `src/observation.py` separate from `src/env.py`. Observation construction is part of the env contract.
- No `src/replay_buffer.py` / `src/agent.py`. SB3 owns these.
- No `tests/integration/` vs `tests/unit/` directory split. Pytest markers (`@pytest.mark.browser`) carry the distinction; a directory split would invite duplication.

## 5. ADRs to land

Each ADR is written in the slice that introduces the surface it documents. The reviewer at slice review checks the ADR exists. Format follows the existing template in [`docs/architecture/decisions/`](../../docs/architecture/decisions/) — context, decision, consequences, alternatives considered.

| ADR | Title | Slice | Source |
|---|---|---|---|
| ADR-001 | Approach choice (browser-native online RL, single Chrome, no headless sim) | Slice 1 | Design plan §5; captures the §0 candidate-set comparison. |
| ADR-002 | Platform choice (Windows-native, not WSL2) | Slice 1 | Design plan §5; vision lock § Operational definitions. |
| ADR-003 | Observation space (14-dim feature vector + DOM read mechanism + step pacing) | Slice 2 | This plan §3.4 and §3.7. |
| ADR-004 | Action space (`Discrete(3)`: NOOP/JUMP/DUCK + key-event mapping) | Slice 2 | This plan §3.5. |
| ADR-005 | Validation harness shape (single eval script, real-time only, episode-boundary detection, score-readout extraction, pinned versions, artifact format) | Slice 1 | Design plan §5; AC-HARNESS. |
| ADR-006 | Singleton infra rule operationalized (file-existence check at slice review) | Slice 1 | Design plan §5; AC-SINGLETON. |
| ADR-007 | Algorithm choice (SB3 DQN with Double + Dueling, small MLP) | Slice 3 | This plan §3.1. |
| ADR-008 | Action dispatch (CDP `Input.dispatchKeyEvent`, swap criterion documented) | Slice 1 | This plan §3.2; informed by slice-1 latency measurement. |

No further ADRs are planned in advance. Anything emerging during execution that meets "significant design choice with a reason" is added at the slice that introduces it (per [`copilot-instructions.md`](../../.github/copilot-instructions.md) § Coding conventions). The reward-magnitude tuning case in §3.3 explicitly does **not** require an ADR; reward *shaping* (any change to the reward function's *shape*, not its scalar magnitude) does.

## 6. Per-slice implementation plan

### Slice 1 — Real-time validation harness + heuristic sanity baseline

**Files added**: `src/__init__.py`, `src/browser.py`, `src/heuristic.py`, `scripts/eval.py`, `scripts/capture_fixtures.py`, `tests/conftest.py`, `tests/test_browser.py`, `tests/test_eval_artifact_schema.py`, `tests/fixtures/dom_state/` (populated by capture run), `pytest.ini`, `requirements.txt`, `chromedriver/.gitkeep`, `docs/setup/windows-chrome-pinning.md`, `docs/architecture/decisions/ADR-001-approach.md`, `ADR-002-platform.md`, `ADR-005-validation-harness.md`, `ADR-006-singleton-rule.md`, `ADR-008-action-dispatch.md`, `logs/slice1/heuristic_eval.json`, `logs/slice1/manual_count.md`.

**Tasks (ordered):**

1. **Pin runtime versions.** Pick a current stable Chrome version; download the matching ChromeDriver to `chromedriver/`; record version IDs, download URLs, and SHA256 of both binaries in `docs/setup/windows-chrome-pinning.md`. Document the side-by-side install path so the eval doesn't accidentally launch the user's auto-updating Chrome.
2. **Implement `src/browser.py`** — Selenium WebDriver launch against the pinned binary; navigate to `chrome://dino`; trigger offline mode (default approach: navigate to an unreachable URL like `http://chrome-dino-offline.invalid/`; CDP `Network.emulateNetworkConditions(offline=true)` is the fallback if the navigate-trigger flakes). Implement: `read_state()` returning the §3.4 raw dict via one `execute_script` call; `send_action(action: int)` using CDP `Input.dispatchKeyEvent` per §3.5; `is_game_over()` reading `Runner.instance_.crashed`; `get_score()` reading `Math.floor(Runner.instance_.distanceRan * Runner.config.COEFFICIENT)` (the same formula the page uses to render the on-screen integer); `reset_episode()` (per §3.5 invariant: if the adapter's `ArrowDown` held-flag is true, dispatch `keyUp ArrowDown` and clear the flag; *then* dispatch `Space`; *then* wait for `Runner.instance_.playing` to flip true); `version_check()` (compares the running Chrome's `navigator.userAgent` major version to the pinned major; raises `VersionMismatchError`); `close()` / context-manager `__exit__` (per §3.5 invariant: release any held keys in a `finally` block before quitting the driver, so an abnormal exit cannot leave the page in a held-key state on the next launch against the same profile).
3. **Implement `src/heuristic.py`** — single `act(observation)` function. Rule: if `obstacle[0].type_id` is PTERODACTYL and at high y → NOOP; else if obstacle is overhead-low → DUCK; else if `xPos_rel < threshold(speed)` (linear-in-speed threshold) → JUMP; else NOOP. Frozen — no parameters tuned during this phase.
4. **Implement `scripts/eval.py`** — CLI: `--policy {heuristic, learned}`, `--episodes` (default 20), `--checkpoint` (required for `learned`), `--out` (artifact path). Runs version-check first; refuses on mismatch. Per step, records timestamps for `read_state` start, policy `act` start, `send_action` start, `send_action` complete; per episode logs final score, episode length, wall-clock duration, page-clock at game-over (`Runner.instance_.time`), wall-clock-vs-page-clock delta at game-over. Writes JSON artifact: `{ "metadata": {chrome_version, chromedriver_version, git_sha, policy, checkpoint, run_started_at}, "episodes": [ {score, steps, wall_seconds, page_seconds_at_gameover, gameover_detection_delay_ms, per_step_latency_ms_p50, per_step_latency_ms_p99}, ... ] }`.
5. **Implement `scripts/capture_fixtures.py`** — drives one heuristic episode; every 10th step calls `browser.read_state()` and dumps the raw dict to `tests/fixtures/dom_state/ep<N>_step<M>.json`. Includes captures specifically targeting: (a) a normal mid-episode state, (b) a state mid-jump, (c) a state mid-duck, (d) a state with `obstacles == []`, (e) a state with both obstacle slots populated, (f) a transient near-crash state (last few steps before terminal), (g) the terminal state itself (`crashed: true`).
6. **Run eval against heuristic for 20 episodes**, commit `logs/slice1/heuristic_eval.json`. Run AC-HARNESS manual count: human plays the recording back / watches 5 episodes live and records the page's displayed final score in `logs/slice1/manual_count.md`. Per AC-HARNESS, harness score must be exact-match (or lower by ≤ 1 score-tick). Compute throughput (steps/sec, episodes/hr), latency (p50, p99), and game-over detection delay across the 20 episodes; record in slice-1 wrap.
7. **Write ADR-001, ADR-002, ADR-005, ADR-006, ADR-008.** ADR-008 includes the slice-1-measured CDP latency as the supporting evidence for "default to CDP."

**Tests:**

- `tests/test_browser.py`: `version_check()` raises on simulated mismatch (mock the `navigator.userAgent` read); `send_action` dispatches the documented CDP method (mock `execute_cdp_cmd`); the duck-key release-on-non-duck state machine is exercised against a sequence of action ints; specifically, a `DUCK → JUMP → DUCK` sequence asserts (a) the intermediate `JUMP` dispatches a `keyUp ArrowDown` *before* the `ArrowUp` press, and (b) the second `DUCK` re-presses `ArrowDown` (i.e., the adapter recognizes that the held state was cleared by the intermediate `JUMP`). **Episode-boundary held-key release** (§3.5 invariant): a `DUCK → terminal → reset_episode() → JUMP` sequence asserts (a) the terminal step releases `ArrowDown` before returning, (b) `reset_episode()` does not dispatch `Space` while `ArrowDown` is held, and (c) the post-reset `JUMP` produces a clean `keyDown/keyUp ArrowUp` with no spurious `keyUp ArrowDown` (because the held flag was already cleared at the boundary). **Teardown release**: a test where `Browser` is used as a context manager and exits while `ArrowDown` is held asserts that `keyUp ArrowDown` is dispatched in the `finally`/`__exit__` path before `driver.quit()`. All unit, no live browser.
- `tests/test_eval_artifact_schema.py`: a frozen JSON-schema-style check on the artifact format from task 4 (so slice 6's MET artifact is guaranteed to match).
- `tests/test_browser.py::test_one_short_episode` — `@pytest.mark.browser`, opt-in. Launches Chrome, runs 100 steps with the heuristic, asserts no exceptions and an artifact-schema-conformant single-episode dict.
- Tester-isolation note: tests are derivable from this §6 spec and ADR-005 alone; tester does not need to read `src/browser.py` source.

**Evidence for slice review:**

- `logs/slice1/heuristic_eval.json` (raw 20 scores, full per-step timing log).
- `logs/slice1/manual_count.md` (5-episode page-displayed-score log + AC-HARNESS pass/fail per episode).
- Slice-1 wrap section: measured throughput (steps/sec, episodes/hr), measured p50/p99 observe-decide-act latency, measured game-over detection delay (page-clock vs wall-clock), projected wall-clock for two RL iterations at this throughput.
- `pytest -m "not browser"` pass count and `pytest -m browser` pass count.
- ADR files present.

**Exit branches (any one routes to `Stage: blocked` BEFORE slice 2 begins):**

- **Throughput exit**: if `2 * (target_episodes_per_iteration / measured_episodes_per_hour) > 14 days * 24 hours`, transition to `Stage: blocked, Blocked Kind: awaiting-human-decision`. Artifact: the throughput projection table, raw timing log. Not routed via AC-STOP-GATE.
- **Latency exit**: if measured CDP key-dispatch round-trip p99 > 16 ms sustained, transition to `Stage: blocked, Blocked Kind: awaiting-human-decision` per §3.2 swap criterion. Artifact: per-step latency log, ADR-008 amendment proposal.
- **Heuristic-stronger-than-expected exit**: if heuristic eval-mean ≥ ~1500 (within plausible reach of MET), transition to `Stage: blocked, Blocked Kind: awaiting-human-decision` per design §7. Artifact: `heuristic_eval.json` + raw per-episode distribution. Reopens design-plan option C.
- **AC-HARNESS fail**: any spot-check episode shows harness/page score gap > 1 score-tick → slice does not pass; do not advance. This is a slice-failure-doesn't-pass exit, not a `blocked` transition — fix the score-readout bug, re-run, re-spot-check.

### Slice 2 — Env contract (observation, action, reward) on captured fixtures

**Files added**: `src/env.py`, `tests/test_env.py`, `docs/architecture/decisions/ADR-003-observation-space.md`, `ADR-004-action-space.md`. **Files modified**: `tests/fixtures/dom_state/` (re-used; no new captures).

**Tasks (ordered):**

1. Write ADR-003 and ADR-004 from §3.4 / §3.5 of this plan; have them in the same commit as `src/env.py`.
2. Implement `src/env.py` as a `gymnasium.Env` subclass: `observation_space = Box(low=-inf, high=+inf, shape=(14,), dtype=float32)`; `action_space = Discrete(3)`. Constructor takes a `Browser` instance (dependency injection — enables fixture-driven tests via a `FakeBrowser` that returns canned `read_state()` dicts).
3. Implement `_observation_from_state(raw_state: dict) -> np.ndarray` — the pure function from raw DOM dict to 14-dim float32 vector. Owns the §3.4 sentinels and normalization. Pure, no I/O — fully unit-testable against the slice-1 fixtures.
4. Implement `step(action)`: forward action to browser; read new state; build observation; compute reward (`+1.0`, or `-100.0` if terminal); detect terminal via `raw_state["crashed"]`; return `(obs, reward, terminated=crashed, truncated=False, info={"score": page_score})`. Action ignored if game is already in the terminal state — env does not crash, surfaces a no-op terminal step.
5. Implement `reset(seed=None, options=None)`: call `browser.reset_episode()`, read initial state, return `(obs, info)`.
6. Write `tests/test_env.py` against the slice-1-captured fixtures (no live browser): observation extraction (one test per fixture file); reward computation (per-step `+1`, terminal `-100`); action encoding (each of 3 actions produces the expected `browser.send_action` call on a mock browser); terminal detection (terminal fixture → `terminated == True`; pre-terminal transient fixture → `terminated == False`); sentinel handling (no-obstacle fixture → observation has the exact sentinel values from §3.4).
7. Add an integration test (`@pytest.mark.browser`): random policy for one full episode against a real browser; assert exactly one terminal step; assert episode length > 0; assert episode produces a non-trivial observation history.
8. Run `grep -rn '0\.025\|MAX_SPEED\|canvas_width' src/ scripts/` to confirm no normalization constant is duplicated outside `src/env.py`. Record output in slice-2 wrap.

**Tests:** see tasks 6 and 7. Tester writes from this §6 spec + ADR-003 + ADR-004 + design plan §6 (test strategy) — does not read `src/env.py` source. Fixture filenames + their documented purpose (mid-jump, no-obstacle, terminal, etc.) are sufficient to derive the test cases.

**Evidence for slice review:**

- `pytest -m "not browser"` pass count for `tests/test_env.py` (must exercise all listed cases).
- `pytest -m browser tests/test_env.py::test_random_policy_episode` pass.
- `grep` output from task 8 (must show normalization constants only in `src/env.py`).
- ADR-003 and ADR-004 present.
- AC-SINGLETON re-check: `ls src/` and `ls scripts/` showing no duplicates.

**Exit branches:** none specific to slice 2; any failure here is a slice-doesn't-pass condition that the builder fixes in place. The phase does not exit to `blocked` from slice 2.

### Slice 3 — Training script + first learned eval

**Files added**: `src/policy.py`, `scripts/train.py`, `tests/test_policy.py`, `tests/test_train_cli.py`, `models/.gitkeep`, `docs/architecture/decisions/ADR-007-algorithm-choice.md`, `logs/slice3/learned_eval.json`, `logs/train/<run-id>/` (training-side reward csv, periodic eval-mean log).

**Tasks (ordered):**

1. Write ADR-007 from §3.1 of this plan.
2. Implement `src/policy.py`: `class LearnedPolicy`, `load(checkpoint_path: str) -> "LearnedPolicy"` (loads SB3 zip + sidecar JSON), `act(observation: np.ndarray) -> int`. Single surface for the learned policy.
3. Implement `scripts/train.py`: instantiate one `Browser`, one `Env`, one SB3 `DQN(policy="MlpPolicy", env=env, policy_kwargs={"net_arch": [64, 64]}, ...)` with double-q + dueling enabled; train for `--total-steps`. Hyperparameters (replay buffer size, train freq, target update interval, exploration schedule) committed in a config block in the script — not a separate config file (avoids the "config dir → multiple configs → which is canonical" failure mode). Save checkpoints every `--ckpt-every` steps to `models/<run-id>/<step>.zip` plus sidecar JSON `{git_sha, hyperparameters, total_steps_so_far}`.
4. Periodic eval: every `--eval-every` env-steps, pause training, `subprocess.run(["python", "scripts/eval.py", "--policy", "learned", "--checkpoint", latest_path, "--episodes", "20", "--out", periodic_out])`. Append the resulting eval-mean to `logs/train/<run-id>/eval_means.csv`. Resume training. (Subprocess approach chosen over in-process re-use to keep training-Chrome and eval-Chrome state cleanly isolated; see §8 risk 3.) **Default `--eval-every = 50000` env-steps** for the first iteration (slice 3): each subprocess eval is a Chrome cold-launch + `chrome://dino` navigate + offline-trigger (~5–10s) + 20 episodes, so cadence directly trades wall-clock against eval-curve resolution. At 50k cadence and ~30 steps/sec real-time throughput, eval fires roughly every ~30 minutes and consumes order-of 5–10% of slice-3 wall-clock for eval overhead. Refinable based on slice-3 measured throughput; the slice-3 wrap records the cadence actually used and its share of slice-3 wall-clock, so slices 4/5 can re-tune.
5. Run training until **both** of the §3.6 slice-3 floors are cleared: ≥ 500k env-steps trained AND ≥ 3 completed periodic eval cycles, capped at 3 days wall-clock. Below either floor, do **not** evaluate the AC-STOP-GATE beat-baseline sub-gate against slice-3 evidence — continue training. If the 3-day wall-clock cap is hit before 500k env-steps, exit via `Stage: blocked, Blocked Kind: awaiting-human-decision` with the throughput-projection / eval-trajectory artifact described in §3.6, *not* by firing the beat-baseline gate. Once both floors are cleared, commit the latest periodic eval as `logs/slice3/learned_eval.json` (re-running the eval at slice end against the best checkpoint).
6. Slice-3 wrap reports — explicitly and separately: **(a)** total env-steps trained, **(b)** total completed periodic eval cycles, **(c)** wall-clock consumed, **(d)** the full eval-mean trajectory across the periodic evals (the `eval_means.csv` series, summarized inline as a min / median / max / last-value table and a one-line trend characterization: rising / plateaued / oscillating / declining), **(e)** training-side reward curve summary, **(f)** slice-3 eval-mean, **(g)** slice-3 eval-mean vs slice-1 heuristic eval-mean (the beat-baseline gate decision), **(h)** explicit pass/fail of each §3.6 floor at slice end.

**Tests:**

- `tests/test_policy.py`: checkpoint round-trip (save tiny SB3 model, load via `LearnedPolicy.load`, call `act` on a synthesized 14-dim observation, assert returned int in `{0, 1, 2}`); `LearnedPolicy.load` raises informatively on a missing or non-SB3 checkpoint.
- `tests/test_train_cli.py`: `python scripts/train.py --help` exits 0 and the help text mentions `--total-steps`, `--eval-every`, `--ckpt-every`; required flags raise on missing values.
- No test invokes a live training run end-to-end (too slow for unit/integration). The training run itself is the slice-3 evidence.
- Tester-isolation note: tester writes both files from §6 + ADR-007 + the policy-module surface in §4. Does not read `src/policy.py` or `scripts/train.py` source.

**Evidence for slice review:**

- `logs/slice3/learned_eval.json` (raw 20 scores from latest checkpoint).
- `logs/train/<run-id>/eval_means.csv` showing periodic eval-means recorded during training.
- `logs/train/<run-id>/training_reward.csv` showing training-side reward (informational, not load-bearing).
- Slice-3 wrap stating: slice-3 eval-mean, slice-1 heuristic eval-mean, explicit pass/fail of the beat-baseline gate.
- ADR-007 present.

**Exit branches:**

- **Slice-3 budget-floor exit (precedes any gate evaluation):** if 3 days wall-clock elapse and either §3.6 floor (≥ 500k env-steps OR ≥ 3 completed periodic eval cycles) is unmet, transition to `Stage: blocked, Blocked Kind: awaiting-human-decision`. Artifact: per-checkpoint eval-means CSV, training-reward CSV, throughput-vs-time log, conservative projection of when both floors would have been cleared. The beat-baseline gate is **not** evaluated on under-floor evidence.
- **Beat-baseline gate (AC-STOP-GATE sub-gate, fires here for the first time, only after both §3.6 floors are cleared):** if slice-3 eval-mean ≤ slice-1 heuristic eval-mean AND the eval-mean trajectory characterization is `plateaued` or `declining` (i.e., the gate distinguishes "trained enough and still didn't beat baseline" from "trained enough and still rising — extend"), transition to `Stage: blocked, Blocked Kind: awaiting-human-decision` BEFORE slice 4 begins. Artifact: per-episode score distributions for both runs, the eval-mean trajectory from task-6 item (d), slice-3 wrap explicitly stating gate fired.

### Slice 4 — One bounded training iteration

**Files added**: `logs/slice4/learned_eval.json`, `logs/train/<run-id-2>/`. **Files modified**: `scripts/train.py` (in-place config-block edit; **NOT** a new `train_v2.py` — any duplication requires a fresh ADR before the duplicate file exists, per AC-SINGLETON).

**Tasks (ordered):**

1. Inspect slice-3 evidence: training reward curve, periodic eval-means, per-episode score distribution. Identify exactly one bounded change. Candidate categories: hyperparameter (e.g., learning rate, replay buffer size, target update interval, train_freq, exploration epsilon schedule), or — if a gap in the observation is plausibly causing failure — *one* observation refinement (e.g., adding obstacle velocity); the latter would require an ADR-003 amendment. Prefer hyperparameter changes (no ADR delta) for slice 4, leaving observation changes for slice 5 if hyperparameter tuning didn't move the metric.
2. Document the change in slice-4 wrap with the rationale (citing the slice-3 evidence that motivated it). Exactly one change.
3. Re-run training. Default: warm-start from the slice-3 best checkpoint (`--init-from <path>` flag added to `scripts/train.py` for this purpose; this is the in-place edit). Cold restart is permitted but must be justified in the wrap.
4. Commit `logs/slice4/learned_eval.json` (final eval against best slice-4 checkpoint, 20 raw scores).
5. Compute and record in slice-4 wrap: slice-3 → slice-4 eval-mean delta absolute and relative; slice-4 eval-mean vs slice-1 heuristic eval-mean.

**Tests:** all slice-1, slice-2, slice-3 tests still pass. No new tests required — slice 4 doesn't add a new public surface.

**Evidence for slice review:**

- `logs/slice4/learned_eval.json`.
- Slice-4 wrap with: the one bounded change, its rationale, slice-3 → slice-4 delta (absolute + relative), per-episode distributions for both, beat-baseline check.

**Exit branches:**

- **Beat-baseline gate (still active):** if slice-4 eval-mean ≤ slice-1 heuristic eval-mean, transition to `Stage: blocked, Blocked Kind: awaiting-human-decision` BEFORE slice 5 begins.
- Movement gate is *not* evaluated alone after slice 4 — it requires both deltas (slice-3 → slice-4 AND slice-4 → slice-5), so the formal evaluation is at end of slice 5. Slice-4 wrap forewarns slice 5 if movement is already weak.

### Slice 5 — Second bounded training iteration + AC-STOP-GATE end-to-end check

**Files added**: `logs/slice5/learned_eval.json`, `logs/train/<run-id-3>/`. **Files modified**: `scripts/train.py` (in-place again, second bounded change).

**Tasks (ordered):**

1. Same shape as slice 4: one bounded change, documented rationale, retrain, eval, record delta.
2. Commit `logs/slice5/learned_eval.json`.
3. **Evaluate AC-STOP-GATE end-to-end** in the slice-5 wrap:
   - **Beat-baseline gate**: is `slice5_mean > slice1_heuristic_mean`?
   - **Movement gate**: did *either* (slice-3 → slice-4) *or* (slice-4 → slice-5) clear *both* `≥ +10% relative` *and* `≥ +50 absolute`?
   - If beat-baseline fails OR movement fails → gate fires.
4. Slice-5 wrap explicitly documents the gate decision, the per-episode distributions for slices 3/4/5, and the slice-1 heuristic baseline.

**Tests:** same as slice 4 — all prior tests still pass. No new tests.

**Evidence for slice review:**

- `logs/slice5/learned_eval.json`.
- Slice-5 wrap with: gate-evaluation table (slice numbers, deltas absolute/relative, both sub-gates pass/fail, gate-fired yes/no, decision: proceed-to-slice-6 or block).
- Per-episode score distributions for slices 3, 4, 5 (so the gate decision is on signal, not on a single-outlier-driven mean).

**Exit branches:**

- **Gate fires** (beat-baseline OR movement) → transition to `Stage: blocked, Blocked Kind: awaiting-human-decision`. Phase ends here. Strategic re-plan happens out of this phase.
- **Gate does not fire AND slice-5 eval-mean < ~1500** → transition to `Stage: blocked, Blocked Kind: awaiting-human-decision` per design §7 slice 6 precondition. Phase ends. Slice 6 does not run.
- **Gate does not fire AND slice-5 eval-mean ≥ ~1500** → proceed to slice 6.

### Slice 6 — MET evaluation + phase wrap (CONDITIONAL)

**Precondition** (per design §7 and slice-5 exit branches): AC-STOP-GATE did not fire through slice 5 AND slice-5 eval-mean ≥ ~1500.

**Files added**: `logs/slice6/met_eval.json`, `roadmap/phases/phase-1-wrap.md`, `models/best/<frozen-checkpoint>.zip` (the committed frozen checkpoint), `models/best/<frozen-checkpoint>.json` (sidecar metadata).

**Tasks (ordered):**

1. Pick the best checkpoint by eval-mean across all periodic evals from slices 3, 4, 5. Copy it to `models/best/`.
2. Run `python -m scripts.eval --policy learned --checkpoint models/best/<...>.zip --episodes 20 --out logs/slice6/met_eval.json` (the canonical eval entry point, same script as slice 1 / 3 / 4 / 5).
3. Verify metadata in the artifact: pinned Chrome version matches, pinned ChromeDriver version matches, no flag combination disables real-time play.
4. Manual sanity-watch: a human watches at least one full episode in the Chrome window, confirms the agent looks like real-time play (no frame stepping, no slow-mo, no warp).
5. Compute mean over the 20 raw scores. Check `≥ 2000`.
6. Write `roadmap/phases/phase-1-wrap.md`: AC-MET pass/fail with the artifact path cited; AC-HARNESS pass status (carried from slice 1); AC-SINGLETON pass status (`ls src/` and `ls scripts/` outputs); AC-STOP-GATE status (whether it fired during the phase, and if so why slice 6 still ran); AC-DEPLOYABILITY pass status (cite the setup doc + the canonical `python -m scripts.eval ...` command). Reference the committed checkpoint, raw per-episode score array, Chrome/ChromeDriver versions, and eval entry point from one section.

**Tests:** the e2e test is the eval script itself — `logs/slice6/met_eval.json` is the test output.

**Evidence for slice review:**

- `logs/slice6/met_eval.json` with 20 raw real-time scores in unmodified Chrome on Windows.
- `models/best/<frozen-checkpoint>.zip` + sidecar JSON.
- `roadmap/phases/phase-1-wrap.md` with the AC table.
- Manual sanity-watch log (one paragraph in the wrap).

**Exit branches:**

- **AC-MET met** (mean ≥ 2000) → propose phase 2 in the wrap; transition to `Stage: cleanup` then onward per the standard pipeline.
- **AC-MET not met** → transition to `Stage: blocked, Blocked Kind: awaiting-human-decision`. Wrap explicitly states MET not achieved. Vision lock is **not** amended to fit the achieved number (binding constraint 4).
- **Eval crashes mid-run** (e.g., on episode 14 of 20) → artifact is not partially counted; re-run from a fresh state, or MET is not claimed (per design §1 story 6 edge cases).

## 7. Test strategy detail

### Fixture-capture utility (slice 1 → slice 2 handoff)

`scripts/capture_fixtures.py` is the bridge that lets slice 2 unit-test `src/env.py` without launching a browser. It runs the heuristic for one episode and dumps `Browser.read_state()`'s raw dict at every Nth step (default N=10), targeting the case-coverage list in §6 slice 1 task 5. Files land in `tests/fixtures/dom_state/ep<N>_step<M>.json` and are committed.

**Anti-staleness**: fixtures are tied to a specific Chrome/ChromeDriver version pair. The fixture file format includes a top-level `chrome_version` and `chromedriver_version` field; `tests/test_env.py` loads them and *warns* if the live pinned versions don't match (does not fail — fixture refresh is a separate task). If a fixture refresh is needed, re-run `scripts/capture_fixtures.py`; the `tests/fixtures/dom_state/` directory is overwritten in one commit.

### Live-browser tests (the `browser` marker)

`pytest.ini`:

```
[pytest]
markers =
    browser: requires a live Chrome/ChromeDriver. Slow. Default: skip.
addopts = -m "not browser"
```

To run browser-bearing tests: `pytest -m browser`. To run everything: `pytest -m "browser or not browser"`. CI (if added later) opts in via a workflow input flag rather than running them on every push.

### pytest layout

Flat: `tests/conftest.py` at root, all test files at `tests/test_*.py`, fixtures under `tests/fixtures/`. No `tests/unit/` vs `tests/integration/` split — markers carry that distinction and a directory split would tempt duplication of helper code.

### Tester-isolation compliance

Per the tester subagent's isolation rules ([copilot-instructions.md](../../.github/copilot-instructions.md) tier-1 enforcement), the tester writes tests from spec, not from implementation. Each slice's tests above are derivable from this plan §6 + the relevant ADRs + the design plan §6 — none require reading `src/` source. Concretely:

- Slice 1: spec is §6 slice 1 + ADR-005 (artifact format) + ADR-008 (CDP method name).
- Slice 2: spec is §6 slice 2 + ADR-003 (each observation dim, sentinels) + ADR-004 (action mapping) + this plan §3.3 (reward).
- Slice 3: spec is §6 slice 3 + ADR-007 (DQN choice) + the `LearnedPolicy` surface in §4.

## 8. Implementation-specific risks (separate from design-plan §4)

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Chrome auto-update breaks pinned ChromeDriver mid-phase**, or the user's default Chrome shadows the pinned install. | Medium-High | All slice numbers become non-reproducible; AC-DEPLOYABILITY at risk. | Pin Chrome to a side-by-side install in a dedicated path (`C:\chrome-dino-runtime\`), document Windows-policy-based auto-update disable for that install, eval refuses to run if `navigator.userAgent` major doesn't match the pinned major. Setup doc covers fresh-machine reproduction. |
| 2 | **Score-tick sampling race**: the harness may sample score *just before* the page renders the final score-tick, then detect game-over, missing one tick. | Medium | AC-HARNESS allows ≤ 1 score-tick gap (per design §2); systematic gap > 1 tick fails the slice. | `Browser.get_score()` is called *after* `is_game_over()` returns true on the terminal step (read final `distanceRan` from the crashed runner), not before. Documented in ADR-005. Slice-1 manual count verifies. |
| 3 | **Training-eval Chrome re-entrancy**. The vision-lock binding constraint 3 forbids "second instance of any of these" without ADR; sub-process eval during training launches a second Chrome process — same browser binary, same pinned version, but a second process. | Medium | Either (a) a second Chrome process is treated as "one Chrome" for vision purposes (because they're never *concurrent* — training pauses while eval runs), in which case fine; or (b) treated as "two Chromes," in which case ADR required. | **Default interpretation**: serial sub-process eval is *one Chrome instance at a time*, just relaunched — analogous to running eval after training, which is uncontroversial. The vision-lock concern is multi-Chrome-*instance-parallelism* (constraint 3 paired with §3 design non-goal "no multi-Chrome-instance parallelism"). If the critic disagrees, fall back to: in-process eval that re-uses the training-Chrome (training paused, eval driven from the same `Browser` instance, env left untouched). Decision recorded in slice-3 wrap. |
| 4 | **CDP key dispatch interpreted as page modification**. Vision lock permits "automation driver attached" but constrains "no injected JavaScript that mutates game state." A `KeyboardEvent` injected via CDP is a synthetic input, not a JS state mutation, but the boundary is fuzzy. | Low | If interpreted strictly, action dispatch is illegal under the vision lock. | ADR-008 explicitly argues the interpretation: a synthetic `KeyboardEvent` is what a human keyboard produces, the page handles it through its normal input handler, no state field is set directly. If the critic challenges, fall back to OS-level synthetic input (`pydirectinput`/WinAPI) — same observable effect on the page, OS-side input rather than browser-side. |
| 5 | **SB3 + Gymnasium API drift between pin and a needed bugfix**. SB3 has had breaking API changes across minors. | Low-Medium | Could force a mid-phase upgrade with regression risk. | Pin tight in `requirements.txt` (`==`, not `>=`) for SB3 and Gymnasium for the duration of phase 1. Upgrades happen between phases, not within. |
| 6 | **`Runner.instance_` JS API changes between Chrome versions**. The dino game's source can change. | Low (within one pinned version) / Medium (across upgrades) | Observation extraction breaks silently if a field is renamed. | DOM-read in `Browser.read_state()` validates that all 14 expected fields are present and raises `DOMReadError` listing missing fields. Slice-1 fixture-capture also exercises this — captures will fail loudly on the pinned version if any field is missing. |
| 7 | **Disk fills during multi-day training** (replay buffer + checkpoints + per-step latency logs). | Low | Training crashes mid-run. | Per-step latency logged at p50/p99 aggregate per episode, not per step (see §6 slice 1 task 4). Checkpoint retention: keep best + last-3, prune older. Replay buffer not persisted across runs. |

## 9. Open questions

Items the planner cannot resolve from current evidence and that the critic should challenge or that should be deferred to an ADR landed during execution:

1. **Subprocess vs in-process periodic eval (§8 risk 3).** Default is subprocess for clean state isolation; in-process re-use of the training Chrome is the fallback. Critic-resolvable: does the design plan's AC-SINGLETON wording "one eval script" already settle that subprocess re-use is fine (since it's *the same* eval script being re-invoked), or is the existence of a second concurrent-but-paused Chrome process a constraint-3 issue?
2. **CDP key dispatch as legitimate "automation driver attached" vs as illegitimate "injected JavaScript" (§8 risk 4).** ADR-008 takes a position; the critic should challenge if the interpretation is wrong.
3. **Reward shaping budget for slice 4 / slice 5.** §3.3 forbids shaping; §6 slice 4 / 5 mention "observation refinement under ADR-003 amendment" as a fallback if hyperparameter tuning is exhausted. Is observation refinement actually different in kind from reward shaping for AC-STOP-GATE purposes? The planner's read: yes — observation changes are a representation choice, reward changes are an objective change; the post-mortem warned specifically about objective drift. But this is a soft distinction worth challenging.
4. **Score-readout formula** (`Math.floor(distanceRan * COEFFICIENT)` vs reading the displayed digit array directly). §6 slice 1 task 2 picks the formula approach. The displayed-digits approach is more robust to upstream formula changes but adds DOM-traversal cost. Defer to slice-1 measurement; record in ADR-005.
5. **Heuristic threshold formula details** (the linear-in-speed jump-distance threshold in §6 slice 1 task 3). Exact coefficients are an implementation detail that lives in the `src/heuristic.py` docstring — *not* an ADR, because the heuristic is a frozen sanity baseline and AC-STOP-GATE's beat-baseline sub-gate compares against whatever number the heuristic actually produced in slice 1. If the threshold formula is "wrong," the heuristic just scores lower, which makes the beat-baseline gate easier to clear, not harder. Flagged here so the critic can confirm the planner is not smuggling tuning into "frozen baseline."
6. **Whether ADR-007 (algorithm choice) should be locked at design level rather than implementation level.** Design plan §3 flagged this as an implementation-planning decision; this plan locks it as DQN. The critic can argue the lock should be revisited at design level if the swap criterion (§3.1) ever fires.
7. **Two iterations from a cold start hitting MET is implausible** (this is the design plan's own framing in §0 and §7). The implementation plan inherits this. Open whether to add an *additional* slice-3-end exit ("if slice-3 eval-mean is < 100, that's already a "noise floor" signal — block now rather than burn 14 days on slices 4 + 5"). Not added by default — the design plan says the gate fires only after slices 4 and 5 (per AC-STOP-GATE), and adding a slice-3 floor exit is implementation-plan-overreach into AC-STOP-GATE territory. Flagged for critic challenge.
8. **Step pacing** — *resolved in §3.7 as part of round 1 response*: free-run, no `sleep`, paced by the page's own clock. ADR-003 scope expanded to include the pacing lock. Listed here for traceability so a reader of the open-questions section sees that this was a R1 critic finding (#10) and where it landed.

## Round 1 Response

Per-item disposition of [`phase-1-critique-implementation-R1.md`](phase-1-critique-implementation-R1.md). One line per critique item, in the same numbering as the critique's summary table.

1. **DQN choice + MLP capacity — PASS.** No action on the verdict itself; see #1a for the citation defect inside the §3.1 prose.
2. **Citation defect (#1a) — fixed.** §3.1 changed `mean ~870 cited in the design plan` → `mean ~555 per project-history.md § Attempt 2 and design plan §0`. The 870 number was an artifact of earlier conversation; the post-mortem and design plan §0 line 8/241 both say 555. The argument (DQN over PPO at < ~30 samples/sec) is unchanged and works at 555.
3. **CDP locked before slice-1 measurement — PASS.** No action.
4. **2-obstacle window justification (#3a) — fixed.** §3.4 now contains a paragraph titled "Obstacle window width = 2 (justification)" citing the page's `gap = obstacle.width * speed + minGap * gapCoefficient` spawning logic and recording why the post-mortem-style "narrowing was the binding gap" failure mode does not apply (v1's narrowing failure was on sim density, not on policy-input width). ADR-003 amendment widens to 3 if slice 3/4 evidence shows policy fails on dense clusters.
5. **Sentinel encoding (#3b) — PASS.** No action; see #3c which constrained the encoding to scalar (which is what makes `type_id = -1` work).
6. **Observation dim BLOCKER (#3c) — fixed.** Picked **scalar `type_id` ∈ {-1, 0, 1, 2}** (the simpler option recommended). §3.4 table row 5–9 now reads `type_id ∈ {-1, 0, 1, 2}` (scalar; ...sentinel=-1)`; the misleading "one-hot in tensor" parenthetical is removed and replaced with explicit "scalar, not one-hot" prose + a short justification paragraph (4 buckets × MLP[64,64] does not need one-hot). The 14-dim total now matches the encoding. Sentinel paragraph clarifies that `type_id = -1` is "only valid in the scalar encoding above." ADR-003 inherits the consistent contract.
7. **Reward magnitudes (#4) — fixed (audit-trail nit).** §3.3 now ends with: "Any magnitude change is recorded in the slice wrap that introduces it (slice-N wrap states the old value, the new value, the reason, and the slice-N-evidence that motivated the change), so the audit trail is complete even without an ADR." Also added the early-vs-late-training credit-assignment framing the critic raised (terminal `-100` is discriminative when episodes are 50–200 steps; that's the regime that matters for DQN bootstrapping).
8. **Action mapping bug (#5) — fixed.** §3.5 action table rewritten with a leading **Invariant**: "any non-`DUCK` action releases a held `ArrowDown` *before* dispatching its own keys." JUMP row now explicitly dispatches `keyUp ArrowDown` first if held, then `keyDown`/`keyUp ArrowUp`. Slice-1 task-7 test list now requires a `DUCK → JUMP → DUCK` state-machine test asserting (a) the intermediate JUMP releases ArrowDown and (b) the second DUCK re-presses it.
9. **`src/browser.py` and AC-SINGLETON (#6) — PASS.** No action. The critic's optional suggestion to mention "browser interface adapter" as a sixth bounded module class in AC-SINGLETON's wording or ADR-006 is deferred to ADR-006 authorship in slice 1 (the ADR can take the position naturally; adding it to the implementation plan now would duplicate prose that ADR-006 will own).
10. **14-day budget routing (#7) — PASS.** No action.
11. **Subprocess vs in-process eval cadence (#8) — fixed.** §6 slice 3 task 4 now sets a default `--eval-every = 50000` env-steps with the wall-clock arithmetic (Chrome cold-launch + 20 episodes ≈ 5–10% of slice-3 wall-clock at this cadence) and requires the slice-3 wrap to record both the cadence used and its share of slice-3 wall-clock. Slices 4/5 inherit the recorded cadence and can re-tune.
12. **Fixture-capture spec (#9) — PASS.** No action; #3c's resolution removes the prerequisite blocker the critic flagged ("tester needs to know the dim/encoding before slice 2 begins").
13. **Step-pacing decision missing (#10) — fixed.** New **§3.7 Env step pacing: free-run, paced by the page's own clock** added between §3.6 and §4. Locks free-run with four-bullet justification (vision-lock alignment, jitter robustness, cost transparency via per-step latency in eval artifact, accepted cost of not seeing every page frame). ADR-003's scope is expanded in the §5 ADR table to "14-dim feature vector + DOM read mechanism + step pacing." Open-questions §9 adds item 8 noting the resolution and where it landed.
14. **Open-question deferrals (#11) — PASS with addition.** Step-pacing question added as §9 item 8 (resolved, not open) — kept on the list for traceability so a reader sees this was a R1 finding.
15. **Post-mortem cross-check (#12) — PASS.** No action.

**Deviations from the critic's recommendations**: none. Every CONCERN/BLOCKER took the critic's primary recommendation (or, on #3c where the critic offered three options, the explicitly-recommended simpler option). The optional ADR-006 wording suggestion under #6 is the only item not implemented inline; it is deferred to ADR-006 authorship in slice 1, where it lives more naturally than in the implementation plan.

## Round 2 Response

Per-item disposition of [`phase-1-critique-implementation-R2.md`](phase-1-critique-implementation-R2.md). Items numbered as in R2; only items requiring action are listed.

- **NEW-A — action-mapping invariant didn't cover `reset_episode()` / terminal / teardown — fixed.** §3.5 invariant rewritten as a single sentence covering both "any non-`DUCK` action" *and* "any state transition that ends an episode (terminal step, `reset_episode()`, env teardown, exception in `step()`/`reset()`)." Required behaviors made concrete: terminal `step()` releases held keys before returning the terminal tuple; `reset_episode()` releases held keys before dispatching `Space`; teardown / exception paths release in a `finally` block. §6 slice 1 task 2 updated: `reset_episode()` spec now explicitly includes the held-flag check and pre-reset release, and a `close()` / `__exit__` surface is added with the same invariant in a `finally` block. §6 slice 1 task 7 test list extended with two new tests: (1) `DUCK → terminal → reset_episode() → JUMP` asserts terminal step releases `ArrowDown`, reset does not dispatch `Space` while held, and the post-reset `JUMP` is clean; (2) context-manager exit while `ArrowDown` is held asserts a `keyUp ArrowDown` is dispatched in the `finally` path before `driver.quit()`.
- **NEW-C — slice-3 training-budget floor missing — fixed.** §3.6 split into two sub-budgets: slice 3 gets a **3-day wall-clock cap with a 500k-env-step floor AND a 3-eval-cycle floor (whichever is greater)** before the AC-STOP-GATE beat-baseline sub-gate is allowed to fire on slice-3 evidence. The 500k figure is justified inline against SB3 DQN's typical small-MLP learning-curve regime (50k steps = noise floor; 500k = ~50% replay-buffer fill at default 1M, ~50 target-network syncs at default `target_update_interval=10000`) and the §3.2 ~30 steps/sec throughput target (~4.6 hours pure training). Slices 4 and 5 retain 7 days each. §6 slice 3 task 5 updated to require both floors before gate eval, with an explicit "under-floor → `awaiting-human-decision`, *not* gate fire" exit. §6 slice 3 task 6 updated: slice-3 wrap now reports total env-steps, total eval cycles, wall-clock consumed, full eval-mean trajectory (with rising/plateaued/oscillating/declining characterization), training-reward summary, slice-3 eval-mean, beat-baseline comparison, and per-floor pass/fail. §6 slice 3 exit branches restructured: a new "slice-3 budget-floor exit" precedes the beat-baseline gate, and the gate now requires the trajectory characterization to be `plateaued` or `declining` to fire (still-rising → extend, do not fire) — closes the false-negative-gate-fire risk R2 flagged.
- **R1 #3a / NEW-D — 2-obstacle window justification's unverified Chromium-formula citation — fixed by deferral.** §3.4's "Obstacle window width = 2" paragraph rewritten to (a) drop the formula citation entirely, (b) keep the two genuine reasons that don't depend on the formula (5 mostly-sentinel dims for the 3rd slot in the common case; v1's narrowing failure was on sim density, not policy-input width), and (c) explicitly defer the width lock to **ADR-003 amendment-on-first-use during slice 2**, with the slice-2 fixture-capture exercise (§6 slice 1 task 5 captures (e) and (f) — both-slots-populated and near-crash states) plus the slice-2 random-policy `@pytest.mark.browser` integration test as the evidence sources. If the slice-2 evidence shows the page surfaces ≥ 3 simultaneous obstacles within the planning horizon at game speeds, the window widens to 3 (recompute observation dim to 19) with an ADR-003 amendment in the same slice; if the observed maximum is consistently ≤ 2 at MET-relevant speeds, ADR-003 records width=2 with the slice-2 fixture evidence as its supporting citation. The false-confidence formula prose is gone; the slice 3 / 4 widen-on-evidence escape hatch is preserved.
- **NEW-B — DQN-Δt invariance under free-run — acknowledged, deferred to ADR-003 authorship in slice 2.** R2 explicitly marked this PASS-with-note and not revise-grade. ADR-003 (already scoped in §5 to cover step pacing) is the natural home for the one-sentence "free-run is consistent with DQN's transition framing because the observation vector encodes absolute state — `xPos_rel`, `current_speed_norm` — rather than per-frame deltas, so the policy can be Δt-invariant by construction." Adding it to the implementation plan now would duplicate text ADR-003 will own in slice 2. No implementation-plan edit.
- **R1 #1a sub-note — design plan §0 internal 870/555 inconsistency.** R2 noted (correctly) that the design plan §0 line 18 still says `~870` while line 8 / line 241 say `~555`. The implementation plan picked the source-of-truth value (555) per R1 #1a fix and is internally consistent. The design plan's own internal inconsistency is not in the implementation plan's lane to fix and is flagged here for the design author / human reader.

**Deviations from R2's recommendations**: one. R2 offered NEW-C as either a wall-clock floor (24 hours OR 500k steps) or a step-count floor (200k steps); the chosen shape is **both** floors (≥ 500k env-steps AND ≥ 3 eval cycles, whichever clears later, capped at 3 days wall-clock). Reasoning: a single floor leaves a hole in the other dimension (a step-count floor under a fast-throughput pathology could complete in 3 hours with only one eval cycle, leaving the wrap unable to characterize the trajectory; a wall-clock floor under a slow-throughput pathology could burn 24 hours producing only ~50k steps). The dual-floor + trajectory-characterization gate (still-rising → extend, plateaued/declining → fire) is the smallest spec that closes both holes and matches the gate's actual question ("is this evidence about the algorithm or about under-training?"). The 500k figure sits between R2's two suggested numbers and is justified inline against SB3 internals; the 3-eval-cycles floor is additive (not in either of R2's options) and is what makes the trajectory characterization possible.
