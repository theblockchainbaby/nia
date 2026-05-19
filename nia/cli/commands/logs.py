"""nia logs <worker> [-n N] — tail recent runs for a worker."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from nia.runtime import state


def logs(worker: str, *, limit: int = 10) -> int:
    console = Console()
    runs = state.list_runs(worker, limit=limit)
    if not runs:
        console.print(f"[dim]No runs found for {worker!r}.[/dim]")
        return 0

    t = Table(title=f"Recent runs — {worker}", show_lines=False)
    t.add_column("Started", style="dim")
    t.add_column("Status")
    t.add_column("Dur", justify="right")
    t.add_column("Actions")
    t.add_column("Dry", justify="center")
    t.add_column("Run ID", style="dim")

    for r in runs:
        action_summary = _summarize_actions(r.get("actions", []))
        t.add_row(
            _short_iso(r.get("started_at", "")),
            _color_status(r.get("status", "?")),
            _duration_str(r),
            action_summary,
            "✓" if r.get("dry_run") else "",
            r.get("id", ""),
        )
    console.print(t)
    return 0


def _color_status(s: str) -> str:
    return {
        "success":  "[green]success[/green]",
        "failed":   "[red]failed[/red]",
        "running":  "[yellow]running[/yellow]",
        "skipped":  "[dim]skipped[/dim]",
        "pending":  "[dim]pending[/dim]",
    }.get(s, s)


def _short_iso(s: str) -> str:
    return s[:19].replace("T", " ") if s else ""


def _summarize_actions(actions: list[dict]) -> str:
    if not actions:
        return ""
    ok = sum(1 for a in actions if a.get("status") == "success")
    skip = sum(1 for a in actions if a.get("status") == "skipped")
    fail = sum(1 for a in actions if a.get("status") == "failed")
    parts = [f"[green]{ok}✓[/green]"]
    if skip: parts.append(f"[dim]{skip} skipped[/dim]")
    if fail: parts.append(f"[red]{fail} fail[/red]")
    return " ".join(parts)


def _duration_str(run: dict) -> str:
    from datetime import datetime
    s, f = run.get("started_at"), run.get("finished_at")
    if not s or not f:
        return ""
    try:
        ms = int((datetime.fromisoformat(f) - datetime.fromisoformat(s)).total_seconds() * 1000)
        return f"{ms}ms"
    except Exception:
        return ""
