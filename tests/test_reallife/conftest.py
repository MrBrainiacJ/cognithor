"""Fixtures for real-life integration tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def jarvis_home(tmp_path):
    """Temporary Jarvis home directory."""
    home = tmp_path / ".jarvis"
    home.mkdir()
    (home / "workspace").mkdir()
    (home / "memory").mkdir()
    (home / "vault").mkdir()
    (home / "skills" / "generated").mkdir(parents=True)
    return home
