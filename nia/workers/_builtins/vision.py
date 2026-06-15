"""Vision builtins — the only surface permitted the camera.

This is the camera-domain analogue of `claude.py`. A worker may invoke it only
as a `kind: judgment` action, which the runtime gates behind a manifest-declared
`condition:`. So the camera is considered only when the worker's prior
deterministic steps have produced state the condition evaluates true against. The
capability is declared (`camera:read`) and the use is gated. Telling an app not
to watch you and not handing it the camera key are not the same thing; this
builtin is the key, and the runtime decides when it turns.

Hard dry-run contract, identical in spirit to claude.py: on a dry run, NO camera
is opened, ever. The builtin returns a labeled preview so a worker's shape can be
seen with zero real perception.

On a real run, the capture is delegated to `nia.adapters.camera`, which shells
out to ffmpeg. If no camera or ffmpeg is present, the builtin returns a graceful
captured=False result rather than crashing. Either way the containment guarantee
holds: this code path is unreachable unless the manifest granted `camera:read`
AND the judgment condition evaluated true.
"""
from __future__ import annotations


def describe_frame(*, inputs: dict, context: dict) -> dict:
    """Capture one frame from the camera and return what was captured.

    Inputs:
      reason: why the worker wants to look, recorded for the audit trail.

    On a real capture returns {"captured": True, "path", "device", "captured_at",
    "bytes", "description", "reason"}. On a dry run, or when no camera is
    available, returns captured=False with a label, so an auditor can tell a
    previewed glance from a real one.
    """
    reason = str(inputs.get("reason", ""))

    if context.get("dry_run"):
        return {
            "captured": False,
            "description": "(dry-run preview; camera not opened)",
            "reason": reason,
            "dry_run": True,
        }

    # Real run. Reaching this line already means the manifest granted camera:read
    # and the gating condition evaluated true. Delegate the actual capture to the
    # OS adapter, and degrade gracefully if no camera is wired.
    from nia.adapters import camera

    try:
        cap = camera.capture_frame()
    except camera.CameraError as e:
        return {
            "captured": False,
            "description": f"(camera unavailable: {e})",
            "reason": reason,
        }

    return {
        "captured": True,
        "path": cap["path"],
        "device": cap["device"],
        "captured_at": cap["captured_at"],
        "bytes": cap["bytes"],
        "description": f"captured one frame for: {reason}",
        "reason": reason,
    }
