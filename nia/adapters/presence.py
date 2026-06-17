"""Presence adapter: a cheap, passive signal of recent human input.

A stock Mac has no PIR or motion sensor, so the honest presence signal is HID
idle time: how long since the last keyboard, mouse, or trackpad input. Recent
input means a person is at the machine. This is the cheap gate that decides
whether the expensive, gated camera step is even considered. It opens no camera
and no microphone; it reads a counter the OS already maintains.

OS specific and dependency light: it shells out to `ioreg` on macOS (the same
posture as the camera adapter's ffmpeg), so the core runtime takes on no new
Python dependency. If the signal cannot be read, it raises PresenceError, which
the sensor builtin turns into a graceful detected=false rather than a crash. The
capability is still gated above this layer: nothing here runs unless the manifest
granted sensor:read.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone


class PresenceError(RuntimeError):
    """Raised when the presence signal cannot be read."""


# Matches the ioreg line: `"HIDIdleTime" = 39349852708`
_HID_IDLE_RE = re.compile(r'"HIDIdleTime"\s*=\s*(\d+)')


def read_presence(*, window_seconds: float = 5.0, timeout: int = 5) -> dict:
    """Read a recent-human-input presence signal.

    Returns {"detected", "idle_seconds", "window_seconds", "signal", "read_at"}.
    `detected` is True iff the idle time is within the window, i.e. there was
    human input in the last `window_seconds`.

    Raises PresenceError if the platform is unsupported, ioreg is missing, or the
    idle counter cannot be read.
    """
    idle_seconds = _hid_idle_seconds(timeout=timeout)
    return {
        "detected": idle_seconds <= window_seconds,
        "idle_seconds": round(idle_seconds, 2),
        "window_seconds": window_seconds,
        "signal": "hid",
        "read_at": datetime.now(timezone.utc).isoformat(),
    }


def _hid_idle_seconds(*, timeout: int = 5) -> float:
    """Seconds since the last keyboard, mouse, or trackpad input on macOS."""
    if sys.platform != "darwin":
        # Honest stub, same posture as the Linux camera path: no adapter yet.
        raise PresenceError(
            f"HID presence not implemented on {sys.platform!r}; macOS only for now"
        )
    if shutil.which("ioreg") is None:
        raise PresenceError("ioreg not found on PATH")
    try:
        proc = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise PresenceError(f"ioreg timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise PresenceError(f"ioreg failed: {(proc.stderr or '').strip() or 'unknown error'}")
    m = _HID_IDLE_RE.search(proc.stdout or "")
    if not m:
        raise PresenceError("HIDIdleTime not found in ioreg output")
    return int(m.group(1)) / 1_000_000_000.0
