"""Shared pytest configuration for chrome-dino tests.

Registers the `browser` marker so live-Chrome tests can be opted into via
`pytest -m browser`. Default invocation (set in pytest.ini) is
`-m "not browser"`, which keeps the unit suite fast and dependency-free.
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "browser: tests that require a live Chrome runtime (opt-in; pinned per docs/setup/windows-chrome-pinning.md)",
    )
