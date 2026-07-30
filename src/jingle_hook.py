#!/usr/bin/python3
"""Command-hook entry point for Jingle's local lifecycle state machine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from codex_spoken_notify import classify_outcome
from jingle_accounting import collect_accounting
from jingle_lifecycle import attach_accounting, begin_work_unit, finish_work_unit, ignore_subagent_event, is_subagent_event


START_EVENTS = {"UserPromptSubmit"}
# Claude Code can end a process before it emits Stop/StopFailure (for example,
# a budget failure). SessionEnd is a terminal-only safety net: lifecycle.py
# ignores it after a normal Stop has already completed the active Work Unit.
END_EVENTS = {"Stop", "StopFailure", "SessionEnd"}


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
        result = finish_work_unit(provider, payload, classify_outcome)
        if result.get("changed") and result.get("status") in {"blocked", "done"}:
            from jingle_summary import first_line, last_assistant_text, launch
            source = last_assistant_text(provider, str(result['unit'].get('transcript_path') or ''))
            from jingle_lifecycle import attach_initial_summary
            card_title = first_line(source)
            result['summary'] = attach_initial_summary(result['unit']['id'], card_title)
            # A terminal independent task is now a quiet queue item: it gets the
            # success sound but never a call card. Blocked work keeps attention
            # speech and is the only state that may call the panel.
            if result.get("delivery_eligible"):
                from codex_spoken_notify import STATUS_ATTENTION, STATUS_SUCCESS, launch_worker
                notification_id = str(result['unit'].get('turn_id') or result['unit']['id'])
                project = Path(str(result['unit'].get('cwd') or '')).name or provider
                classification = STATUS_ATTENTION if result["status"] == "blocked" else STATUS_SUCCESS
                launch_worker(notification_id, str(result['unit'].get('session_id') or ''), f"{project}：{card_title}", "jingle_lifecycle", classification)
            accounting = collect_accounting(result["unit"])
            result["accounting"] = attach_accounting(result["unit"]["id"], accounting)
            launch(result['unit']['id'], provider, str(result['unit'].get('transcript_path') or ''))
        return result
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
