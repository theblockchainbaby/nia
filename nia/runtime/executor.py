"""Worker execution engine.

The minimum viable executor for v0.1:
  - Load a manifest
  - Iterate actions in order
  - For each: resolve impl, evaluate `when`, execute, capture result
  - For judgment kind: also evaluate `condition` BEFORE running
  - Persist the Run to ~/.nia/runs/<worker>/<id>.json

What's intentionally NOT in v0.1:
  - Parallel actions (sequential only; deterministic order)
  - Retry policy (declared but not enforced yet)
  - Timeout enforcement (declared but advisory)
  - Cost ceiling enforcement (declared but advisory)

These ship in v0.2. The protocol surface (manifest fields) is locked NOW so
adding them later does not break existing manifests.
"""
from __future__ import annotations

import importlib
import os
import traceback
from typing import Any

from . import condition, state
from .types import (
    Action,
    ActionKind,
    ActionResult,
    Run,
    RunStatus,
    WorkerManifest,
    utc_now,
)


class ImplError(RuntimeError):
    pass


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
            result = _run_action(action, ctx, dry_run=dry_run)
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


def _run_action(action: Action, ctx: dict, *, dry_run: bool) -> ActionResult:
    started = utc_now()

    # `when` gate — applies to all action kinds.
    if not condition.evaluate(action.when, ctx):
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.SKIPPED,
            started_at=started,
            finished_at=utc_now(),
            skipped_reason=f"when={action.when!r} evaluated false",
        )

    # `condition` gate — only judgment actions have one (enforced by parser).
    if action.kind == ActionKind.JUDGMENT and action.condition is not None:
        if not condition.evaluate(action.condition, ctx):
            return ActionResult(
                action_id=action.id,
                kind=action.kind,
                status=RunStatus.SKIPPED,
                started_at=started,
                finished_at=utc_now(),
                skipped_reason=(
                    f"judgment condition {action.condition!r} false — LLM not invoked"
                ),
            )

    # Resolve and invoke the impl.
    try:
        fn = _resolve_impl(action.impl)
    except Exception as e:
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.FAILED,
            started_at=started,
            finished_at=utc_now(),
            error=f"impl resolution failed: {e}",
        )

    inputs = _render_inputs(action.inputs, ctx)
    invocation_ctx = {
        "dry_run": dry_run,
        "worker_config": ctx["config"],
        "prior_actions": ctx["actions"],
    }

    try:
        result_obj = fn(inputs=inputs, context=invocation_ctx)
        if not isinstance(result_obj, dict):
            result_obj = {"value": result_obj}
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.SUCCESS,
            started_at=started,
            finished_at=utc_now(),
            results=result_obj,
        )
    except Exception as e:
        return ActionResult(
            action_id=action.id,
            kind=action.kind,
            status=RunStatus.FAILED,
            started_at=started,
            finished_at=utc_now(),
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}",
        )


def _resolve_impl(impl: str):
    """`builtin:<module>.<fn>` → callable. file: scheme deferred to v0.2."""
    if impl.startswith("builtin:"):
        path = impl[len("builtin:"):]
        if "." not in path:
            raise ImplError(f"builtin impl must be `module.fn`, got {impl!r}")
        module_path, fn_name = path.rsplit(".", 1)
        mod = importlib.import_module(f"nia.workers._builtins.{module_path}")
        if not hasattr(mod, fn_name):
            raise ImplError(f"builtin {impl!r}: function {fn_name!r} not found")
        return getattr(mod, fn_name)
    if impl.startswith("file:"):
        raise ImplError("file: impls not supported in v0.1 (coming v0.2)")
    raise ImplError(f"unknown impl scheme: {impl!r}")


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
