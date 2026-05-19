"""nia install — one-shot bootstrap of ~/.nia/ + next-step hints."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

NIA_HOME = Path.home() / ".nia"


def install() -> int:
    console = Console()
    NIA_HOME.mkdir(exist_ok=True)
    (NIA_HOME / "workers").mkdir(exist_ok=True)
    (NIA_HOME / "runs").mkdir(exist_ok=True)
    (NIA_HOME / "logs").mkdir(exist_ok=True)

    console.print(Panel.fit(
        f"[bold green]Nia installed.[/bold green]\n\n"
        f"State directory: [cyan]{NIA_HOME}[/cyan]\n\n"
        "[dim]Next steps:[/dim]\n"
        "  [bold]nia worker list[/bold]            see built-in workers\n"
        "  [bold]nia inspect worker hello-world[/bold]   read a worker's mind\n"
        "  [bold]nia dry-run worker hello-world[/bold]   try a run without side effects\n"
        "  [bold]nia worker run hello-world[/bold]       run for real",
        title="nia",
        border_style="cyan",
    ))
    return 0
