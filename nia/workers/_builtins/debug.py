"""Debug builtins. Useful for hello-world workers and runtime sanity checks."""
from __future__ import annotations

from typing import Any


def echo(*, inputs: dict, context: dict) -> dict:
    """Print the input `message` and return it.

    In dry_run mode we still print, prefixed with [DRY-RUN]. Pure debug; never
    touches the network or filesystem outside stdout.
    """
    msg = str(inputs.get("message", ""))
    prefix = "[DRY-RUN] " if context.get("dry_run") else ""
    print(f"{prefix}{msg}")
    return {"echoed": msg}


def counter(*, inputs: dict, context: dict) -> dict:
    """Return whatever integer is in `inputs.value`. Used in tests."""
    return {"value": int(inputs.get("value", 0))}
