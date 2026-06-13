"""Pytest configuration for the Nia test suite.

Keeps tests hermetic: no real API calls, no real filesystem writes outside
a tmp_path fixture, no real launchd manipulation.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch, tmp_path):
    """Ensure no test accidentally reads or writes the user's real ~/.nia state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Belt and suspenders: explicitly remove API keys so a test cannot make
    # a live call by accident if it forgets to set dry_run.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    yield


@pytest.fixture
def fake_anthropic_key(monkeypatch):
    """Use this in tests that exercise the live-API code path with a mock."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
