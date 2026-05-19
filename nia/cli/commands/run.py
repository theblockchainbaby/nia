"""nia worker run <name> [--dry-run]   |   nia dry-run worker <name>"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nia.runtime import executor, registry


def run_worker(name: str, *, dry_run: bool = False) -> int:
    console = Console()
    try:
        m = registry.load(name)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    label = "[yellow]DRY-RUN[/yellow]" if dry_run else "[bold green]RUN[/bold green]"
    console.print(f"\n{label}  [cyan]{m.name}[/cyan]  v{m.version}\n")

    run = executor.execute(m, dry_run=dry_run, trigger_source="cli")

    # Render action results
    t = Table(show_lines=False)
    t.add_column("Action", style="cyan")
    t.add_column("Kind")
    t.add_column("Status")
    t.add_column("Detail", overflow="fold")
    for ar in run.actions:
        kind_str = (
            "[green]det[/green]" if ar.kind.value == "deterministic"
            else "[yellow]jud[/yellow]"
        )
        status_str = _color_status(ar.status.value)
        detail = ar.error or ar.skipped_reason or _summarize_results(ar.results)
        t.add_row(ar.action_id, kind_str, status_str, detail)
    console.print(t)

    final = (
        "[bold green]✓ success[/bold green]" if run.status.value == "success"
        else f"[bold red]✗ {run.status.value}[/bold red]"
    )
    dur = run.duration_ms or 0
    console.print(Panel.fit(
        f"{final}  in {dur}ms  ·  run id [dim]{run.id}[/dim]",
        border_style="green" if run.status.value == "success" else "red",
    ))
    return 0 if run.status.value == "success" else 2


def _color_status(s: str) -> str:
    return {
        "success":  "[green]success[/green]",
        "failed":   "[red]failed[/red]",
        "running":  "[yellow]running[/yellow]",
        "skipped":  "[dim]skipped[/dim]",
        "pending":  "[dim]pending[/dim]",
    }.get(s, s)


def _summarize_results(r: dict) -> str:
    if not r:
        return ""
    parts = []
    for k, v in list(r.items())[:3]:
        s = str(v)
        if len(s) > 60:
            s = s[:57] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
