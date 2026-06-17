"""Sensor builtins — cheap, deterministic perception signals.

A presence event is a low-cost passive read: it tells a worker whether a person
is recently active at the machine, without opening a camera or invoking a model.
It is the deterministic gate that decides whether the camera-bearing `vision`
step is even considered. Reading a sensor is itself a capability, so a worker
must declare `sensor:read` to use these.

On a real run the signal comes from the presence adapter (HID idle time on
macOS, recent keyboard, mouse, or trackpad input). The honest reality is that a
stock Mac has no PIR or motion sensor, so "recent human input" is the real
passive presence proxy, and it keeps the cheap-sensor-gates-expensive-camera
architecture intact. On a dry run the signal is simulated from worker config so
the camera gate can be exercised without touching hardware. If the adapter
cannot read the signal, the builtin degrades to detected=false with a reason
rather than raising, so a failed read never accidentally opens the gate.
"""
from __future__ import annotations


def _truthy(v: object) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


def motion_event(*, inputs: dict, context: dict) -> dict:
    """Return whether a person is recently present at a named source.

    Inputs:
      source: a label for the sensor location, e.g. "front-door".
      window_seconds: how recent input must be to count as present (default 5).
      detected: dry-run only. The simulated presence value, templated from
        worker config so the camera gate can be exercised without hardware. A
        real run ignores it and reads the presence adapter directly.

    Returns a dict with at least {"source", "detected"}. On a real run it also
    carries idle_seconds and window_seconds so the run record shows the decision,
    effectively idle_seconds <= window. Never opens a camera, never calls a model.
    """
    source = str(inputs.get("source", ""))
    window = float(inputs.get("window_seconds", 5) or 5)

    # Dry run: simulate from config, never touch hardware.
    if context.get("dry_run"):
        detected = _truthy(inputs.get("detected", False))
        return {
            "source": source,
            "detected": detected,
            "signal": "config",
            "window_seconds": window,
            "dry_run": True,
            "reason": "dry-run simulated presence from config",
        }

    # Real run: read the passive HID presence signal.
    from nia.adapters import presence
    try:
        r = presence.read_presence(window_seconds=window)
    except presence.PresenceError as e:
        return {
            "source": source,
            "detected": False,
            "signal": "hid",
            "window_seconds": window,
            "reason": f"presence signal unavailable: {e}",
        }
    idle = r["idle_seconds"]
    return {
        "source": source,
        "detected": bool(r["detected"]),
        "signal": "hid",
        "idle_seconds": idle,
        "window_seconds": window,
        "read_at": r.get("read_at"),
        "reason": f"idle_seconds={idle} {'<=' if r['detected'] else '>'} window={window:g}",
    }
