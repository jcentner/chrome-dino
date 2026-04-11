"""
Train PPO directly in Chrome's frame-stepped Dino game.

This trains with ZERO sim-to-real gap — the game IS the training environment.
Trade-off: ~30 steps/sec (vs ~100K headless) means fewer total steps, but
every step is 100% faithful to Chrome's actual mechanics.

Usage:
    python scripts/train_browser.py --timesteps 50000 --name browser_ppo_v1

Requires: ChromeDriver running on port 9515
    /mnt/c/Temp/chromedriver.exe --port=9515
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import (
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.monitor import Monitor

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.chrome_env import ChromeDinoEnv


def main():
    parser = argparse.ArgumentParser(description="Train PPO in Chrome Dino")
    parser.add_argument("--timesteps", type=int, default=50_000,
                        help="Total training timesteps (default: 50000)")
    parser.add_argument("--name", type=str, default="browser_ppo_v1",
                        help="Experiment name")
    parser.add_argument("--frame-skip", type=int, default=4,
                        help="Game frames per env step (default: 4)")
    parser.add_argument("--max-episode-steps", type=int, default=3000,
                        help="Max steps per episode")
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--n-steps", type=int, default=256,
                        help="Steps per rollout (lower than headless due to slow env)")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to model to resume training from")
    args = parser.parse_args()

    model_dir = Path("models") / args.name
    log_dir = Path("logs") / args.name
    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Single env (can't parallelize across Chrome instances easily)
    print(f"Creating ChromeDinoEnv (frame_skip={args.frame_skip})...")
    env = Monitor(
        ChromeDinoEnv(
            frame_skip=args.frame_skip,
            max_steps=args.max_episode_steps,
        ),
        str(log_dir),
    )

    # Eval env (separate Chrome session? Actually, same Chrome instance
    # can only run one game. For eval, we'll skip separate eval env and
    # rely on training episode scores.)
    print(f"Training for {args.timesteps} timesteps (~{args.timesteps/30:.0f}s "
          f"= ~{args.timesteps/30/60:.1f} min at ~30 steps/sec)...")

    if args.resume:
        model = PPO.load(args.resume, env=env)
        print(f"Resumed from {args.resume}")
    else:
        model = PPO(
            "MlpPolicy",
            env,
            learning_rate=args.learning_rate,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.01,
            vf_coef=0.5,
            max_grad_norm=0.5,
            verbose=1,
            tensorboard_log=str(log_dir),
            policy_kwargs={"net_arch": [256, 256]},
            device="cpu",  # MlpPolicy is faster on CPU than GPU
        )

    checkpoint_cb = CheckpointCallback(
        save_freq=max(args.n_steps, 1000),
        save_path=str(model_dir / "checkpoints"),
        name_prefix="browser_ppo",
    )

    try:
        model.learn(
            total_timesteps=args.timesteps,
            callback=checkpoint_cb,
            progress_bar=True,
            reset_num_timesteps=args.resume is None,
        )
    except KeyboardInterrupt:
        print("\nTraining interrupted — saving current model...")
    finally:
        save_path = str(model_dir / "final" / "model")
        model.save(save_path)
        print(f"Model saved to {save_path}")

    env.close()

    # Quick eval of final model
    print("\nEvaluating final model (5 episodes)...")
    eval_env = ChromeDinoEnv(
        frame_skip=args.frame_skip,
        max_steps=args.max_episode_steps,
    )
    scores = []
    for ep in range(5):
        obs, _ = eval_env.reset()
        total_reward = 0
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = eval_env.step(action)
            total_reward += reward
            done = terminated or truncated
        score = info.get("score", 0)
        scores.append(score)
        print(f"  Episode {ep+1}: score={score:.0f}")

    scores = np.array(scores)
    print(f"\nFinal eval: mean={scores.mean():.0f}, max={scores.max():.0f}, "
          f"min={scores.min():.0f}")
    eval_env.close()


if __name__ == "__main__":
    main()
