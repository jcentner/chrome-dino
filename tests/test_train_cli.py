"""Slice-3 tests for `scripts/train.py` CLI.

Tests are derived from `roadmap/phases/phase-1-implementation.md` §3.1
(algorithm), §3.6 (training loop / wall-clock cap), and §6 slice 3 task 6
(CLI evidence requirements: --total-steps, --eval-every, --ckpt-every flags
in --help). The tester does not (and cannot) read `scripts/train.py` source —
the isolation hook denies it. Tests pin the contract; the implementer
reconciles to the tests.

Resolved spec ambiguities (documented inline):

- Wall-clock cap flag name is implementation-defined: tests accept any of
  `--max-wall-seconds`, `--max-wall-hours`, or a flag containing `wall-clock`.
  The default value (3-day spec cap vs 4-hour session-config cap from the
  2026-04-25 CURRENT-STATE.md entry) is NOT pinned — that's a session
  decision, not a code-pinned contract.
- argparse exits with code 2 on missing required flags; we accept `in (1, 2)`
  to allow an explicit `sys.exit(1)` fallback.
- All subprocess invocations carry a `timeout=30` so a misbehaving import
  (e.g., one that launches Chrome at module load) fails the test rather
  than hanging the suite.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAIN_SCRIPT = REPO_ROOT / "scripts" / "train.py"

SUBPROCESS_TIMEOUT_S = 30


def _run_train(*args: str) -> subprocess.CompletedProcess:
    """Invoke `python scripts/train.py <args>` with a hard timeout."""
    return subprocess.run(
        [sys.executable, str(TRAIN_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_S,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_help_exits_zero_and_mentions_required_flags() -> None:
    """`--help` exits 0 and mentions --total-steps, --eval-every, --ckpt-every."""
    result = _run_train("--help")
    assert result.returncode == 0, (
        f"--help exited {result.returncode}; stderr={result.stderr!r}"
    )
    out = result.stdout.lower()
    for flag in ("total-steps", "eval-every", "ckpt-every"):
        assert flag in out, f"--help output missing {flag!r}; got:\n{result.stdout}"


def test_help_mentions_wall_clock_cap_flag() -> None:
    """`--help` mentions a wall-clock cap flag (name is impl-defined)."""
    result = _run_train("--help")
    assert result.returncode == 0
    out = result.stdout.lower()
    assert (
        "max-wall-seconds" in out
        or "max-wall-hours" in out
        or "wall-clock" in out
    ), f"--help output missing wall-clock cap flag; got:\n{result.stdout}"


def test_missing_required_flag_exits_nonzero() -> None:
    """No args → argparse-style nonzero exit (1 or 2)."""
    result = _run_train()
    assert result.returncode != 0, (
        f"expected nonzero exit when --total-steps missing; "
        f"got {result.returncode}, stdout={result.stdout!r}"
    )
    assert result.returncode in (1, 2), (
        f"expected exit code 1 or 2 (argparse missing-required), "
        f"got {result.returncode}"
    )


def test_unknown_flag_exits_nonzero() -> None:
    """Unknown flag → argparse rejects with nonzero exit."""
    result = _run_train("--total-steps", "1000", "--bogus-flag")
    assert result.returncode != 0, (
        f"expected nonzero exit on unknown flag; got {result.returncode}"
    )


def test_main_callable_imports_cleanly() -> None:
    """`from scripts.train import main` and `main(['--help'])` exits 0.

    Pins (a) `main` is the canonical entry point with `argv` parameter, and
    (b) `--help` short-circuits before any browser/SB3 setup so the import
    has no Chrome-launching side effects at module load time.
    """
    from scripts.train import main  # noqa: E402

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    # argparse's --help raises SystemExit(0).
    assert exc_info.value.code == 0, (
        f"main(['--help']) exited with {exc_info.value.code}, expected 0"
    )
