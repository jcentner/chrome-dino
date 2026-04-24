"""Slice-1 utility: drive one heuristic episode and dump raw DOM-state
snapshots to `tests/fixtures/dom_state/` for slice-2 unit tests.

NOT a second eval entry point. Dumps fixtures only. Imports
`src.browser.Browser` and `src.heuristic.act` to drive the page; uses the
same launch path as `scripts/eval.py` (re-imported, not duplicated).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any


_TARGET_LABELS = (
    "normal_mid_episode",
    "mid_jump",
    "mid_duck",
    "no_obstacles",
    "both_obstacle_slots_populated",
    "near_crash",
    "terminal",
)


def _classify(state: dict) -> str | None:
    """Return one of `_TARGET_LABELS` if `state` matches that shape, else None.

    Captured first-match-wins — once we have one of each, we stop early.
    """
    if state.get("crashed"):
        return "terminal"
    obs = state.get("obstacles") or []
    obs0 = obs[0] if obs else None
    obs1 = obs[1] if len(obs) > 1 else None
    if obs0 and obs1:
        return "both_obstacle_slots_populated"
    if not obs0:
        return "no_obstacles"
    trex = state.get("tRex") or {}
    if trex.get("ducking"):
        return "mid_duck"
    if trex.get("jumping"):
        return "mid_jump"
    if obs0 and float(obs0.get("xPos") or 1e9) < 80:
        return "near_crash"
    return "normal_mid_episode"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture DOM-state fixtures.")
    parser.add_argument(
        "--out-dir",
        default=os.path.join("tests", "fixtures", "dom_state"),
    )
    parser.add_argument("--max-steps", type=int, default=2000)
    args = parser.parse_args(argv)

    # Lazy import so unit tests don't pull in Selenium.
    from scripts.eval import _launch_browser
    from src.heuristic import act as heuristic_act

    os.makedirs(args.out_dir, exist_ok=True)

    browser, _ = _launch_browser()
    captured: dict[str, dict[str, Any]] = {}

    try:
        browser.version_check()
        # Run up to 5 episodes to maximise scenario coverage; the heuristic
        # crashes early so a single episode rarely sees ducking / multiple
        # obstacle slots / etc.
        for _episode in range(5):
            browser.reset_episode()
            # Wait for boot transition.
            for _ in range(50):
                s = browser.read_state()
                if s is not None and s.get("playing") and not s.get("crashed"):
                    break
                time.sleep(0.05)

            steps = 0
            while steps < args.max_steps and len(captured) < len(_TARGET_LABELS):
                state = browser.read_state()
                if state is None:
                    time.sleep(0.01)
                    continue

                if state.get("crashed"):
                    captured.setdefault("terminal", state)
                    break

                label = _classify(state)
                if label and label not in captured:
                    captured[label] = state

                action = int(heuristic_act(state))
                browser.send_action(action)
                steps += 1

            if len(captured) >= len(_TARGET_LABELS):
                break
    finally:
        browser.close()

    for label, state in captured.items():
        path = os.path.join(args.out_dir, f"{label}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        print(f"wrote {path}")

    missing = [t for t in _TARGET_LABELS if t not in captured]
    if missing:
        print(f"warning: did not capture {missing}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
