"""nia worker {list, install, enable, run}.

v0.2: install and enable do real work.
  install: copies the bundled worker.yaml into ~/.nia/workers/<name>/ and
           scaffolds accounts.yaml.template / config.yaml.template so the
           user has a starting point to fill in.
  enable:  generates a launchd plist from the worker's cron trigger,
           writes it to ~/Library/LaunchAgents/com.nia.<name>.plist, and
           loads it via launchctl. macOS only.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from nia.runtime import registry


USER_WORKERS = Path.home() / ".nia" / "workers"
LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
DEFAULT_ENV_FILE = Path.home() / ".nia" / "env"


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


# ─── install ────────────────────────────────────────────────────────────


def worker_install(name: str) -> int:
    """Copy a built-in worker manifest into ~/.nia/workers/<name>/.

    Generates accounts.yaml.template and config.yaml.template scaffolds
    if the manifest references them. Idempotent: re-running prints a
    notice but does not clobber existing user customizations.
    """
    console = Console()

    src = registry.BUILTIN_WORKERS / name / "worker.yaml"
    if not src.is_file():
        bundled = sorted(p.name for p in registry.BUILTIN_WORKERS.iterdir()
                         if p.is_dir() and (p / "worker.yaml").is_file())
        console.print(
            f"[red]Worker {name!r} not found among bundled workers.[/red]\n"
            f"Bundled: {', '.join(bundled)}"
        )
        return 1

    dest_dir = USER_WORKERS / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_manifest = dest_dir / "worker.yaml"

    manifest_text = src.read_text()
    already_installed = dest_manifest.is_file()

    if already_installed:
        console.print(f"[yellow]Already installed at {dest_manifest}.[/yellow] "
                      f"Not overwriting your customizations.")
    else:
        shutil.copy2(src, dest_manifest)

    # Scaffold accounts.yaml.template if the manifest references it.
    accounts_template = dest_dir / "accounts.yaml.template"
    if "accounts_file" in manifest_text and not accounts_template.is_file():
        accounts_template.write_text(_ACCOUNTS_TEMPLATE)

    # Scaffold config.yaml.template (empty stub with header).
    config_template = dest_dir / "config.yaml.template"
    if not config_template.is_file():
        config_template.write_text(_CONFIG_TEMPLATE.format(name=name))

    # Print next steps.
    lines = []
    lines.append(f"[bold green]Installed:[/bold green] {name}")
    lines.append(f"  Path: [cyan]{dest_dir}[/cyan]")
    lines.append("")
    lines.append("Next steps:")
    if accounts_template.is_file():
        lines.append("  1. Copy [cyan]accounts.yaml.template[/cyan] to "
                     "[cyan]accounts.yaml[/cyan] and fill in credentials")
    lines.append(f"  2. [bold]nia inspect worker {name}[/bold]   verify the load")
    lines.append(f"  3. [bold]nia dry-run worker {name}[/bold]  mock the side effects")
    lines.append(f"  4. [bold]nia worker run {name}[/bold]      run once for real")
    lines.append(f"  5. [bold]nia worker enable {name}[/bold]   schedule under launchd")
    console.print(Panel.fit("\n".join(lines), title="install", border_style="green"))
    return 0


# ─── enable ─────────────────────────────────────────────────────────────


def worker_enable(name: str) -> int:
    """Generate and load a launchd plist for the worker's cron trigger.

    macOS only. For non-cron triggers, manual workers, or non-macOS hosts,
    prints a clear error rather than silently failing.
    """
    console = Console()

    if platform.system() != "Darwin":
        console.print(
            f"[red]nia worker enable currently supports macOS (launchd) only.[/red]\n"
            f"Detected: {platform.system()}. Linux/systemd support is on the v0.3 roadmap."
        )
        return 1

    try:
        manifest = registry.load(name)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    cron = manifest.trigger.cron
    interval = manifest.trigger.interval_seconds

    if manifest.trigger.manual:
        console.print(
            f"[red]Worker {name!r} is manually triggered.[/red] "
            f"Run it with [bold]nia worker run {name}[/bold]."
        )
        return 1
    if manifest.trigger.event:
        console.print(
            "[red]Event-triggered workers are not yet schedulable via "
            "`nia worker enable`.[/red] v0.3 will add a webhook listener."
        )
        return 1
    if not cron and not interval:
        console.print(f"[red]Worker {name!r} has no schedulable trigger.[/red]")
        return 1

    plist_path = LAUNCH_AGENTS / f"com.nia.{_label_safe(name)}.plist"
    nia_bin = _resolve_nia_bin()
    log_dir = Path.home() / ".nia" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    schedule_xml = _schedule_xml(cron, interval)

    env_source = ""
    if DEFAULT_ENV_FILE.is_file():
        env_source = f"set -a; source {DEFAULT_ENV_FILE}; set +a; "

    plist_xml = _PLIST_TEMPLATE.format(
        label=f"com.nia.{_label_safe(name)}",
        env_source=env_source,
        nia_bin=nia_bin,
        worker_name=name,
        working_dir=str(Path.cwd()),
        schedule_xml=schedule_xml,
        stdout_log=log_dir / f"{_label_safe(name)}_stdout.log",
        stderr_log=log_dir / f"{_label_safe(name)}_stderr.log",
    )

    console.print(Panel(
        Syntax(plist_xml, "xml", line_numbers=False),
        title=f"Generated plist for {name}",
        border_style="cyan",
    ))

    LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(plist_xml)

    # Unload first in case it was already loaded (idempotency).
    subprocess.run(
        ["launchctl", "unload", str(plist_path)],
        check=False, capture_output=True,
    )
    load_result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        check=False, capture_output=True, text=True,
    )

    if load_result.returncode != 0:
        console.print(
            f"[yellow]Plist written but launchctl load returned non-zero "
            f"(stderr: {load_result.stderr.strip() or 'empty'}).[/yellow]\n"
            f"Plist at: [cyan]{plist_path}[/cyan]\n"
            f"Try: [bold]launchctl load {plist_path}[/bold]"
        )
        return 1

    console.print(Panel.fit(
        f"[bold green]Enabled:[/bold green] {name}\n"
        f"  Plist: [cyan]{plist_path}[/cyan]\n"
        f"  Stdout: [cyan]{log_dir / (_label_safe(name) + '_stdout.log')}[/cyan]\n"
        f"  Stderr: [cyan]{log_dir / (_label_safe(name) + '_stderr.log')}[/cyan]\n"
        f"\nVerify: [bold]launchctl list | grep nia[/bold]\n"
        f"Disable: [bold]launchctl unload {plist_path}[/bold]",
        title="enable",
        border_style="green",
    ))
    return 0


# ─── helpers ────────────────────────────────────────────────────────────


_LABEL_RE = re.compile(r"[^a-z0-9]+")


def _label_safe(name: str) -> str:
    """Make a worker name safe for a launchd Label (alphanumeric only)."""
    return _LABEL_RE.sub("", name.lower())


def _resolve_nia_bin() -> str:
    """Best-effort path to the nia executable.

    Prefer the venv-installed entry point; fall back to bare `nia`.
    """
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        candidate = Path(venv) / "bin" / "nia"
        if candidate.is_file():
            return str(candidate)
    # Common project venv location.
    project_venv = Path.cwd() / ".venv" / "bin" / "nia"
    if project_venv.is_file():
        return str(project_venv)
    found = shutil.which("nia")
    return found or "nia"


def _schedule_xml(cron: str | None, interval_seconds: int | None) -> str:
    """Convert a cron expression OR an interval into launchd XML.

    Supports:
      cron with single values or comma-separated values per field
      cron with `*` (wildcard) per field
      interval in seconds → StartInterval

    Does NOT support: step (*/N), ranges (1-5), shorthand (@daily).
    """
    if interval_seconds:
        return (
            f"    <key>StartInterval</key>\n"
            f"    <integer>{int(interval_seconds)}</integer>"
        )

    if not cron:
        raise ValueError("schedule requires cron or interval")

    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(
            f"cron expression must have 5 fields (m h dom mon dow), got {len(parts)}: {cron!r}"
        )
    minute, hour, dom, mon, dow = parts

    # Reject unsupported shorthand explicitly.
    for field in parts:
        if "/" in field or "-" in field:
            raise ValueError(
                f"v0.2 cron support is single values or comma-separated lists only. "
                f"Got: {cron!r}. Ranges (1-5) and steps (*/N) are not yet supported."
            )

    # Build the list of value combinations.
    minute_vals = ["*" if minute == "*" else m for m in minute.split(",")]
    hour_vals = ["*" if hour == "*" else h for h in hour.split(",")]
    dom_vals = ["*" if dom == "*" else d for d in dom.split(",")]
    mon_vals = ["*" if mon == "*" else m for m in mon.split(",")]
    dow_vals = ["*" if dow == "*" else d for d in dow.split(",")]

    entries: list[dict[str, int]] = []
    for mi in minute_vals:
        for ho in hour_vals:
            for da in dom_vals:
                for mo in mon_vals:
                    for we in dow_vals:
                        entry: dict[str, int] = {}
                        if mi != "*":
                            entry["Minute"] = int(mi)
                        if ho != "*":
                            entry["Hour"] = int(ho)
                        if da != "*":
                            entry["Day"] = int(da)
                        if mo != "*":
                            entry["Month"] = int(mo)
                        if we != "*":
                            entry["Weekday"] = int(we)
                        entries.append(entry)

    if not entries:
        # All wildcards means every minute. Unusual but valid.
        entries = [{}]

    if len(entries) == 1:
        # Single dict.
        return _calendar_dict_xml(entries[0])

    # Array of dicts.
    inner = "\n".join("        " + line
                      for e in entries
                      for line in _calendar_dict_xml(e, indent="").splitlines())
    return (
        f"    <key>StartCalendarInterval</key>\n"
        f"    <array>\n{inner}\n    </array>"
    )


def _calendar_dict_xml(d: dict[str, int], indent: str = "    ") -> str:
    """One StartCalendarInterval dict (or a plain dict inside an array)."""
    lines = [f"{indent}<key>StartCalendarInterval</key>", f"{indent}<dict>"] if indent else ["<dict>"]
    if not indent:
        lines = ["<dict>"]
    for k in ("Minute", "Hour", "Day", "Month", "Weekday"):
        if k in d:
            lines.append(f"    <key>{k}</key>")
            lines.append(f"    <integer>{d[k]}</integer>")
    lines.append("</dict>")
    if indent:
        # Wrap with the StartCalendarInterval key.
        return (f"{indent}<key>StartCalendarInterval</key>\n"
                f"{indent}<dict>\n"
                + "\n".join(f"{indent}    <key>{k}</key>\n{indent}    <integer>{d[k]}</integer>"
                            for k in ("Minute", "Hour", "Day", "Month", "Weekday")
                            if k in d)
                + f"\n{indent}</dict>")
    return "\n".join(lines)


_PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>{env_source}{nia_bin} worker run {worker_name}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{working_dir}</string>
{schedule_xml}
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{stdout_log}</string>
    <key>StandardErrorPath</key>
    <string>{stderr_log}</string>
</dict>
</plist>
"""


_ACCOUNTS_TEMPLATE = """# Copy this file to accounts.yaml and fill in real credentials.
# accounts.yaml is gitignored by convention; do not commit it.
accounts:
  - label: my-account
    user: you@example.com
    pass: app-password-or-imap-password
    server: imap.gmail.com
    sent_folder: "[Gmail]/Sent Mail"
"""


_CONFIG_TEMPLATE = """# Optional: override the worker's config block here.
# Any keys you set override the defaults baked into worker.yaml.
# Example:
#
# brief_recipient: "+15551234567"
# output_dir: "~/.nia/briefs"
#
# Worker: {name}
"""
