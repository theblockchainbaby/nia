"""Worker execution engine.

The minimum viable executor for v0.1:
  - Load a manifest
  - Iterate actions in order
  - For each: ask the reference monitor to authorize the dispatch, and only on
    ALLOW invoke the resolved impl, capturing the result
  - Persist the Run to ~/.nia/runs/<worker>/<id>.json

Authorization is not done here. Every action passes through
`monitor.authorize_action`, which folds capability and the `when`/`condition`
gates into one decision and is the only thing that resolves an implementation.
The executor can invoke an implementation only if the monitor returned ALLOW for
that action. See nia/runtime/monitor.py.

What's intentionally NOT in v0.1:
  - Parallel actions (sequential only; deterministic order)
  - Retry policy (declared but not enforced yet)
  - Timeout enforcement (declared but advisory)
  - Cost ceiling enforcement (declared but advisory)

These ship in v0.2. The protocol surface (manifest fields) is locked NOW so
adding them later does not break existing manifests.
"""
from __future__ import annotations

import os
import traceback
from typing import Any

from . import condition, monitor, state
from .types import (
    Action,
    ActionResult,
    Run,
    RunStatus,
    WorkerManifest,
    utc_now,
)


def execute(manifest: WorkerManifest, *, dry_run: bool = False,
            trigger_source: str = "manual") -> Run:
    """Run a worker once. Returns the completed Run (also persisted to disk)."""
    run = Run(
        id=state.new_run_id(),
        worker=manifest.name,
        worker_version=manifest.version,
        started_at=utc_now(),
        status=RunStatus.RUNNING,
        dry_run=dry_run,
        trigger_source=trigger_source,
    )
    state.save_run(run)

    # Context made available to `when` / `condition` expressions.
    # `env` exposes os.environ so manifests can reference secrets without
    # baking them into the YAML.
    ctx: dict[str, Any] = {
        "config": dict(manifest.config),
        "env": dict(os.environ),
        "actions": {},
    }

    try:
        for action in manifest.actions:
            result = _run_action(action, ctx, dry_run=dry_run,
                                 granted=manifest.permissions)
            run.actions.append(result)
            # Expose to subsequent `when` / `condition` evaluations.
            ctx["actions"][action.id] = {
                "results": dict(result.results),
                "status": result.status.value,
            }
            # Stop on first hard failure.
            if result.status == RunStatus.FAILED:
                run.status = RunStatus.FAILED
                run.error = result.error
                break
        else:
            run.status = RunStatus.SUCCESS
    except Exception as e:
        run.status = RunStatus.FAILED
        run.error = f"{type(e).__name__}: {e}"
    finally:
        run.finished_at = utc_now()
        state.save_run(run)

    return run


def _run_action(action: Action, ctx: dict, *, dry_run: bool,
                granted: list[str]) -> ActionResult:
    started = utc_now()

    # Mandatory mediation: the executor obtains a callable only through the
    # monitor, and only on an ALLOW decision.
    decision = monitor.authorize_action(action, ctx, granted=granted)

    if decision.outcome is monitor.Outcome.DENY:
        # A denial is a containment event, distinct from a skip.
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.FAILED,
            started_at=started,
            finished_at=utc_now(),
            error=f"denied: {decision.reason}",
            audit=decision.audit,
        )

    if decision.outcome is monitor.Outcome.SKIP:
        # The manifest allowed this action; a gate said not now. Normal flow.
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.SKIPPED,
            started_at=started,
            finished_at=utc_now(),
            skipped_reason=decision.reason,
            audit=decision.audit,
        )

    # ALLOW. A missing callable means resolution failed (a broken impl), which
    # is an execution failure, not an authorization denial.
    if decision.fn is None:
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.FAILED,
            started_at=started,
            finished_at=utc_now(),
            error=decision.resolution_error or "impl resolution failed",
            audit=decision.audit,
        )

    inputs = _render_inputs(action.inputs, ctx)
    invocation_ctx = {
        "dry_run": dry_run,
        "worker_config": ctx["config"],
        "prior_actions": ctx["actions"],
    }

    try:
        result_obj = decision.fn(inputs=inputs, context=invocation_ctx)
        if not isinstance(result_obj, dict):
            result_obj = {"value": result_obj}
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.SUCCESS,
            started_at=started,
            finished_at=utc_now(),
            results=result_obj,
            audit=decision.audit,
        )
    except Exception as e:
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.FAILED,
            started_at=started,
            finished_at=utc_now(),
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}",
            audit=decision.audit,
        )


def _render_inputs(inputs: dict, ctx: dict) -> dict:
    """Minimal templating: `{{ config.x }}` and `{{ actions.id.results.y }}`."""
    rendered: dict[str, Any] = {}
    for k, v in inputs.items():
        rendered[k] = _render_value(v, ctx)
    return rendered


def _render_value(v: Any, ctx: dict) -> Any:
    if isinstance(v, str) and v.startswith("{{") and v.endswith("}}"):
        expr = v[2:-2].strip()
        return condition.access(expr, ctx)
    if isinstance(v, list):
        return [_render_value(x, ctx) for x in v]
    if isinstance(v, dict):
        return {k: _render_value(x, ctx) for k, x in v.items()}
    return v
