"""Local run state persistence.

Runs are written to ~/.nia/runs/<worker>/<run-id>.json as they execute, so
`nia inspect` and `nia logs` can read them without coupling to the executor.

JSON is intentional — readable from any tool, including `jq`. Infrastructure
state should always be inspectable without launching Python.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .types import Run, RunStatus


NIA_HOME = Path.home() / ".nia"
RUNS_DIR = NIA_HOME / "runs"


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def runs_dir_for(worker: str) -> Path:
    d = RUNS_DIR / worker
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_run(run: Run) -> Path:
    path = runs_dir_for(run.worker) / f"{run.id}.json"
    path.write_text(json.dumps(_to_jsonable(asdict(run)), indent=2, default=str))
    return path


def list_runs(worker: str, limit: int = 10) -> list[dict]:
    """Return the most recent runs for a worker, newest first."""
    d = runs_dir_for(worker)
    files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict] = []
    for f in files[:limit]:
        try:
            out.append(json.loads(f.read_text()))
        except Exception:
            continue
    return out


def list_workers_with_runs() -> list[str]:
    if not RUNS_DIR.exists():
        return []
    return sorted(p.name for p in RUNS_DIR.iterdir() if p.is_dir())


def _to_jsonable(obj):
    """asdict() gives us enums and datetimes — coerce to strings."""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    return obj
