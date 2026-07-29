"""CLI entry point for ``python3 -m router``."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .adapters import ClaudeAdapter, CodexAdapter, MachineGate
from .ledger import RunStore
from .workflow import Workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tr",
        description="Route one task through the fixed TokenRouter v0 SOP.",
    )
    parser.add_argument("task", help="The task to execute.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace in which Codex and the machine gate run (default: current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run Fable triage without editing the target workspace, gating, or review.",
    )
    args = parser.parse_args(argv)

    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        parser.error("--workspace must name an existing directory")

    package_root = Path(__file__).resolve().parent
    workflow = Workflow(
        triage=ClaudeAdapter(),
        developer=CodexAdapter(),
        gate=MachineGate(),
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
