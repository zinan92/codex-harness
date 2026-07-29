#!/usr/bin/python3
"""Capture a hook payload's schema without retaining user or assistant text."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

SENSITIVE = {"prompt", "last_assistant_message", "message", "content", "error_details"}

def main() -> int:
    try: payload = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError, TypeError): return 0
    if not isinstance(payload, dict): return 0
    fields = {key: type(value).__name__ for key, value in payload.items() if key not in SENSITIVE}
    evidence = {"ts": time.time(), "event": payload.get("hook_event_name"), "fields": fields, "has": {key: key in payload for key in ("session_id", "turn_id", "cwd", "transcript_path", "agent_id", "agent_type", "stop_hook_active", "last_assistant_message")}}
    path = Path(os.environ["JINGLE_HOOK_SHAPE_LOG"])
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output: output.write(json.dumps(evidence) + "\n")
    return 0
if __name__ == "__main__": raise SystemExit(main())
