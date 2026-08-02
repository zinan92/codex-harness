#!/usr/bin/env python3
"""Read-only Codex thread token ledger.

The scanner consumes Codex JSONL session history and stores only deterministic
accounting metadata.  It deliberately never reads or stores prompt or response
content, and it makes no network calls.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


RUNTIME_DIR = Path.home() / ".codex" / "token-counter"
STATE_PATH = RUNTIME_DIR / "threads.json"
PROJECTS_PATH = RUNTIME_DIR / "projects.json"
PACKAGE_PROJECTS_PATH = Path(__file__).parents[1] / "assets" / "token-counter-projects.json"
SESSION_ROOTS = (Path.home() / ".codex" / "sessions", Path.home() / ".codex" / "archived_sessions")
UNCLASSIFIED = {"project_id": "uncategorized", "name": "Uncategorized", "source": "unmapped_cwd"}


def reporting_timezone() -> timezone | ZoneInfo:
    name = os.environ.get("TOKEN_COUNTER_TIMEZONE", "Asia/Shanghai")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def parse_timestamp(value: object) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def nonnegative(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def normalized_snapshot(value: object) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    input_tokens = nonnegative(value.get("input_tokens"))
    cached = min(nonnegative(value.get("cached_input_tokens")), input_tokens)
    output = nonnegative(value.get("output_tokens"))
    reasoning = nonnegative(value.get("reasoning_output_tokens"))
    declared_total = nonnegative(value.get("total_tokens"))
    # Codex may report reasoning separately.  Prefer its declared cumulative
    # total when present, retaining the component so the inclusion is auditable.
    computed_total = input_tokens + output + reasoning
    return {
        "fresh_input_tokens": input_tokens - cached,
        "cached_input_tokens": cached,
        "output_tokens": output,
        "reasoning_output_tokens": reasoning,
        "total_tokens": declared_total if declared_total else computed_total,
    }


def day_at(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=reporting_timezone()).date().isoformat()


def project_for(cwd: object, projects: list[dict[str, Any]]) -> dict[str, str]:
    path = os.path.normpath(os.path.expanduser(str(cwd or "").strip()))
    matches: list[tuple[int, dict[str, str]]] = []
    if not path.startswith("/"):
        return dict(UNCLASSIFIED)
    for project in projects:
        if not isinstance(project, dict):
            continue
        for alias in project.get("aliases", []):
            if not isinstance(alias, dict):
                continue
            prefix = os.path.normpath(os.path.expanduser(str(alias.get("prefix") or "").strip()))
            if prefix.startswith("/") and (path == prefix or path.startswith(prefix + os.sep)):
                matches.append((len(prefix), {
                    "project_id": str(project.get("project_id") or "uncategorized"),
                    "name": str(project.get("name") or project.get("project_id") or "Uncategorized"),
                    "source": "cwd_prefix",
                }))
    return max(matches, key=lambda item: item[0])[1] if matches else dict(UNCLASSIFIED)


def load_projects(path: Path | None = None) -> list[dict[str, Any]]:
    chosen = path or (PROJECTS_PATH if PROJECTS_PATH.is_file() else PACKAGE_PROJECTS_PATH)
    try:
        result = json.loads(chosen.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    projects = result.get("projects") if isinstance(result, dict) else None
    return projects if isinstance(projects, list) else []


def session_files(roots: Iterable[Path] = SESSION_ROOTS) -> list[Path]:
    return sorted(path for root in roots if root.is_dir() for path in root.rglob("*.jsonl"))


def extract_threads(paths: Iterable[Path], projects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build one row per session meta ID, allocating each cumulative delta once."""
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, float, tuple[int, int, int]]] = set()
    for path in paths:
        active_id: str | None = None
        active_cwd = ""
        try:
            handle = path.open("r", encoding="utf-8")
        except OSError:
            continue
        with handle:
            for line in handle:
                # Skip raw prompt/response records before JSON parsing. This is
                # both the privacy boundary and the only practical way to scan
                # large local session histories without loading their bodies.
                if '"session_meta"' not in line and '"token_count"' not in line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                timestamp = parse_timestamp(record.get("timestamp"))
                if record.get("type") == "session_meta":
                    payload = record.get("payload")
                    if isinstance(payload, dict) and isinstance(payload.get("id"), str) and payload["id"]:
                        active_id = payload["id"]
                        active_cwd = str(payload.get("cwd") or "")
                        events[active_id].append({"kind": "meta", "timestamp": timestamp, "cwd": active_cwd})
                    continue
                if not active_id or record.get("type") != "event_msg" or timestamp is None:
                    continue
                payload = record.get("payload")
                if not isinstance(payload, dict) or payload.get("type") != "token_count":
                    continue
                info = payload.get("info")
                if not isinstance(info, dict):
                    continue
                incremental = normalized_snapshot(info.get("last_token_usage"))
                snapshot = normalized_snapshot(info.get("total_token_usage"))
                usage = incremental or snapshot
                if usage is None:
                    continue
                signature = (active_id, timestamp, tuple(usage.values()))
                if signature not in seen:
                    seen.add(signature)
                    events[active_id].append({
                    "kind": "increment" if incremental is not None else "snapshot",
                    "timestamp": timestamp,
                    "snapshot": usage,
                    "cumulative": snapshot,
                        "cwd": active_cwd,
                    })

    rows: dict[str, dict[str, Any]] = {}
    for thread_id, thread_events in events.items():
        ordered = sorted(thread_events, key=lambda event: (event.get("timestamp") is None, event.get("timestamp") or 0))
        metadata = next((event for event in ordered if event["kind"] == "meta"), None)
        cwd = str(metadata.get("cwd") or "") if metadata else ""
        row: dict[str, Any] = {
            "thread_id": thread_id,
            "provider": "codex",
            "cwd": cwd,
            "project": project_for(cwd, projects),
            "activity_label": "Codex thread",
            "status": "unavailable",
            "reason": "missing_cumulative_snapshot",
            "started_at": metadata.get("timestamp") if metadata else None,
            "ended_at": None,
            "fresh_input_tokens": None,
            "cached_input_tokens": None,
            "output_tokens": None,
            "reasoning_output_tokens": None,
            "total_tokens": None,
            "daily": {},
            "cumulative_reset_count": 0,
            "sources": [],
        }
        prior: dict[str, int] | None = None
        prior_cumulative: dict[str, int] | None = None
        recorded = False
        totals = {"fresh_input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 0}
        daily: dict[str, dict[str, int]] = {}
        for event in ordered:
            if event["kind"] not in {"snapshot", "increment"}:
                continue
            current = event["snapshot"]
            if event["kind"] == "increment":
                cumulative = event.get("cumulative")
                if isinstance(cumulative, dict) and prior_cumulative is not None:
                    if cumulative["total_tokens"] == prior_cumulative["total_tokens"]:
                        # Codex can repeat a token_count while only status/rate
                        # metadata changes. It is not another model turn.
                        prior_cumulative = cumulative
                        continue
                    if cumulative["total_tokens"] < prior_cumulative["total_tokens"]:
                        row["cumulative_reset_count"] += 1
                if isinstance(cumulative, dict):
                    prior_cumulative = cumulative
                delta = current
                if "last_token_usage" not in row["sources"]:
                    row["sources"].append("last_token_usage")
            else:
                delta = current if prior is None else {key: current[key] - prior[key] for key in current}
                if "cumulative_delta" not in row["sources"]:
                    row["sources"].append("cumulative_delta")
            if event["kind"] == "snapshot" and delta["total_tokens"] < 0:
                # A resumed Codex transcript can start a new cumulative epoch.
                # Count that epoch from zero instead of carrying a stale prior.
                # The reset count makes this transparent for later audit.
                row["cumulative_reset_count"] += 1
                delta = current
            if event["kind"] == "snapshot":
                prior = current
            stamp = float(event["timestamp"])
            bucket = daily.setdefault(day_at(stamp), {"fresh_input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 0})
            for key, value in delta.items():
                totals[key] += value
                bucket[key] += value
            row["ended_at"] = stamp
            recorded = True
        if recorded:
            row.update(totals)
            row["total_tokens"] = totals["total_tokens"]
            row["daily"] = daily
            row["status"] = "available"
            row.pop("reason", None)
        rows[thread_id] = row
    return rows


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "threads": {}}
    return candidate if isinstance(candidate, dict) and isinstance(candidate.get("threads"), dict) else {"schema_version": 1, "threads": {}}


def freeze_attribution(rows: dict[str, dict[str, Any]], existing: dict[str, Any], *, remap_uncategorized: bool = False) -> None:
    old_threads = existing.get("threads", {}) if isinstance(existing, dict) else {}
    for thread_id, row in rows.items():
        old = old_threads.get(thread_id)
        if isinstance(old, dict) and isinstance(old.get("project"), dict) and not (
            remap_uncategorized and old["project"].get("project_id") == "uncategorized"
        ):
            row["project"] = old["project"]


def save_state(rows: dict[str, dict[str, Any]], path: Path = STATE_PATH) -> dict[str, Any]:
    state = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "reporting_timezone": os.environ.get("TOKEN_COUNTER_TIMEZONE", "Asia/Shanghai"), "threads": rows}
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="threads-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return state


def summary(state: dict[str, Any]) -> dict[str, Any]:
    threads = state.get("threads", {}).values()
    totals = {"fresh_input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0, "total_tokens": 0}
    available = 0
    daily: dict[str, int] = defaultdict(int)
    for row in threads:
        if not isinstance(row, dict) or row.get("status") != "available":
            continue
        available += 1
        for key in totals:
            totals[key] += nonnegative(row.get(key))
        for day, values in row.get("daily", {}).items():
            if isinstance(values, dict):
                daily[str(day)] += nonnegative(values.get("total_tokens"))
    return {"threads": len(state.get("threads", {})), "available_threads": available, "reporting_timezone": state.get("reporting_timezone", os.environ.get("TOKEN_COUNTER_TIMEZONE", "Asia/Shanghai")), "tokens": totals, "daily_total_tokens": dict(sorted(daily.items()))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Local, read-only Codex thread token ledger")
    parser.add_argument("command", choices=("scan", "summary"), nargs="?", default="summary")
    parser.add_argument("--state", type=Path, default=STATE_PATH, help="ledger path (default: ~/.codex/token-counter/threads.json)")
    parser.add_argument("--projects", type=Path, default=None, help="project mapping JSON")
    parser.add_argument("--sessions-root", type=Path, action="append", help="override session root; repeatable")
    parser.add_argument("--remap-uncategorized", action="store_true", help="explicitly reattribute only historic Uncategorized rows")
    args = parser.parse_args()
    if args.command == "scan":
        roots = tuple(args.sessions_root) if args.sessions_root else SESSION_ROOTS
        rows = extract_threads(session_files(roots), load_projects(args.projects))
        existing = load_state(args.state)
        freeze_attribution(rows, existing, remap_uncategorized=args.remap_uncategorized)
        state = save_state(rows, args.state)
    else:
        state = load_state(args.state)
    print(json.dumps(summary(state), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
