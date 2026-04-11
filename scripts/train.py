"""
Train a PPO agent to play Chrome Dino.

Usage:
    python scripts/train.py [--timesteps N] [--name NAME]
"""

import argparse
import os
import sys
from pathlib import Path

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import (
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.env import DinoEnv


def make_env(seed: int):
    def _init():
        env = DinoEnv()
        env.reset(seed=seed)
        return env
    return _init


def main():
    parser = argparse.ArgumentParser(description="Train PPO on Chrome Dino")
    parser.add_argument("--timesteps", type=int, default=2_000_000,
                        help="Total training timesteps")
    parser.add_argument("--name", type=str, default="ppo_dino",
                        help="Run name for logs/models")
    parser.add_argument("--n-envs", type=int, default=16,
                        help="Number of parallel environments")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to model zip to resume from")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    log_dir = project_root / "logs" / args.name
    model_dir = project_root / "models" / args.name
    log_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # Vectorized environments for parallel rollouts
    env = SubprocVecEnv([make_env(i) for i in range(args.n_envs)])
    env = VecMonitor(env, str(log_dir))

    # Eval environment (single, deterministic)
    eval_env = SubprocVecEnv([make_env(1000)])
    eval_env = VecMonitor(eval_env, str(log_dir / "eval"))

    # Callbacks
    checkpoint_cb = CheckpointCallback(
        save_freq=max(50_000 // args.n_envs, 1),
        save_path=str(model_dir / "checkpoints"),
        name_prefix="dino",
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(model_dir / "best"),
        log_path=str(log_dir / "eval"),
        eval_freq=max(25_000 // args.n_envs, 1),
        n_eval_episodes=20,
        deterministic=True,
    )

    if args.resume:
        print(f"Resuming from {args.resume}")
        model = PPO.load(args.resume, env=env, device=device)
    else:
        # PPO hyperparameters tuned for this environment
        model = PPO(
            "MlpPolicy",
            env,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=256,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.02,
            vf_coef=0.5,
            max_grad_norm=0.5,
            policy_kwargs=dict(
                net_arch=dict(pi=[256, 256], vf=[256, 256]),
                activation_fn=torch.nn.ReLU,
            ),
            verbose=1,
            tensorboard_log=str(log_dir),
            device=device,
        )

    print(f"Training for {args.timesteps:,} timesteps with {args.n_envs} envs")
    print(f"Logs: {log_dir}")
    print(f"Models: {model_dir}")

    model.learn(
        total_timesteps=args.timesteps,
        callback=[checkpoint_cb, eval_cb],
        progress_bar=True,
    )

    # Save final model
    final_path = model_dir / "final"
    model.save(str(final_path))
    print(f"Final model saved to {final_path}")

    env.close()
    eval_env.close()


if __name__ == "__main__":
    main()
