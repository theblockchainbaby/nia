"""nia status — overall runtime health snapshot."""
from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.table import Table

from nia.runtime import registry, state


def status() -> int:
    console = Console()
    workers = registry.list_installed()
    console.print(f"\n[bold cyan]Nia[/bold cyan]   "
                  f"[dim]{len(workers)} worker(s) installed[/dim]\n")

    t = Table(show_lines=False)
    t.add_column("Worker", style="cyan")
    t.add_column("Trigger", style="green")
    t.add_column("Last run", style="dim")
    t.add_column("Last status")

    for w in workers:
        runs = state.list_runs(w.name, limit=1)
        last_started = "(never)"
        last_status = "[dim]—[/dim]"
        if runs:
            r = runs[0]
            last_started = _short_iso(r.get("started_at", ""))
            last_status = _color_status(r.get("status", "?"))
        trig = (
            f"cron `{w.trigger.cron}`" if w.trigger.cron else
            f"every {w.trigger.interval_seconds}s" if w.trigger.interval_seconds else
            "manual" if w.trigger.manual else "?"
        )
        t.add_row(w.name, trig, last_started, last_status)
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
    if not s:
        return ""
    try:
        return datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return s[:16]
