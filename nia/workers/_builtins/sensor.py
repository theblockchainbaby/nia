"""Sensor builtins — cheap, deterministic perception signals.

A motion event is a low-cost passive read: it tells a worker whether something
moved at a named source, without opening a camera or invoking a model. It is the
deterministic gate that decides whether the camera-bearing `vision` step is even
considered. Reading a sensor is itself a capability, so a worker must declare
`sensor:read` to use these.

No hardware adapter ships yet (the same honest-stub posture as the Linux
adapter). The demo drives `detected` from the worker's config so the camera gate
can be exercised without a sensor on the bench. A real adapter replaces the body
of `motion_event` with a hardware read; the manifest and the gating do not change.
"""
from __future__ import annotations


def motion_event(*, inputs: dict, context: dict) -> dict:
    """Return whether motion was detected at a named source.

    Inputs:
      source: a label for the sensor location, e.g. "front-door".
      detected: the motion signal. The demo templates this from worker config so
        the camera gate can be exercised without hardware; a real adapter ignores
        it and reads the sensor directly.

    Returns {"source": str, "detected": bool}. Never opens a camera, never calls
    a model. Safe to run on every tick.
    """
    return {
        "source": str(inputs.get("source", "")),
        "detected": bool(inputs.get("detected", False)),
    }
