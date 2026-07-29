#!/usr/bin/python3
"""Explicit local boundary markers for `/go`-style Jingle workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_spoken_notify import STATUS_ATTENTION, launch_worker
from jingle_lifecycle import (
    POLICY_WORKFLOW_TERMINAL,
    STATE_BLOCKED,
    STATE_DONE,
    finish_workflow,
    start_workflow,
)


def deliver_blocked_workflow(result: dict[str, object]) -> None:
    """Interrupt once for an explicit workflow-level decision, never for done."""
    unit = result.get("unit")
    if not isinstance(unit, dict) or result.get("status") != STATE_BLOCKED:
        return
    notification_id = str(unit.get("turn_id") or unit.get("id") or "")
    session_id = str(unit.get("session_id") or "")
    if not notification_id or not session_id:
        return
    project = Path(str(unit.get("cwd") or "")).name or str(unit.get("provider") or "workflow")
    launch_worker(
        notification_id,
        session_id,
        f"{project}：workflow 需要决定",
        "jingle_workflow",
        STATUS_ATTENTION,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("codex", "claude"), required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--cwd", default="")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true")
    group.add_argument("--finish", action="store_true")
    group.add_argument("--blocked", action="store_true")
    args = parser.parse_args()
    if args.start:
        result = start_workflow(args.provider, args.session_id, args.cwd, POLICY_WORKFLOW_TERMINAL)
    else:
        result = finish_workflow(args.provider, args.session_id, STATE_BLOCKED if args.blocked else STATE_DONE)
        deliver_blocked_workflow(result)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
