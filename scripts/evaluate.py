"""
Evaluate a trained model and display results.

Usage:
    python scripts/evaluate.py --model models/ppo_dino/best/best_model.zip [--episodes 100] [--render]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.env import DinoEnv


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained Dino agent")
    parser.add_argument("--model", type=str, required=True, help="Path to model zip")
    parser.add_argument("--episodes", type=int, default=100, help="Number of eval episodes")
    parser.add_argument("--render", action="store_true", help="Show ANSI rendering")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--action-delay", type=int, default=1,
                        help="Action delay in frames (match training env)")
    parser.add_argument("--frame-skip", type=int, default=2,
                        help="Internal frames per env step (match training env)")
    parser.add_argument("--clear-time-ms", type=float, default=500,
                        help="Milliseconds before obstacles spawn")
    args = parser.parse_args()

    model = PPO.load(args.model)
    env = DinoEnv(
        render_mode="ansi" if args.render else None,
        action_delay=args.action_delay,
        frame_skip=args.frame_skip,
        clear_time_ms=args.clear_time_ms,
    )

    scores = []
    episode_lengths = []

    for ep in range(args.episodes):
        obs, _ = env.reset(seed=args.seed + ep)
        total_reward = 0
        steps = 0

        while True:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(int(action))
            total_reward += reward
            steps += 1

            if args.render and steps % 5 == 0:
                print("\033[2J\033[H" + env.render())

            if terminated or truncated:
                scores.append(info["score"])
                episode_lengths.append(steps)
                if args.render:
                    print(f"\nEpisode {ep+1}: score={info['score']:.0f}, steps={steps}")
                break

    scores = np.array(scores)
    lengths = np.array(episode_lengths)

    print(f"\n{'='*50}")
    print(f"Evaluation Results ({args.episodes} episodes)")
    print(f"{'='*50}")
    print(f"Score:  mean={scores.mean():.0f}, std={scores.std():.0f}, "
          f"min={scores.min():.0f}, max={scores.max():.0f}")
    print(f"Steps:  mean={lengths.mean():.0f}, std={lengths.std():.0f}, "
          f"min={lengths.min():.0f}, max={lengths.max():.0f}")
    print(f"Median score: {np.median(scores):.0f}")
    print(f"90th percentile: {np.percentile(scores, 90):.0f}")

    # Compare to random baseline
    print(f"\nRandom baseline score: ~160")
    improvement = (scores.mean() - 160) / 160 * 100
    print(f"Improvement over random: {improvement:.0f}%")


if __name__ == "__main__":
    main()
