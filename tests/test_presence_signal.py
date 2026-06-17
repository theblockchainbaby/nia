"""The presence adapter reads recent human input (HID idle) as a passive signal.

No hardware is touched: `ioreg` is faked, and the platform is forced to darwin so
these run on the Linux CI too. The contract pinned here: detected is True iff the
idle time is within the window, and an unreadable signal raises PresenceError
(which the sensor builtin turns into a graceful detected=false, tested elsewhere).
"""
from __future__ import annotations

import types

import pytest

from nia.adapters import presence


def _fake_ioreg(monkeypatch, *, idle_ns: int | None, returncode: int = 0):
    """Force darwin, a present ioreg, and a canned ioreg stdout."""
    monkeypatch.setattr(presence.sys, "platform", "darwin")
    monkeypatch.setattr(presence.shutil, "which", lambda name: "/usr/sbin/ioreg")
    body = "" if idle_ns is None else f'    | |   "HIDIdleTime" = {idle_ns}\n'
    def fake_run(*args, **kwargs):
        return types.SimpleNamespace(returncode=returncode, stdout=body, stderr="")
    monkeypatch.setattr(presence.subprocess, "run", fake_run)


def test_detected_when_input_is_recent(monkeypatch):
    _fake_ioreg(monkeypatch, idle_ns=2_000_000_000)  # 2.0s idle
    out = presence.read_presence(window_seconds=5.0)
    assert out["detected"] is True
    assert out["idle_seconds"] == 2.0
    assert out["window_seconds"] == 5.0
    assert out["signal"] == "hid"


def test_not_detected_when_idle_exceeds_window(monkeypatch):
    _fake_ioreg(monkeypatch, idle_ns=60_000_000_000)  # 60s idle
    out = presence.read_presence(window_seconds=5.0)
    assert out["detected"] is False
    assert out["idle_seconds"] == 60.0


def test_raises_without_ioreg(monkeypatch):
    monkeypatch.setattr(presence.sys, "platform", "darwin")
    monkeypatch.setattr(presence.shutil, "which", lambda name: None)
    with pytest.raises(presence.PresenceError, match="ioreg"):
        presence.read_presence()


def test_raises_when_idle_counter_missing(monkeypatch):
    _fake_ioreg(monkeypatch, idle_ns=None)  # ioreg ran but no HIDIdleTime line
    with pytest.raises(presence.PresenceError, match="HIDIdleTime"):
        presence.read_presence()


def test_raises_on_unsupported_platform(monkeypatch):
    monkeypatch.setattr(presence.sys, "platform", "linux")
    with pytest.raises(presence.PresenceError, match="macOS only"):
        presence.read_presence()
