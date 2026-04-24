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
# Pterodactyls spawn at three fixed yPos values per
# `chromium/.../offline.ts` Pterodactyl.config.Y_POS_HEIGHT = [100, 75, 50].
#  - y=100 (low):  overlaps standing dino body AND ducking dino body → must JUMP
#  - y=75  (mid):  overlaps standing dino body but NOT ducking box   → must DUCK
#  - y=50  (high): well above standing dino head                     → NOOP
_PTERO_Y_LOW = 100   # exact value; we treat y >= 90 as "low" for tolerance
_PTERO_Y_MID = 75    # exact value; we treat 60 <= y < 90 as "mid"
_PTERO_Y_HIGH = 50   # exact value; y < 60 → NOOP


def _jump_threshold(speed: float, width: float) -> float:
    """Trigger leading-edge x for jumping over an obstacle of given width.

    Combines two terms:
    1. Physics: align obstacle center with apex \u2192 `14.5*speed - W/2`
       (full ~553ms jump, apex at 242ms with held-ArrowUp).
    2. Latency buffer: the Python loop polls at ~50Hz and each
       `execute_script` round-trip suspends the page's RAF, so an obstacle
       can effectively "tunnel" 30-50 px between reads. Add a generous
       constant so we trigger before that gap can swallow the threshold.
    """
    return 14.5 * float(speed) - 0.5 * float(width) + 40.0


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
    width = float(obs0.get("width") or 0.0)

    is_pterodactyl = any(t in type_label for t in _PTERODACTYL_TOKENS)

    if is_pterodactyl:
        # Low pterodactyl (y≈97..103) overlaps both standing and ducking
        # collision boxes → jump over it like a tall obstacle.
        if y >= 90:
            if x < _jump_threshold(speed, width):
                return JUMP
            return NOOP
        # Mid pterodactyl (y≈72..78) clears a ducking dino but hits a
        # standing one → duck.
        if y >= 60:
            return DUCK
        # High pterodactyl (y≈48..52) flies overhead → ignore.
        return NOOP

    # Ground obstacle within jump range → jump.
    if x < _jump_threshold(speed, width):
        return JUMP

    return NOOP
