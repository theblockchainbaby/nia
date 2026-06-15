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

No camera adapter ships yet. On a real run the builtin captures nothing and says
so, rather than pretending to have seen something. The containment guarantee is
the point and it holds regardless: this code path is unreachable unless the
manifest granted `camera:read` AND the judgment condition evaluated true.
"""
from __future__ import annotations


def describe_frame(*, inputs: dict, context: dict) -> dict:
    """Capture one frame from the camera and return a short description.

    Inputs:
      reason: why the worker wants to look, recorded for the audit trail.

    Returns {"captured": bool, "description": str, "reason": str, "dry_run"?: bool}.

    `captured` is True only when a real adapter opened the camera. No adapter
    ships yet, so it is always False today: on a dry run by contract, and on a
    real run because there is no lens wired. The two cases are distinguishable in
    the result so an auditor can tell a previewed glance from a real one.
    """
    reason = str(inputs.get("reason", ""))

    if context.get("dry_run"):
        return {
            "captured": False,
            "description": "(dry-run preview; camera not opened)",
            "reason": reason,
            "dry_run": True,
        }

    # Real run. A camera adapter would open the lens here and a vision model
    # would describe the frame. Neither is wired yet, so we capture nothing and
    # label it honestly. Reaching this line at all already means the manifest
    # granted camera:read and the gating condition evaluated true.
    return {
        "captured": False,
        "description": "(no camera adapter installed; capture point reached under gate)",
        "reason": reason,
    }
