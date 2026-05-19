"""Worker manifest parser.

Strict by design. Anything that ships with `nia worker install` must pass
through this parser cleanly. Once v0.1 lands publicly, breaking changes
require a schema_version bump.

The runtime invariant this parser enforces:
  A judgment action MUST have a non-empty `condition`.
  No exceptions. This is the architectural thesis encoded in the loader.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .types import (
    SCHEMA_VERSION,
    Action,
    ActionKind,
    Output,
    RetryBackoff,
    RetryPolicy,
    Trigger,
    WorkerManifest,
)


class ManifestError(ValueError):
    """Raised when a worker.yaml is malformed or violates a runtime invariant."""


# Top-level keys allowed on a worker manifest. Unknown keys are rejected
# rather than silently ignored — this keeps the protocol surface explicit.
_TOP_LEVEL_KEYS = {
    "name", "version", "schema_version", "description", "author",
    "homepage", "license", "tags", "trigger", "permissions", "config",
    "actions", "outputs",
}

_ACTION_KEYS = {
    "id", "kind", "impl", "inputs", "when", "timeout", "retry",
    "condition", "cost_ceiling_usd",
}

_TRIGGER_KEYS = {"cron", "interval", "manual", "event"}


def load(path: Path) -> WorkerManifest:
    """Load and validate a worker.yaml file."""
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ManifestError(f"{path}: top-level must be a mapping")

    unknown = set(raw) - _TOP_LEVEL_KEYS
    if unknown:
        raise ManifestError(f"{path}: unknown top-level keys: {sorted(unknown)}")

    name = _require_str(raw, "name", path)
    if not _is_kebab(name):
        raise ManifestError(f"{path}: name must be kebab-case, got {name!r}")
    version = _require_str(raw, "version", path)
    schema_version = raw.get("schema_version", SCHEMA_VERSION)
    if str(schema_version) != SCHEMA_VERSION:
        raise ManifestError(
            f"{path}: schema_version {schema_version!r} not supported "
            f"by runtime (expected {SCHEMA_VERSION!r})"
        )

    trigger = _parse_trigger(raw.get("trigger"), path)
    actions = _parse_actions(raw.get("actions"), path)
    outputs = _parse_outputs(raw.get("outputs", []), path)

    return WorkerManifest(
        name=name,
        version=version,
        schema_version=str(schema_version),
        description=str(raw.get("description", "")),
        author=str(raw.get("author", "")),
        homepage=str(raw.get("homepage", "")),
        license=str(raw.get("license", "")),
        tags=list(raw.get("tags") or []),
        trigger=trigger,
        permissions=list(raw.get("permissions") or []),
        config=dict(raw.get("config") or {}),
        actions=actions,
        outputs=outputs,
        source_path=path,
    )


def _parse_trigger(raw: Any, path: Path) -> Trigger:
    if not isinstance(raw, dict):
        raise ManifestError(f"{path}: `trigger` is required and must be a mapping")
    unknown = set(raw) - _TRIGGER_KEYS
    if unknown:
        raise ManifestError(f"{path}: trigger has unknown keys: {sorted(unknown)}")
    set_keys = [k for k in _TRIGGER_KEYS if raw.get(k) not in (None, False)]
    if len(set_keys) != 1:
        raise ManifestError(
            f"{path}: trigger must set exactly one of "
            f"{sorted(_TRIGGER_KEYS)} (found {set_keys})"
        )
    t = Trigger()
    if "cron" in raw and raw["cron"]:
        t.cron = str(raw["cron"])
    if "interval" in raw and raw["interval"]:
        iv = raw["interval"]
        if not isinstance(iv, dict):
            raise ManifestError(f"{path}: trigger.interval must be a mapping")
        total = 0
        total += int(iv.get("seconds", 0))
        total += int(iv.get("minutes", 0)) * 60
        total += int(iv.get("hours", 0)) * 3600
        total += int(iv.get("days", 0)) * 86400
        if total <= 0:
            raise ManifestError(f"{path}: trigger.interval must be > 0")
        t.interval_seconds = total
    if raw.get("manual"):
        t.manual = True
    if raw.get("event"):
        t.event = dict(raw["event"])
    return t


def _parse_actions(raw: Any, path: Path) -> list[Action]:
    if not isinstance(raw, list) or not raw:
        raise ManifestError(f"{path}: `actions` is required and must be a non-empty list")
    seen: set[str] = set()
    out: list[Action] = []
    for i, a in enumerate(raw):
        if not isinstance(a, dict):
            raise ManifestError(f"{path}: actions[{i}] must be a mapping")
        unknown = set(a) - _ACTION_KEYS
        if unknown:
            raise ManifestError(f"{path}: actions[{i}] has unknown keys: {sorted(unknown)}")
        aid = _require_str(a, "id", path)
        if aid in seen:
            raise ManifestError(f"{path}: duplicate action id {aid!r}")
        seen.add(aid)
        try:
            kind = ActionKind(a.get("kind", "deterministic"))
        except ValueError:
            raise ManifestError(
                f"{path}: actions[{aid}].kind must be one of "
                f"{[k.value for k in ActionKind]}"
            )
        impl = _require_str(a, "impl", path)
        if not (impl.startswith("builtin:") or impl.startswith("file:")):
            raise ManifestError(
                f"{path}: actions[{aid}].impl must start with `builtin:` or `file:`"
            )

        # The runtime invariant: judgment requires a condition.
        condition = a.get("condition")
        if kind == ActionKind.JUDGMENT and not condition:
            raise ManifestError(
                f"{path}: actions[{aid}] kind=judgment requires a `condition` "
                f"(this is the runtime's cost-guard contract)"
            )

        retry = RetryPolicy()
        if "retry" in a and a["retry"]:
            rraw = a["retry"]
            if not isinstance(rraw, dict):
                raise ManifestError(f"{path}: actions[{aid}].retry must be a mapping")
            retry.attempts = int(rraw.get("attempts", 1))
            if "backoff" in rraw:
                try:
                    retry.backoff = RetryBackoff(rraw["backoff"])
                except ValueError:
                    raise ManifestError(
                        f"{path}: actions[{aid}].retry.backoff must be one of "
                        f"{[b.value for b in RetryBackoff]}"
                    )

        out.append(Action(
            id=aid,
            kind=kind,
            impl=impl,
            inputs=dict(a.get("inputs") or {}),
            when=str(a.get("when", "true")),
            timeout=int(a.get("timeout", 30)),
            retry=retry,
            condition=str(condition) if condition else None,
            cost_ceiling_usd=(
                float(a["cost_ceiling_usd"]) if "cost_ceiling_usd" in a else None
            ),
        ))
    return out


def _parse_outputs(raw: Any, path: Path) -> list[Output]:
    if not isinstance(raw, list):
        raise ManifestError(f"{path}: outputs must be a list")
    out: list[Output] = []
    for i, o in enumerate(raw):
        if not isinstance(o, dict):
            raise ManifestError(f"{path}: outputs[{i}] must be a mapping")
        out.append(Output(
            id=_require_str(o, "id", path),
            description=str(o.get("description", "")),
            path=o.get("path"),
            counter=o.get("counter"),
        ))
    return out


def _require_str(d: dict, key: str, path: Path) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v:
        raise ManifestError(f"{path}: required field `{key}` missing or not a string")
    return v


def _is_kebab(s: str) -> bool:
    return bool(s) and all(c.islower() or c.isdigit() or c == "-" for c in s) and not s.startswith("-")
