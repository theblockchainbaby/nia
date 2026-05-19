"""nia worker {list, install, enable}"""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from nia.runtime import registry


def worker_list() -> int:
    console = Console()
    workers = registry.list_installed()
    if not workers:
        console.print("[yellow]No workers installed.[/yellow] "
                      "Try [bold]nia worker install hello-world[/bold].")
        return 0
    t = Table(title="Installed workers", show_lines=False)
    t.add_column("Name", style="cyan", no_wrap=True)
    t.add_column("Version", style="dim")
    t.add_column("Trigger", style="green")
    t.add_column("Actions", justify="right")
    t.add_column("Judgments", justify="right")
    t.add_column("Description", overflow="fold")
    for w in workers:
        trig = (
            f"cron: {w.trigger.cron}" if w.trigger.cron else
            f"every {w.trigger.interval_seconds}s" if w.trigger.interval_seconds else
            "manual" if w.trigger.manual else
            f"event: {w.trigger.event}" if w.trigger.event else "?"
        )
        det = sum(1 for a in w.actions if a.kind.value == "deterministic")
        jud = sum(1 for a in w.actions if a.kind.value == "judgment")
        t.add_row(w.name, w.version, trig, str(det), str(jud), w.description.split("\n")[0])
    console.print(t)
    return 0


def worker_install(name: str) -> int:
    """v0.1: prints registry URL. v0.2: actually fetches and installs."""
    console = Console()
    console.print(
        f"[yellow]v0.1: in-place install not yet implemented.[/yellow]\n"
        f"Clone the worker into [cyan]~/.nia/workers/{name}/[/cyan] manually for now, "
        f"or use built-in workers shipped with Nia.\n"
        f"v0.2 will support: [bold]nia worker install {name}[/bold] from a registry."
    )
    return 0


def worker_enable(name: str) -> int:
    """v0.1: prints how to set up launchd/systemd manually. v0.2: registers it."""
    console = Console()
    console.print(
        f"[yellow]v0.1: scheduling not yet automated.[/yellow]\n"
        f"For now run [bold]nia worker run {name}[/bold] manually or schedule it "
        f"via launchd/cron pointing at [bold]nia worker run {name}[/bold].\n"
        f"v0.2 will wire scheduling automatically via the OS adapter."
    )
    return 0
