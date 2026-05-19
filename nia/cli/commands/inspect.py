"""nia inspect worker <name> — the wedge command.

The reason inspect matters: most "agent" products are black boxes. A runtime
where you can read the worker's mind in 200ms is a different category. This
command IS the trust pitch in CLI form.
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nia.runtime import registry, state


def inspect_worker(name: str) -> int:
    console = Console()
    try:
        m = registry.load(name)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    # Header
    trig = (
        f"cron `{m.trigger.cron}`" if m.trigger.cron else
        f"every {m.trigger.interval_seconds}s" if m.trigger.interval_seconds else
        "manual only" if m.trigger.manual else
        f"event {m.trigger.event}" if m.trigger.event else "?"
    )
    console.print(Panel.fit(
        f"[bold cyan]{m.name}[/bold cyan]  v{m.version}\n"
        f"[dim]{m.description}[/dim]\n\n"
        f"Trigger:      [green]{trig}[/green]\n"
        f"Permissions:  {', '.join(m.permissions) or '[dim]none declared[/dim]'}\n"
        f"Source:       [dim]{m.source_path}[/dim]",
        border_style="cyan",
    ))

    # Actions table
    t = Table(title="Actions", show_lines=False)
    t.add_column("#", style="dim", justify="right")
    t.add_column("ID", style="cyan")
    t.add_column("Kind")
    t.add_column("Impl")
    t.add_column("Gate", overflow="fold")

    for i, a in enumerate(m.actions, 1):
        kind_str = (
            "[green]deterministic[/green]" if a.kind.value == "deterministic"
            else "[yellow]judgment[/yellow]"
        )
        gate_parts = []
        if a.when and a.when != "true":
            gate_parts.append(f"when: {a.when}")
        if a.kind.value == "judgment" and a.condition:
            gate_parts.append(f"[yellow]condition:[/yellow] {a.condition}")
        gate = "\n".join(gate_parts) if gate_parts else "[dim]always runs[/dim]"
        t.add_row(str(i), a.id, kind_str, a.impl, gate)
    console.print(t)

    # Recent runs
    runs = state.list_runs(m.name, limit=10)
    if runs:
        rt = Table(title="Recent runs", show_lines=False)
        rt.add_column("Started", style="dim")
        rt.add_column("Status")
        rt.add_column("Duration", justify="right")
        rt.add_column("Dry-run", justify="center")
        rt.add_column("Run ID", style="dim")
        for r in runs:
            status_str = _color_status(r.get("status", "?"))
            dur = _duration_ms(r)
            dr = "✓" if r.get("dry_run") else ""
            rt.add_row(
                _short_iso(r.get("started_at", "")),
                status_str,
                f"{dur}ms" if dur is not None else "",
                dr,
                r.get("id", ""),
            )
        console.print(rt)
    else:
        console.print("[dim]No runs yet. Try [bold]nia dry-run worker "
                      f"{m.name}[/bold] to see the first one.[/dim]")
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


def _duration_ms(run: dict) -> int | None:
    s = run.get("started_at")
    f = run.get("finished_at")
    if not s or not f:
        return None
    from datetime import datetime
    try:
        return int((datetime.fromisoformat(f) - datetime.fromisoformat(s)).total_seconds() * 1000)
    except Exception:
        return None
