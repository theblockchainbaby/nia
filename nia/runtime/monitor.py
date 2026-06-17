"""The reference monitor: the mandatory mediation layer for action dispatch.

Every action the executor runs passes through `authorize_action` first. It folds
the two authorization questions into one decision, made BEFORE any
implementation is resolved or invoked:

  - Capability: do the worker's granted permissions cover what this action's
    impl requires? If not, DENY. A denial is a containment event, not normal
    control flow.
  - Gates: does the `when` predicate hold, and for judgment steps the
    `condition`? If not, SKIP. A skip is normal control flow: the manifest
    allowed the action, runtime context says not now.

Only on ALLOW does the monitor resolve the implementation and return the
callable. DENY and SKIP carry no callable. That is the invariant the executor
depends on and the tests pin down:

    the executor can invoke an implementation only if the monitor returned
    ALLOW for that action.

Resolution lives here, not in the executor, on purpose. The executor has no
other route to a builtin callable, so a future bypass would have to reimplement
importlib resolution somewhere else, which is loud and reviewable instead of a
call to an innocent looking helper. Python cannot make this airtight, but it
makes a bypass obvious.

This is dispatch time mediation, defense in depth. It does not replace the load
time permission validation in manifest.py; it asserts the same property again at
the one point where an action actually runs.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from . import condition, permissions
from .types import Action, ActionKind


class ImplError(RuntimeError):
    pass


class Outcome(str, Enum):
    ALLOW = "allow"   # authorized; carries the resolved callable
    SKIP = "skip"     # manifest allowed it, a gate says not now (normal flow)
    DENY = "deny"     # this dispatch is not authorized (containment event)


@dataclass
class Decision:
    outcome: Outcome
    reason: str = ""
    decided_by: str = "ok"          # capability | when | condition | ok
    fn: Callable | None = None      # present iff ALLOW and resolution succeeded
    resolution_error: str | None = None
    audit: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.outcome is Outcome.ALLOW


def authorize_action(action: Action, ctx: dict, *, granted: list[str]) -> Decision:
    """The single authorization chokepoint.

    Returns a Decision. Only an ALLOW outcome carries a resolved callable; DENY
    and SKIP carry none. Capability is checked before the gates, because a denial
    is a containment decision that precedes the question of whether it is time to
    run.
    """
    required = sorted(permissions.required_for_impl(action.impl))
    granted_sorted = sorted(set(granted))

    def _audit(outcome: Outcome, decided_by: str, reason: str) -> dict:
        return {
            "outcome": outcome.value,
            "decided_by": decided_by,
            "required": required,
            "granted": granted_sorted,
            "reason": reason,
        }

    # 1. Capability. A denial is a containment event, evaluated before the gates.
    missing = permissions.missing_permissions(action.impl, list(granted))
    if missing:
        reason = (
            f"action {action.id!r} impl {action.impl!r} requires "
            f"{sorted(missing)}, not granted by the worker"
        )
        return Decision(Outcome.DENY, reason=reason, decided_by="capability",
                        audit=_audit(Outcome.DENY, "capability", reason))

    # 2. `when` gate, all kinds. A failed gate is a SKIP, not a denial.
    if not condition.evaluate(action.when, ctx):
        reason = f"when={action.when!r} evaluated false"
        return Decision(Outcome.SKIP, reason=reason, decided_by="when",
                        audit=_audit(Outcome.SKIP, "when", reason))

    # 3. `condition` gate, judgment steps only.
    if action.kind == ActionKind.JUDGMENT and action.condition is not None:
        if not condition.evaluate(action.condition, ctx):
            reason = f"judgment condition {action.condition!r} false, step not invoked"
            return Decision(Outcome.SKIP, reason=reason, decided_by="condition",
                            audit=_audit(Outcome.SKIP, "condition", reason))

    # 4. ALLOW, and only now is the implementation resolved. A resolution failure
    # is a mechanism failure (broken impl), not a denial: still no callable.
    try:
        fn = _resolve_impl(action.impl)
    except Exception as e:
        return Decision(Outcome.ALLOW, decided_by="ok", fn=None,
                        resolution_error=f"impl resolution failed: {e}",
                        audit=_audit(Outcome.ALLOW, "ok", "allowed; resolution failed"))
    return Decision(Outcome.ALLOW, decided_by="ok", fn=fn,
                    audit=_audit(Outcome.ALLOW, "ok", "allowed"))


def _resolve_impl(impl: str) -> Callable:
    """`builtin:<module>.<fn>` to callable. Private to the monitor: the executor
    has no other route to a builtin. `file:` scheme is deferred to v0.2."""
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
