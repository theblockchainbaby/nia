"""The reference monitor is the mandatory mediation layer for action dispatch.

The spine of this file, and the property the whole PR exists to guarantee:

    the executor can invoke an implementation only if the monitor returned
    ALLOW for that action.

Everything else is supporting evidence. DENY (this dispatch is not authorized)
is kept distinct from SKIP (the manifest allowed it, a gate says not now): one is
a containment event, the other is normal control flow.
"""
from __future__ import annotations

import yaml

from nia.runtime import executor, monitor
from nia.runtime.manifest import load
from nia.runtime.types import Action, ActionKind, RunStatus
from nia.workers._builtins import debug


def _ctx(actions: dict | None = None) -> dict:
    return {"config": {}, "env": {}, "actions": actions or {}}


# ─── authorize_action: no impl resolves without an allow decision ─────────


def test_capability_deny_returns_no_callable():
    """An under-permissioned dispatch is DENIED before any gate, and yields no
    callable. This is the containment case."""
    action = Action(id="glance", kind=ActionKind.JUDGMENT,
                    impl="builtin:vision.describe_frame", condition="true")
    d = monitor.authorize_action(action, _ctx(), granted=[])
    assert d.outcome is monitor.Outcome.DENY
    assert d.fn is None
    assert d.decided_by == "capability"
    assert "camera:read" in d.reason


def test_when_false_skips_before_resolution():
    """A false `when` is a SKIP, not a denial, and resolves nothing."""
    action = Action(id="e", kind=ActionKind.DETERMINISTIC,
                    impl="builtin:debug.echo", when="false")
    d = monitor.authorize_action(action, _ctx(), granted=[])
    assert d.outcome is monitor.Outcome.SKIP
    assert d.fn is None
    assert d.decided_by == "when"


def test_judgment_condition_false_skips_and_resolves_nothing():
    """A judgment step whose condition is false is SKIPPED with no callable."""
    action = Action(id="glance", kind=ActionKind.JUDGMENT,
                    impl="builtin:vision.describe_frame",
                    condition="actions.m.results.detected == true")
    ctx = _ctx({"m": {"results": {"detected": False}, "status": "success"}})
    d = monitor.authorize_action(action, ctx, granted=["camera:read"])
    assert d.outcome is monitor.Outcome.SKIP
    assert d.fn is None
    assert d.decided_by == "condition"


def test_allow_resolves_and_returns_callable():
    """Only on ALLOW does the monitor resolve and hand back a callable."""
    action = Action(id="m", kind=ActionKind.DETERMINISTIC,
                    impl="builtin:sensor.motion_event")
    d = monitor.authorize_action(action, _ctx(), granted=["sensor:read"])
    assert d.outcome is monitor.Outcome.ALLOW
    assert callable(d.fn)
    assert d.decided_by == "ok"


def test_resolution_failure_is_allow_with_error_not_deny():
    """A broken impl is a mechanism failure, not an authorization denial. The
    decision is ALLOW with no callable and a resolution error, never DENY."""
    action = Action(id="x", kind=ActionKind.DETERMINISTIC,
                    impl="builtin:nope.missing")
    d = monitor.authorize_action(action, _ctx(), granted=[])
    assert d.outcome is monitor.Outcome.ALLOW
    assert d.fn is None
    assert "impl resolution failed" in (d.resolution_error or "")


def test_every_decision_carries_an_audit_record():
    deny = monitor.authorize_action(
        Action(id="g", kind=ActionKind.JUDGMENT,
               impl="builtin:vision.describe_frame", condition="true"),
        _ctx(), granted=[])
    allow = monitor.authorize_action(
        Action(id="m", kind=ActionKind.DETERMINISTIC,
               impl="builtin:sensor.motion_event"),
        _ctx(), granted=["sensor:read"])
    for d in (deny, allow):
        assert d.audit["outcome"] == d.outcome.value
        assert {"decided_by", "required", "granted", "reason"} <= set(d.audit)


# ─── the spine, through the executor ─────────────────────────────────────


_MIN_WORKER = {
    "name": "monitor-spine",
    "version": "0.1.0",
    "schema_version": "0.1",
    "trigger": {"manual": True},
    "permissions": [],
    "actions": [
        {"id": "echo", "kind": "deterministic",
         "impl": "builtin:debug.echo", "inputs": {"message": "hi"}},
    ],
}


def _load_min(tmp_path):
    p = tmp_path / "worker.yaml"
    p.write_text(yaml.safe_dump(_MIN_WORKER))
    return load(p)


def test_executor_invokes_impl_only_on_allow(tmp_path, monkeypatch):
    """The spine. Force the monitor to DENY and the builtin must never run."""
    def explode(**kwargs):
        raise AssertionError("builtin must not run when the monitor denies")
    monkeypatch.setattr(debug, "echo", explode)

    def forced_deny(action, ctx, *, granted):
        return monitor.Decision(
            monitor.Outcome.DENY, reason="forced deny", decided_by="capability",
            audit={"outcome": "deny", "decided_by": "capability",
                   "required": [], "granted": [], "reason": "forced deny"})
    monkeypatch.setattr(monitor, "authorize_action", forced_deny)

    run = executor.execute(_load_min(tmp_path), dry_run=False)

    echo = run.actions[0]
    assert echo.status == RunStatus.FAILED
    assert "denied" in (echo.error or "")


def test_executor_allow_runs_and_records_audit(tmp_path):
    """A real ALLOW runs the builtin and stamps the audit record on the result."""
    run = executor.execute(_load_min(tmp_path), dry_run=False)
    echo = run.actions[0]
    assert echo.status == RunStatus.SUCCESS
    assert echo.audit is not None
    assert echo.audit["outcome"] == "allow"


def test_executor_has_no_independent_resolution_path():
    """Supporting evidence, not the proof: resolution lives in the monitor, so
    the executor exposes no way to obtain a builtin callable on its own."""
    assert not hasattr(executor, "_resolve_impl")
    assert not hasattr(executor, "ImplError")
