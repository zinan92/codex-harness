"""CLI entry point for ``python3 -m router``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys

from .adapters import ClaudeAdapter, CodexAdapter, MachineGate
from .ledger import RunStore
from .summary import aggregate_runs
from .workflow import Workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tr",
        description="Route one task through the fixed TokenRouter v0 SOP.",
    )
    parser.add_argument("task", nargs="?", help="The task to execute.")
    parser.add_argument("--summary", action="store_true", help="Print JSON summary of run receipts.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace in which Codex and the machine gate run (default: current directory).",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Path to router/runs for summary output (defaults to router/runs).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run Fable triage without editing the target workspace, gating, or review.",
    )
    parser.add_argument(
        "--gate",
        help="Machine-gate command to run in the workspace (default: configured repository gate).",
    )
    args = parser.parse_args(argv)

    if args.summary:
        package_root = Path(__file__).resolve().parent
        runs_dir = args.runs_dir or (package_root / "runs")
        runs_dir = runs_dir.expanduser().resolve()
        print(json.dumps(aggregate_runs(runs_dir), ensure_ascii=False, sort_keys=True))
        return 0

    if not args.task:
        parser.error("task is required unless --summary is used")

    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        parser.error("--workspace must name an existing directory")
    gate_command = None
    if args.gate is not None:
        gate_command = tuple(shlex.split(args.gate))
        if not gate_command:
            parser.error("--gate must contain a command")

    package_root = Path(__file__).resolve().parent
    workflow = Workflow(
        triage=ClaudeAdapter(),
        developer=CodexAdapter(),
        gate=MachineGate(command=gate_command),
        reviewer=ClaudeAdapter(),
        store=RunStore(package_root),
    )
    result = workflow.run(task=args.task, workspace=workspace, dry_run=args.dry_run)
    print("run_id: {}".format(result.run_id))
    print("profile: {}".format(result.profile or "unclassified"))
    print("status: {}".format(result.status))
    if result.message:
        print("detail: {}".format(result.message))
    return 0 if result.status in {"succeeded", "planned"} else 1


if __name__ == "__main__":
    sys.exit(main())
