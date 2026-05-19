"""Find and load worker manifests.

Two locations searched, in order:
  1. ~/.nia/workers/<name>/worker.yaml   (user-installed)
  2. <repo>/nia/workers/<name>/worker.yaml  (built-in reference workers)

User-installed wins on name collision so users can override built-ins.
"""
from __future__ import annotations

from pathlib import Path

from . import manifest as _m
from .types import WorkerManifest


USER_WORKERS = Path.home() / ".nia" / "workers"
BUILTIN_WORKERS = Path(__file__).resolve().parents[1] / "workers"


def _candidate_dirs(name: str) -> list[Path]:
    return [
        USER_WORKERS / name / "worker.yaml",
        BUILTIN_WORKERS / name / "worker.yaml",
    ]


def find(name: str) -> Path | None:
    for p in _candidate_dirs(name):
        if p.is_file():
            return p
    return None


def load(name: str) -> WorkerManifest:
    path = find(name)
    if not path:
        raise FileNotFoundError(
            f"Worker {name!r} not found. Searched: "
            f"{', '.join(str(p.parent) for p in _candidate_dirs(name))}"
        )
    return _m.load(path)


def list_installed() -> list[WorkerManifest]:
    """Return all unique workers across user + built-in locations."""
    seen: dict[str, WorkerManifest] = {}
    # User first so it shadows built-in on collision.
    for root in (USER_WORKERS, BUILTIN_WORKERS):
        if not root.exists():
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            mf = d / "worker.yaml"
            if not mf.is_file():
                continue
            if d.name in seen:
                continue
            try:
                seen[d.name] = _m.load(mf)
            except Exception:
                continue
    return list(seen.values())
