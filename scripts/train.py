"""Slice-3 training entry point: SB3 DQN over `DinoEnv`.

Per ADR-007: stable-baselines3 `DQN`, MLP `[64, 64]`, hyperparameters
trimmed for the slice-3 4-hour wall-clock cap (impl plan §3.6 default
of 3 days narrowed by the 2026-04-25 operator decision recorded in
`roadmap/CURRENT-STATE.md`).

CLI is intentionally minimal — every hyperparameter not on the command
line is hardcoded in the `_DQN_KWARGS` block below per impl plan §6
slice 3 task 3 ("hyperparameters committed in a config block in the
script — not a separate config file").
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Repo root for sibling imports when invoked via `python scripts/train.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------
# DQN config (ADR-007). Edits here are the audit trail; keep them in
# this single block, not split across files.
# ---------------------------------------------------------------------

_DQN_KWARGS: dict[str, Any] = {
    "policy": "MlpPolicy",
    "policy_kwargs": {"net_arch": [64, 64]},
    "learning_rate": 1e-3,
    "buffer_size": 100_000,         # trimmed for 4h cap; ADR-007
    "learning_starts": 1_000,       # trimmed for 4h cap; ADR-007
    "batch_size": 64,
    "gamma": 0.99,
    "train_freq": 4,
    "gradient_steps": 1,
    "target_update_interval": 1_000,  # trimmed for 4h cap; ADR-007
    "exploration_fraction": 0.1,
    "exploration_initial_eps": 1.0,
    "exploration_final_eps": 0.05,
    "verbose": 1,
    "seed": 42,
    # `device` is overridden from the CLI flag below; "auto" picks GPU if
    # torch sees CUDA. For a 14-dim MLP[64,64] the gradient-compute cost
    # is small relative to env-step latency (Chrome/CDP), so CPU is
    # often comparable to GPU; the flag exists so the operator can pin
    # a device explicitly when measuring.
    "device": "auto",
}


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _build_argparser() -> argparse.ArgumentParser:
    """Build the CLI parser. Factored out so `--help` doesn't import SB3."""
    parser = argparse.ArgumentParser(
        prog="train.py",
        description=(
            "Slice-3 SB3 DQN training over DinoEnv. Capped by both an "
            "env-step budget (--total-steps) and a wall-clock budget "
            "(--max-wall-hours). Periodic eval fires every --eval-every "
            "env-steps and writes a subprocess-eval artifact to the run "
            "log dir; checkpoints save every --ckpt-every env-steps. "
            "Per ADR-007."
        ),
    )
    parser.add_argument(
        "--total-steps",
        type=int,
        required=True,
        help="Env-step budget. Slice-3 floor (impl §3.6) is 500000; "
             "the 4h-cap operator decision will most likely cap effective "
             "steps below this floor — slice will exit via the budget-"
             "floor branch in that case.",
    )
    parser.add_argument(
        "--eval-every",
        type=int,
        default=50_000,
        help="Env-steps between periodic eval cycles. Default 50000 per "
             "impl §3.6 / §6 slice 3 task 4.",
    )
    parser.add_argument(
        "--ckpt-every",
        type=int,
        default=25_000,
        help="Env-steps between checkpoint saves.",
    )
    parser.add_argument(
        "--max-wall-hours",
        type=float,
        default=4.0,
        help="Wall-clock cap in hours. Default 4.0 per the 2026-04-25 "
             "operator decision recorded in roadmap/CURRENT-STATE.md.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier. Defaults to a UTC timestamp.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(_REPO_ROOT / "logs" / "train"),
        help="Parent directory for run logs. The run-id becomes a "
             "subdirectory.",
    )
    parser.add_argument(
        "--models-dir",
        default=str(_REPO_ROOT / "models"),
        help="Parent directory for checkpoint zips.",
    )
    parser.add_argument(
        "--eval-episodes",
        type=int,
        default=20,
        help="Episodes per periodic eval invocation.",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Torch device for SB3. 'auto' picks CUDA if available, else CPU. "
             "For the [64,64] MLP at 14-dim observation, CPU is often "
             "comparable to or faster than GPU due to launch overhead — "
             "the env-step latency (Chrome/CDP round-trip) dominates total "
             "throughput. Pin explicitly when measuring.",
    )
    return parser


class _WallClockCallback:
    """SB3 callback that aborts `model.learn` once a wall-clock deadline
    is reached. Implemented as a `stable_baselines3.common.callbacks.BaseCallback`
    via lazy import to keep top-level import light. Returning False from
    `_on_step` causes SB3 to terminate the current `learn` call.
    """

    def __new__(cls, *, deadline_monotonic: float) -> Any:
        from stable_baselines3.common.callbacks import BaseCallback

        class _Impl(BaseCallback):
            def __init__(self) -> None:
                super().__init__(verbose=0)
                self._deadline = deadline_monotonic

            def _on_step(self) -> bool:
                return time.monotonic() < self._deadline

        return _Impl()


def _make_env_and_browser():
    """Lazy import of Browser+Env so `--help` does not pay the cost."""
    from src.browser import Browser
    from src.env import DinoEnv

    browser = Browser.launch()
    env = DinoEnv(browser)
    return env, browser


def _run_periodic_eval(
    *,
    checkpoint_path: Path,
    eval_episodes: int,
    out_path: Path,
) -> float | None:
    """Subprocess-invoke `scripts/eval.py --policy learned`.

    Subprocess (not in-process) per impl §6 slice 3 task 4 / §8 risk 3:
    keeps the training-Chrome and eval-Chrome state cleanly isolated.
    Returns the mean score on success, `None` on subprocess failure.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "eval.py"),
        "--policy", "learned",
        "--checkpoint", str(checkpoint_path),
        "--episodes", str(eval_episodes),
        "--out", str(out_path),
    ]
    # Pass PYTHONPATH so the subprocess can import `src.*` regardless of
    # how the parent was launched. Inherit the rest of the environment so
    # CHROME_DINO_RUNTIME and any other operator-set vars survive.
    sub_env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT)}
    try:
        # Worst-case eval wall-clock: eval_episodes × 300s per-episode cap
        # (the eval.py default --max-episode-seconds) + Chrome cold-launch
        # overhead. Pad generously so the timeout only fires on a true hang.
        eval_timeout_s = max(30 * 60, eval_episodes * 360)
        subprocess.run(
            cmd,
            check=True,
            timeout=eval_timeout_s,
            cwd=str(_REPO_ROOT),
            env=sub_env,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"[train] periodic eval failed: {exc}", file=sys.stderr)
        return None
    try:
        with out_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        scores = [ep["score"] for ep in data.get("episodes", [])]
        return float(sum(scores) / len(scores)) if scores else None
    except Exception as exc:
        print(f"[train] could not read eval artifact: {exc}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)

    run_id = args.run_id or datetime.now(timezone.utc).strftime(
        "dqn-%Y%m%dT%H%M%SZ"
    )
    run_log_dir = Path(args.out_dir) / run_id
    run_log_dir.mkdir(parents=True, exist_ok=True)
    run_models_dir = Path(args.models_dir) / run_id
    run_models_dir.mkdir(parents=True, exist_ok=True)

    eval_means_csv = run_log_dir / "eval_means.csv"
    train_reward_csv = run_log_dir / "training_reward.csv"
    config_json = run_log_dir / "config.json"

    config_record = {
        "git_sha": _git_sha(),
        "run_id": run_id,
        "total_steps_budget": args.total_steps,
        "eval_every": args.eval_every,
        "ckpt_every": args.ckpt_every,
        "max_wall_hours": args.max_wall_hours,
        "eval_episodes": args.eval_episodes,
        "dqn_kwargs": _DQN_KWARGS,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    config_json.write_text(json.dumps(config_record, indent=2), encoding="utf-8")

    # Lazy SB3 import after argparse so `--help` is fast and importable in
    # tests that mustn't construct a Chrome.
    from stable_baselines3 import DQN

    env, browser = _make_env_and_browser()
    try:
        browser.version_check()
        browser.sanity_probe()
    except Exception:
        browser.close()
        raise

    dqn_kwargs = dict(_DQN_KWARGS)
    dqn_kwargs["device"] = args.device
    model = DQN(
        env=env,
        tensorboard_log=str(run_log_dir / "tb"),
        **dqn_kwargs,
    )

    wall_start = time.monotonic()
    wall_cap_seconds = args.max_wall_hours * 3600.0
    steps_done = 0
    next_eval_at = args.eval_every
    next_ckpt_at = args.ckpt_every

    eval_csv_handle = eval_means_csv.open("w", encoding="utf-8", newline="")
    eval_writer = csv.writer(eval_csv_handle)
    eval_writer.writerow(["step", "wall_seconds", "eval_mean"])
    eval_csv_handle.flush()

    train_csv_handle = train_reward_csv.open(
        "w", encoding="utf-8", newline=""
    )
    train_writer = csv.writer(train_csv_handle)
    train_writer.writerow(["step", "wall_seconds", "ep_reward_mean"])
    train_csv_handle.flush()

    exit_reason: str = "unknown"
    try:
        # Outer loop: train in chunks bounded by the next checkpoint /
        # eval / wall-cap event, whichever fires first.
        while steps_done < args.total_steps:
            wall_elapsed = time.monotonic() - wall_start
            if wall_elapsed >= wall_cap_seconds:
                exit_reason = "wall-cap"
                break

            # Step budget for this chunk: until the next event.
            next_event = min(next_ckpt_at, next_eval_at, args.total_steps)
            chunk = max(1, next_event - steps_done)

            cap_callback = _WallClockCallback(
                deadline_monotonic=wall_start + wall_cap_seconds
            )
            model.learn(
                total_timesteps=chunk,
                reset_num_timesteps=False,
                log_interval=10,
                progress_bar=False,
                callback=cap_callback,
            )
            steps_done = int(model.num_timesteps)

            # SB3's `model.logger.name_to_value` is cleared each dump
            # cycle, so reading it from the periodic-eval cadence almost
            # always returned None (slice-3 logging bug). Use the
            # model's `ep_info_buffer` (deque of recent completed-episode
            # info dicts) directly — each entry has key `"r"` for reward.
            ep_rew_mean = None
            try:
                buf = getattr(model, "ep_info_buffer", None)
                if buf:
                    rewards = [ep["r"] for ep in buf if "r" in ep]
                    if rewards:
                        ep_rew_mean = float(sum(rewards) / len(rewards))
            except Exception:
                pass
            train_writer.writerow(
                [steps_done, time.monotonic() - wall_start, ep_rew_mean]
            )
            train_csv_handle.flush()

            if steps_done >= next_ckpt_at:
                ckpt_path = run_models_dir / f"{steps_done}.zip"
                model.save(str(ckpt_path))
                sidecar = {
                    "git_sha": config_record["git_sha"],
                    "hyperparameters": _DQN_KWARGS,
                    "total_steps_so_far": steps_done,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                }
                ckpt_path.with_suffix(".json").write_text(
                    json.dumps(sidecar, indent=2), encoding="utf-8"
                )
                next_ckpt_at = steps_done + args.ckpt_every

            if steps_done >= next_eval_at:
                # Tear down the training browser before subprocess-eval so
                # there is only one Chrome alive at a time per impl §8 risk 3.
                try:
                    browser.close()
                except Exception:
                    pass
                latest_ckpt = run_models_dir / f"{steps_done}.zip"
                if not latest_ckpt.exists():
                    # Force a checkpoint right now so eval has something
                    # current to load.
                    model.save(str(latest_ckpt))
                eval_out = run_log_dir / f"eval_{steps_done}.json"
                eval_mean = _run_periodic_eval(
                    checkpoint_path=latest_ckpt,
                    eval_episodes=args.eval_episodes,
                    out_path=eval_out,
                )
                eval_writer.writerow(
                    [steps_done, time.monotonic() - wall_start, eval_mean]
                )
                eval_csv_handle.flush()
                next_eval_at = steps_done + args.eval_every
                # Re-launch training browser after eval.
                env, browser = _make_env_and_browser()
                browser.version_check()
                browser.sanity_probe()
                model.set_env(env)
        else:
            exit_reason = "step-budget"
    finally:
        try:
            browser.close()
        except Exception:
            pass
        eval_csv_handle.close()
        train_csv_handle.close()
        # Always save a final checkpoint so the operator can resume / eval.
        final_ckpt = run_models_dir / f"final_{steps_done}.zip"
        try:
            model.save(str(final_ckpt))
        except Exception:
            pass

    summary = {
        "run_id": run_id,
        "exit_reason": exit_reason,
        "steps_done": steps_done,
        "wall_seconds_elapsed": time.monotonic() - wall_start,
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_log_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
