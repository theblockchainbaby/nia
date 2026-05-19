"""Nia CLI entry point.

Locked v0.1 surface — every command below is part of the public contract:

    nia worker list
    nia worker install <name>
    nia worker enable <name>
    nia worker run <name> [--dry-run]
    nia inspect worker <name>
    nia dry-run worker <name>
    nia status
    nia logs <worker> [-n N]
    nia install                       # one-shot bootstrap, prints next steps
"""
from __future__ import annotations

import argparse
import sys

from . import commands


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nia",
        description="Local operations runtime. Deterministic by default. AI only when needed.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # nia install
    sub.add_parser("install", help="Bootstrap ~/.nia/ and print next steps")

    # nia status
    sub.add_parser("status", help="Show runtime status and most recent runs")

    # nia logs <worker> [-n N]
    p_logs = sub.add_parser("logs", help="Tail recent runs for a worker")
    p_logs.add_argument("worker")
    p_logs.add_argument("-n", "--limit", type=int, default=10)

    # nia inspect worker <name>
    p_inspect = sub.add_parser("inspect", help="Show a worker's triggers, actions, conditions, recent runs")
    p_inspect_sub = p_inspect.add_subparsers(dest="target", required=True)
    p_inspect_worker = p_inspect_sub.add_parser("worker")
    p_inspect_worker.add_argument("name")

    # nia dry-run worker <name>
    p_dryrun = sub.add_parser("dry-run", help="Execute a worker with all side effects mocked")
    p_dryrun_sub = p_dryrun.add_subparsers(dest="target", required=True)
    p_dryrun_worker = p_dryrun_sub.add_parser("worker")
    p_dryrun_worker.add_argument("name")

    # nia worker {list, install, enable, run}
    p_worker = sub.add_parser("worker", help="Manage workers")
    p_worker_sub = p_worker.add_subparsers(dest="worker_command", required=True)
    p_worker_sub.add_parser("list", help="List installed workers")
    p_wi = p_worker_sub.add_parser("install", help="Install a worker by name (v0.1: prints registry URL)")
    p_wi.add_argument("name")
    p_we = p_worker_sub.add_parser("enable", help="Enable scheduling for a worker")
    p_we.add_argument("name")
    p_wr = p_worker_sub.add_parser("run", help="Run a worker once, now")
    p_wr.add_argument("name")
    p_wr.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "install":
        return commands.install()
    if args.command == "status":
        return commands.status()
    if args.command == "logs":
        return commands.logs(args.worker, limit=args.limit)
    if args.command == "inspect":
        return commands.inspect_worker(args.name)
    if args.command == "dry-run":
        return commands.run_worker(args.name, dry_run=True)
    if args.command == "worker":
        if args.worker_command == "list":
            return commands.worker_list()
        if args.worker_command == "install":
            return commands.worker_install(args.name)
        if args.worker_command == "enable":
            return commands.worker_enable(args.name)
        if args.worker_command == "run":
            return commands.run_worker(args.name, dry_run=args.dry_run)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
