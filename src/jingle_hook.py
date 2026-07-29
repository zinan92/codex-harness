#!/usr/bin/python3
"""Command-hook entry point for Jingle's local lifecycle state machine."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from codex_spoken_notify import classify_outcome
from jingle_lifecycle import begin_work_unit, finish_work_unit, ignore_subagent_event, is_subagent_event


START_EVENTS = {"UserPromptSubmit"}
END_EVENTS = {"Stop", "StopFailure"}


def read_payload() -> dict[str, Any] | None:
    try:
        payload = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def handle(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    if is_subagent_event(payload):
        return ignore_subagent_event(provider, payload)
    event_name = str(payload.get("hook_event_name") or "").strip()
    if event_name in START_EVENTS:
        return begin_work_unit(provider, payload)
    if event_name in END_EVENTS:
        return finish_work_unit(provider, payload, classify_outcome)
    return {"status": "ignored_event", "changed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("codex", "claude"), required=True)
    parser.add_argument("--print-result", action="store_true")
    arguments = parser.parse_args()
    payload = read_payload()
    if payload is None:
        return 0
    result = handle(arguments.provider, payload)
    if arguments.print_result:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
