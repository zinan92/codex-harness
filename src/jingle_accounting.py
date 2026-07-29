#!/usr/bin/python3
"""End-only Work Unit token accounting for Codex and Claude JSONL histories."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


UNAVAILABLE = None


def parse_timestamp(value: object) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def integer(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def unavailable(provider: str, reason: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "status": "unavailable",
        "reason": reason,
        "input_tokens": UNAVAILABLE,
        "cached_input_tokens": UNAVAILABLE,
        "cache_write_input_tokens": UNAVAILABLE,
        "output_tokens": UNAVAILABLE,
        "total_tokens": UNAVAILABLE,
    }


def normalized_codex_snapshot(raw: dict[str, Any]) -> dict[str, int]:
    input_tokens = integer(raw.get("input_tokens"))
    cached_input = min(integer(raw.get("cached_input_tokens")), input_tokens)
    return {
        "fresh_input_tokens": input_tokens - cached_input,
        "cached_input_tokens": cached_input,
        "output_tokens": integer(raw.get("output_tokens")),
    }


def codex_accounting(lines: list[str], started_at: float, ended_at: float) -> dict[str, Any]:
    snapshots: list[tuple[float, dict[str, int]]] = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or record.get("type") != "event_msg":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        total = info.get("total_token_usage") if isinstance(info, dict) else None
        timestamp = parse_timestamp(record.get("timestamp"))
        if not isinstance(total, dict) or timestamp is None:
            continue
        snapshots.append((timestamp, normalized_codex_snapshot(total)))
    baseline = next((item for item in reversed(snapshots) if item[0] <= started_at), None)
    ending = next((item for item in reversed(snapshots) if item[0] <= ended_at), None)
    if baseline is None or ending is None or ending[0] < started_at:
        return unavailable("codex", "missing_cumulative_snapshot")
    start = baseline[1]
    end = ending[1]
    fresh_input = end["fresh_input_tokens"] - start["fresh_input_tokens"]
    cached_input = end["cached_input_tokens"] - start["cached_input_tokens"]
    output = end["output_tokens"] - start["output_tokens"]
    if min(fresh_input, cached_input, output) < 0:
        return unavailable("codex", "non_monotonic_cumulative_snapshot")
    return {
        "provider": "codex",
        "status": "available",
        "source": "cumulative_delta",
        "input_tokens": fresh_input,
        "cached_input_tokens": cached_input,
        "cache_write_input_tokens": UNAVAILABLE,
        "output_tokens": output,
        "total_tokens": fresh_input + cached_input + output,
        "snapshot_count": len(snapshots),
        "start_snapshot_at": baseline[0],
        "end_snapshot_at": ending[0],
    }


def claude_accounting(lines: list[str], started_at: float, ended_at: float) -> dict[str, Any]:
    totals = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 0,
    }
    seen_message_ids: set[str] = set()
    matched = 0
    duplicates = 0
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        timestamp = parse_timestamp(record.get("timestamp"))
        message = record.get("message") if isinstance(record, dict) else None
        if timestamp is None or not (started_at < timestamp <= ended_at):
            continue
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        usage = message.get("usage")
        message_id = message.get("id")
        if not isinstance(usage, dict) or not isinstance(message_id, str) or not message_id:
            continue
        if message_id in seen_message_ids:
            duplicates += 1
            continue
        seen_message_ids.add(message_id)
        matched += 1
        totals["input_tokens"] += integer(usage.get("input_tokens"))
        totals["cached_input_tokens"] += integer(usage.get("cache_read_input_tokens"))
        totals["cache_write_input_tokens"] += integer(usage.get("cache_creation_input_tokens"))
        totals["output_tokens"] += integer(usage.get("output_tokens"))
    if not matched:
        return unavailable("claude", "missing_window_usage")
    return {
        "provider": "claude",
        "status": "available",
        "source": "window_usage_sum",
        **totals,
        "total_tokens": sum(totals.values()),
        "usage_message_count": matched,
        "duplicate_usage_messages_suppressed": duplicates,
    }


def collect_accounting(unit: dict[str, Any]) -> dict[str, Any]:
    """Read the transcript once, only after a Work Unit has ended."""
    provider = str(unit.get("provider") or "")
    transcript_path = Path(str(unit.get("transcript_path") or ""))
    started_at = unit.get("started_at")
    ended_at = unit.get("ended_at")
    if provider not in {"codex", "claude"}:
        return unavailable(provider, "unsupported_provider")
    if unit.get("state") == "running":
        return unavailable(provider, "work_unit_still_running")
    if not isinstance(started_at, (int, float)) or not isinstance(ended_at, (int, float)):
        return unavailable(provider, "missing_work_unit_window")
    if not transcript_path.is_file():
        return unavailable(provider, "missing_transcript")
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return unavailable(provider, "unreadable_transcript")
    if provider == "codex":
        return codex_accounting(lines, float(started_at), float(ended_at))
    return claude_accounting(lines, float(started_at), float(ended_at))
