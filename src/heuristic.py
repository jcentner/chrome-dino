"""Frozen speed-adaptive heuristic policy. Slice-1 sanity baseline only.

Per AC-SINGLETON, this is the single fixed-policy module. It is invoked
through `scripts/eval.py` like any other policy. No parameters are tuned
during phase 1.
"""

from __future__ import annotations

from typing import Any

from src.browser import NOOP, JUMP, DUCK


# Pterodactyl `type` strings vary slightly across Chrome dino revisions; we
# match by substring on the lowercased page-reported type label.
_PTERODACTYL_TOKENS = ("ptero",)
_LOW_PTERODACTYL_Y = 75  # page units; below this y the pterodactyl is at dino height
_DUCK_Y_THRESHOLD = 90   # any obstacle (pterodactyl) at y >= this is overhead


def _jump_threshold(speed: float) -> float:
    """Linear-in-speed jump-trigger distance (xPos in page units).

    Faster speed → trigger earlier. Tuned by inspection from 2018-impl
    behaviour; frozen for phase 1.
    """
    return 60.0 + 12.0 * float(speed)


def act(observation: Any) -> int:
    """Return one of {NOOP, JUMP, DUCK} from a raw `Browser.read_state` dict.

    Accepts the dict shape directly; deliberately does not depend on the
    14-dim feature vector (which doesn't exist until slice 2). This keeps
    the heuristic re-usable as a sanity baseline even after the env contract
    is locked.
    """
    if not isinstance(observation, dict):
        return NOOP

    obstacles = observation.get("obstacles") or []
    obs0 = obstacles[0] if obstacles else None
    if obs0 is None:
        return NOOP

    speed = float(observation.get("currentSpeed") or 0.0)
    type_label = str(obs0.get("type") or "").lower()
    y = float(obs0.get("yPos") or 0.0)
    x = float(obs0.get("xPos") or 0.0)

    is_pterodactyl = any(t in type_label for t in _PTERODACTYL_TOKENS)

    # Overhead pterodactyl → duck under it.
    if is_pterodactyl and y >= _DUCK_Y_THRESHOLD:
        return DUCK

    # High-flying pterodactyl → no need to act, it passes overhead naturally.
    if is_pterodactyl and y < _LOW_PTERODACTYL_Y:
        return NOOP

    # Ground obstacle within jump range → jump.
    if x < _jump_threshold(speed):
        return JUMP

    return NOOP
