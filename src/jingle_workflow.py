#!/usr/bin/python3
"""Explicit local boundary markers for `/go`-style Jingle workflows."""

from __future__ import annotations

import argparse
import json

from jingle_lifecycle import POLICY_WORKFLOW_TERMINAL, STATE_BLOCKED, STATE_DONE, finish_workflow, start_workflow


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
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
