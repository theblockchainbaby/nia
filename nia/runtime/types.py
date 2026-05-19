"""Core types for the Nia runtime.

These dataclasses are the in-memory representation of a parsed worker.yaml
plus the run-state captured during execution. Kept stdlib-only so the parser
can validate manifests without touching disk or network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"


class ActionKind(str, Enum):
    DETERMINISTIC = "deterministic"
    JUDGMENT = "judgment"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RetryBackoff(str, Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    NONE = "none"


@dataclass
class RetryPolicy:
    attempts: int = 1
    backoff: RetryBackoff = RetryBackoff.NONE


@dataclass
class Action:
    id: str
    kind: ActionKind
    impl: str
    inputs: dict[str, Any] = field(default_factory=dict)
    when: str = "true"
    timeout: int = 30
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    # Required for judgment steps; ignored for deterministic.
    condition: str | None = None
    # Optional cost guard for judgment steps.
    cost_ceiling_usd: float | None = None


@dataclass
class Trigger:
    """Exactly one of these fields is non-None."""
    cron: str | None = None
    interval_seconds: int | None = None
    manual: bool = False
    event: dict[str, str] | None = None


@dataclass
class Output:
    id: str
    description: str = ""
    path: str | None = None
    counter: str | None = None


@dataclass
class WorkerManifest:
    name: str
    version: str
    schema_version: str
    trigger: Trigger
    actions: list[Action]
    description: str = ""
    author: str = ""
    homepage: str = ""
    license: str = ""
    tags: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    outputs: list[Output] = field(default_factory=list)
    # Resolved by the registry; not from YAML.
    source_path: Path | None = None


@dataclass
class ActionResult:
    action_id: str
    kind: ActionKind
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    skipped_reason: str | None = None
    # Judgment-only: actual cost incurred.
    cost_usd: float | None = None


@dataclass
class Run:
    """One execution of a worker. Persisted to ~/.nia/runs/<worker>/<id>.json"""
    id: str
    worker: str
    worker_version: str
    started_at: datetime
    finished_at: datetime | None = None
    status: RunStatus = RunStatus.PENDING
    dry_run: bool = False
    trigger_source: str = "manual"
    actions: list[ActionResult] = field(default_factory=list)
    error: str | None = None

    @property
    def duration_ms(self) -> int | None:
        if not self.finished_at:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
