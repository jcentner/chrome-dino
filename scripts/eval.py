"""Single eval entry point for chrome-dino phase 1.

Per AC-SINGLETON, this is the ONLY eval script. CLI flags select the policy
{heuristic, learned} and the checkpoint. The output JSON artifact format is
pinned by `tests/test_eval_artifact_schema.py` and reused by every later
slice (3, 4, 5, 6) — including the MET-claim eval in slice 6.

Slice 1 ships:
- `validate_artifact(dict)` — schema validator used by tests and by the
  eval loop itself before writing output.
- `main(argv)` — CLI entry point. Live-browser execution is gated on the
  pinned runtime being installed; the function is exercised end-to-end in
  the slice-1 manual eval run, not in unit tests.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Artifact schema + validator (pinned by tests/test_eval_artifact_schema.py)
# ---------------------------------------------------------------------------

_METADATA_REQUIRED = {
    "chrome_version",
    "chromedriver_version",
    "git_sha",
    "policy",
    "checkpoint",
    "run_started_at",
}

_EPISODE_REQUIRED = {
    "score",
    "steps",
    "wall_seconds",
    "wall_capped",
    "page_seconds_at_gameover",
    "gameover_detection_delay_ms",
    "per_step_latency_ms_p50",
    "per_step_latency_ms_p99",
}

_VALID_POLICIES = {"heuristic", "learned"}


class ArtifactValidationError(ValueError):
    """Raised by `validate_artifact` when the artifact does not conform."""


def validate_artifact(artifact: Any) -> dict:
    """Validate an eval artifact against the slice-1-pinned schema.

    Returns `{"valid": True, "errors": []}` on success; on failure either
    returns `{"valid": False, "errors": [...]}` or raises
    `ArtifactValidationError` for hard-shape violations (top-level type,
    missing top-level keys). Tests accept either rejection mechanism.

    Schema is exact: extra metadata or episode fields are rejected so that
    slice 6's MET artifact cannot silently grow new fields.
    """
    errors: list[str] = []

    if not isinstance(artifact, dict):
        raise ArtifactValidationError(
            f"artifact must be a dict, got {type(artifact).__name__}"
        )

    top_level_keys = set(artifact.keys())
    expected_top = {"metadata", "episodes"}
    if missing := (expected_top - top_level_keys):
        raise ArtifactValidationError(
            f"artifact missing top-level keys: {sorted(missing)}"
        )
    if extra := (top_level_keys - expected_top):
        errors.append(f"unexpected top-level keys: {sorted(extra)}")

    metadata = artifact.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be a dict")
    else:
        meta_keys = set(metadata.keys())
        if missing := (_METADATA_REQUIRED - meta_keys):
            errors.append(f"metadata missing fields: {sorted(missing)}")
        if extra := (meta_keys - _METADATA_REQUIRED):
            errors.append(f"unexpected metadata fields: {sorted(extra)}")
        policy = metadata.get("policy")
        if policy not in _VALID_POLICIES:
            errors.append(
                f"metadata.policy must be one of {sorted(_VALID_POLICIES)}, "
                f"got {policy!r}"
            )

    episodes = artifact.get("episodes")
    if not isinstance(episodes, list):
        errors.append("episodes must be a list")
    elif len(episodes) == 0:
        errors.append("episodes must be non-empty")
    else:
        for i, ep in enumerate(episodes):
            if not isinstance(ep, dict):
                errors.append(f"episodes[{i}] must be a dict")
                continue
            ep_keys = set(ep.keys())
            if missing := (_EPISODE_REQUIRED - ep_keys):
                errors.append(f"episodes[{i}] missing fields: {sorted(missing)}")
            if extra := (ep_keys - _EPISODE_REQUIRED):
                errors.append(f"episodes[{i}] unexpected fields: {sorted(extra)}")

    return {"valid": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# Live eval loop (exercised in the manual slice-1 run, not in unit tests)
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        )
        return out.decode("ascii").strip()
    except Exception:
        return "unknown"


def _percentile(samples: list[float], p: float) -> float:
    if not samples:
        return 0.0
    s = sorted(samples)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return float(s[k])


def _run_one_episode(
    browser, policy_act, *, max_episode_seconds: float = 300.0,
    max_consecutive_none_reads: int = 200,
) -> dict:
    """Run one full episode via `browser` + `policy_act(state) -> int`.
    Returns one episode dict in the artifact-schema-conformant shape.

    Bounded by both a wall-clock cap and a consecutive-None-read cap so a
    silently-failed page navigation cannot hang the manual eval.
    """
    # `Browser.reset_episode()` only dispatches Space; it does not block on
    # the page actually transitioning out of the prior episode's `crashed`
    # state. Per the chromium-dino-runner skill, jump-key restart is gated by
    # `gameoverClearTime` (1200 ms) after a crash. We retry the Space at
    # short intervals until the page reports `playing && !crashed`, which
    # also handles the very first kickoff (no prior crash, just `playing`
    # transitions true on the first Space).
    _BOOT_TIMEOUT_S = 5.0
    _BOOT_RETRY_INTERVAL_S = 0.25
    boot_deadline = time.perf_counter() + _BOOT_TIMEOUT_S
    while True:
        browser.reset_episode()
        retry_deadline = time.perf_counter() + _BOOT_RETRY_INTERVAL_S
        while time.perf_counter() < retry_deadline:
            s = browser.read_state()
            if s is not None and s.get("playing") and not s.get("crashed"):
                break
            time.sleep(0.02)
        else:
            if time.perf_counter() < boot_deadline:
                continue
            raise RuntimeError(
                f"could not start a fresh episode within {_BOOT_TIMEOUT_S}s"
            )
        break

    step_latencies_ms: list[float] = []
    wall_start = time.perf_counter()
    page_clock_at_gameover = 0.0
    gameover_wall = wall_start
    steps = 0
    consecutive_none_reads = 0

    wall_capped = False
    while True:
        if (time.perf_counter() - wall_start) > max_episode_seconds:
            wall_capped = True
            gameover_wall = time.perf_counter()
            state = browser.read_state() or {}
            page_clock_at_gameover = float(state.get("time") or 0.0) / 1000.0
            break

        t0 = time.perf_counter()
        state = browser.read_state()
        if state is None:
            consecutive_none_reads += 1
            if consecutive_none_reads > max_consecutive_none_reads:
                raise RuntimeError(
                    f"read_state returned None for {consecutive_none_reads} "
                    "consecutive reads; page is not driving Runner.instance_"
                )
            time.sleep(0.005)
            continue
        consecutive_none_reads = 0

        if state.get("crashed"):
            gameover_wall = time.perf_counter()
            page_clock_at_gameover = float(state.get("time") or 0.0) / 1000.0
            break

        action = int(policy_act(state))
        browser.send_action(action)
        t1 = time.perf_counter()
        step_latencies_ms.append((t1 - t0) * 1000.0)
        steps += 1

    score = browser.get_score()
    wall_seconds = gameover_wall - wall_start
    return {
        "score": int(score),
        "steps": int(steps),
        "wall_seconds": float(wall_seconds),
        "wall_capped": bool(wall_capped),
        "page_seconds_at_gameover": float(page_clock_at_gameover),
        "gameover_detection_delay_ms": float(
            max(0.0, (wall_seconds - page_clock_at_gameover) * 1000.0)
        ),
        "per_step_latency_ms_p50": _percentile(step_latencies_ms, 50),
        "per_step_latency_ms_p99": _percentile(step_latencies_ms, 99),
    }


def _resolve_policy(name: str, checkpoint: str | None):
    """Return a callable `policy_act(state_dict) -> int`."""
    if name == "heuristic":
        from src.heuristic import act as heuristic_act

        return heuristic_act
    if name == "learned":
        if not checkpoint:
            raise SystemExit("--checkpoint is required when --policy=learned")
        # Slice-3 wires this up; slice 1 only ships the surface.
        try:
            from src.policy import LearnedPolicy  # type: ignore[attr-defined]
            from src.env import _observation_from_state  # type: ignore[attr-defined]
        except Exception as exc:
            raise SystemExit(
                "learned policy requested but src/policy.py is not yet "
                f"implemented (slice 3): {exc}"
            )
        loaded = LearnedPolicy.load(checkpoint)

        # Adapter: eval loop calls policy_act(state_dict); LearnedPolicy.act
        # consumes the 14-dim observation per ADR-003 / ADR-007. The env
        # owns observation construction, so route the dict through it
        # before invoking the SB3 model.
        def _learned_act(state: dict) -> int:
            obs = _observation_from_state(state)
            return loaded.act(obs)

        return _learned_act
    # argparse enforces choices=_VALID_POLICIES, but keep the explicit guard
    # for direct callers of `_resolve_policy`.
    raise SystemExit(f"unknown policy: {name!r}")


def _launch_browser():
    """Construct a real `Browser` against the pinned runtime, returning
    `(browser, driver)` so the caller can read driver capabilities for the
    artifact metadata. Imported lazily to keep unit-test collection fast."""
    from src.browser import Browser

    browser = Browser.launch()
    return browser, browser._driver  # noqa: SLF001 — caller needs caps


def _chrome_versions(driver) -> tuple[str, str]:
    chrome_version = "unknown"
    chromedriver_version = "unknown"
    try:
        caps = getattr(driver, "capabilities", {}) or {}
        chrome_version = str(caps.get("browserVersion") or "unknown")
        chromedriver_version = str(
            (caps.get("chrome") or {}).get("chromedriverVersion") or "unknown"
        )
        # chromedriverVersion is "<version> (<sha>)" — keep just the version.
        chromedriver_version = chromedriver_version.split(" ", 1)[0]
    except Exception:
        pass
    return chrome_version, chromedriver_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Real-time eval for chrome-dino phase 1."
    )
    parser.add_argument("--policy", choices=sorted(_VALID_POLICIES), required=True)
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--out", required=True, help="Output JSON artifact path.")
    parser.add_argument("--max-episode-seconds", type=float, default=300.0,
                        help="Wall-clock cap per episode. Lower for fast iteration; "
                             "the dino can survive indefinitely with the held-jump policy.")
    args = parser.parse_args(argv)

    policy_act = _resolve_policy(args.policy, args.checkpoint)
    browser, driver = _launch_browser()

    try:
        browser.version_check()
    except Exception:
        # Surface but do not silently continue. The slice-1 manual run will
        # respond by aligning the pin or the runtime.
        browser.close()
        raise

    chrome_version, chromedriver_version = _chrome_versions(driver)

    artifact = {
        "metadata": {
            "chrome_version": chrome_version,
            "chromedriver_version": chromedriver_version,
            "git_sha": _git_sha(),
            "policy": args.policy,
            "checkpoint": args.checkpoint,
            "run_started_at": datetime.now(timezone.utc).isoformat(),
        },
        "episodes": [],
    }

    try:
        for _ in range(int(args.episodes)):
            ep = _run_one_episode(browser, policy_act, max_episode_seconds=args.max_episode_seconds)
            artifact["episodes"].append(ep)
    finally:
        browser.close()

    result = validate_artifact(artifact)
    if not result["valid"]:
        raise ArtifactValidationError(
            f"eval produced an artifact that fails validation: {result['errors']}"
        )

    out_path = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)

    scores = [ep["score"] for ep in artifact["episodes"]]
    print(
        f"wrote {out_path}  episodes={len(scores)}  "
        f"mean={statistics.fmean(scores):.1f}  "
        f"min={min(scores)}  max={max(scores)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
