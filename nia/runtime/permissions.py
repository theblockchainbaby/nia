"""Soft permission enforcement: a worker manifest must declare the
permissions every action it uses actually needs.

This is "soft" in the sense that the runtime does NOT enforce permissions
at the syscall layer (that requires real sandboxing, which is Phase II
research). What it DOES enforce, at manifest load time, is that the
worker's `permissions:` block honestly reflects what the actions inside
the worker are going to do. A worker that imports `email.sweep_recent`
must declare `imap:read`. A worker that uses `claude.classify` must
declare `llm:claude`. Decorative `permissions:` blocks are rejected.

The runtime invariant:
  For every action with `impl: builtin:<module>.<fn>`, the worker's
  `permissions:` list must cover the action's declared requirements.

A grant `g` covers a requirement `r` iff `g == r` or `g.startswith(r + ":")`
(i.e., the grant is exactly the requirement, or more specific). A grant
like `filesystem:write:~/.nia/briefs` therefore covers `filesystem:write`.
"""
from __future__ import annotations


# What each bundled builtin needs in the worker's `permissions:` block.
# Builtins not listed here are assumed to need no permissions (e.g.,
# debug.echo).
BUILTIN_REQUIREMENTS: dict[str, set[str]] = {
    # email
    "email.sweep_recent": {"imap:read"},
    # notion
    "notion.due_reminders": {"notion:read"},
    "notion.email_sync": {"notion:write", "imap:read"},
    "notion.git_sync": {"notion:write", "filesystem:read"},
    "notion.stripe_sync": {"notion:write", "stripe:read"},
    # claude (judgment)
    "claude.classify": {"llm:claude"},
    # imessage
    "imessage.send_pdf": {"imessage:send"},
    # render
    "render.morning_brief_pdf": {"filesystem:write"},
    # debug — explicit empty for clarity
    "debug.echo": set(),
}


def required_for_impl(impl: str) -> set[str]:
    """Return the set of permissions required by `impl: builtin:<module>.<fn>`.

    Unknown impls (e.g., `file:<path>:<fn>` for v0.3) return an empty set;
    we cannot statically know their requirements.
    """
    if not impl.startswith("builtin:"):
        return set()
    key = impl[len("builtin:"):]
    return BUILTIN_REQUIREMENTS.get(key, set())


def covers(grant: str, requirement: str) -> bool:
    """True iff `grant` covers `requirement`.

    Equality matches. A more-specific grant (with extra `:resource`) also
    matches. The reverse does not: a grant of `imap` does not cover
    `imap:read` (the grant is too vague).
    """
    if grant == requirement:
        return True
    return grant.startswith(requirement + ":")


def missing_permissions(impl: str, granted: list[str]) -> set[str]:
    """Return the requirements for `impl` that are not covered by `granted`.

    Empty set means the worker has declared everything the impl needs.
    """
    required = required_for_impl(impl)
    granted_set = set(granted)
    missing: set[str] = set()
    for req in required:
        if any(covers(g, req) for g in granted_set):
            continue
        missing.add(req)
    return missing
