"""Schema test for the eval artifact format (§6 slice 1 task 4 + design §2 ACs).

Pins the JSON schema the eval script emits so that slices 3, 4, 5, 6 can rely
on it. Imports `validate_artifact` from `scripts.eval`; until the script
exists, every test in this module fails at collection with `ModuleNotFoundError`
— that's the contract pin.
"""

from __future__ import annotations

import copy
import pytest

# This import will fail with ModuleNotFoundError until scripts/eval.py and
# its `validate_artifact` callable exist. That is the slice-1 contract.
from scripts.eval import validate_artifact  # noqa: E402


def _valid_artifact() -> dict:
    return {
        "metadata": {
            "chrome_version": "131.0.6778.140",
            "chromedriver_version": "131.0.6778.140",
            "git_sha": "deadbeefcafebabe1234567890abcdef12345678",
            "policy": "heuristic",
            "checkpoint": None,
            "run_started_at": "2026-04-17T12:00:00Z",
        },
        "episodes": [
            {
                "score": 437,
                "steps": 312,
                "wall_seconds": 14.218,
                "page_seconds_at_gameover": 14.111,
                "gameover_detection_delay_ms": 17.4,
                "per_step_latency_ms_p50": 11.2,
                "per_step_latency_ms_p99": 27.8,
            }
        ],
    }


def _is_rejection(result) -> bool:
    """Return True if `result` indicates the artifact failed validation.

    `validate_artifact` may signal failure either by raising or by returning a
    falsy / non-success value. We accept either contract — the slice-1 test
    pins "rejection happens", not the precise mechanism.
    """
    if result is None:
        return False  # treat None as ambiguous; prefer raising for failure
    if isinstance(result, bool):
        return not result
    if isinstance(result, (list, tuple, set)):
        return len(result) > 0  # non-empty error list = rejection
    if isinstance(result, dict):
        # common shapes: {"valid": False, ...} or {"errors": [...]}
        if "valid" in result:
            return not result["valid"]
        if "errors" in result:
            return bool(result["errors"])
    return False


def test_valid_artifact_passes() -> None:
    """A hand-written conformant artifact passes `validate_artifact`."""
    artifact = _valid_artifact()
    # Either returns truthy / None without raising, or returns a success-shaped
    # value. We assert "did not raise and did not signal rejection."
    result = validate_artifact(artifact)
    assert not _is_rejection(result), (
        f"valid artifact was rejected by validate_artifact: result={result!r}"
    )


def test_missing_metadata_field_rejected() -> None:
    """Dropping `chrome_version` from metadata causes validation to reject."""
    artifact = _valid_artifact()
    del artifact["metadata"]["chrome_version"]

    raised = False
    rejected = False
    try:
        result = validate_artifact(artifact)
        rejected = _is_rejection(result)
    except Exception:
        raised = True

    assert raised or rejected, (
        "validate_artifact must reject artifacts missing required metadata "
        "fields (chrome_version), either by raising or returning a "
        "rejection-shaped result."
    )


def test_extra_episode_field_rejected_or_warned() -> None:
    """An unexpected field in an episode causes validation to reject or
    otherwise signal non-success. Anchors the schema as exact so slice 6's
    MET artifact cannot silently grow new fields."""
    artifact = _valid_artifact()
    artifact["episodes"][0]["unexpected_field"] = "surprise"

    raised = False
    rejected = False
    try:
        result = validate_artifact(artifact)
        rejected = _is_rejection(result)
    except Exception:
        raised = True

    assert raised or rejected, (
        "validate_artifact must reject (or non-success-signal) episodes with "
        "unexpected fields — the schema is exact, not additive."
    )


def test_episodes_count_field_present() -> None:
    """A valid artifact has at least one episode and every required episode
    field is present on each episode entry."""
    artifact = _valid_artifact()
    assert len(artifact["episodes"]) >= 1

    required_fields = {
        "score",
        "steps",
        "wall_seconds",
        "page_seconds_at_gameover",
        "gameover_detection_delay_ms",
        "per_step_latency_ms_p50",
        "per_step_latency_ms_p99",
    }
    for ep in artifact["episodes"]:
        missing = required_fields - set(ep.keys())
        assert not missing, f"episode missing required fields: {missing}"

    # And: the validator accepts this baseline artifact.
    result = validate_artifact(artifact)
    assert not _is_rejection(result)
