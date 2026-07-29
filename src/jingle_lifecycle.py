#!/usr/bin/python3
"""Persist Jingle's provider-neutral three-state Work Unit lifecycle.

This module intentionally has no UI, audio, network, or token-accounting code.
Hook commands call it with lifecycle metadata only; prompts and assistant messages
are used transiently for classification and are never written to disk.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Callable


JINGLE_RUNTIME_DIR = Path.home() / ".codex" / "jingle"
DEFAULT_STATE_PATH = JINGLE_RUNTIME_DIR / "work-units.json"
DEFAULT_LOCK_PATH = JINGLE_RUNTIME_DIR / "work-units.lock"
DEFAULT_EVENT_LOG_PATH = JINGLE_RUNTIME_DIR / "lifecycle-events.jsonl"

STATE_RUNNING = "running"
STATE_BLOCKED = "blocked"
STATE_DONE = "done"
VALID_STATES = {STATE_RUNNING, STATE_BLOCKED, STATE_DONE}
VALID_PROVIDERS = {"codex", "claude"}
LOCATOR_FIELDS = ("terminal_app", "terminal_tty", "terminal_session_id", "parent_pid")


def runtime_path(variable: str, default: Path) -> Path:
    """Allow tests and local diagnostics to use an isolated state directory."""
    configured = os.environ.get(variable, "").strip()
    return Path(configured).expanduser() if configured else default


def state_path() -> Path:
    return runtime_path("JINGLE_STATE_PATH", DEFAULT_STATE_PATH)


def lock_path() -> Path:
    return runtime_path("JINGLE_LOCK_PATH", DEFAULT_LOCK_PATH)


def event_log_path() -> Path:
    return runtime_path("JINGLE_EVENT_LOG_PATH", DEFAULT_EVENT_LOG_PATH)


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "units": {},
        "active_by_session": {},
        "next_sequence_by_session": {},
        "updated_at": 0,
    }


def _private_parent(path: Path) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass


def load_state(path: Path | None = None) -> dict[str, Any]:
    path = path or state_path()
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return empty_state()
    if not isinstance(candidate, dict) or candidate.get("schema_version") != 1:
        return empty_state()
    state = empty_state()
    for key in ("units", "active_by_session", "next_sequence_by_session"):
        if isinstance(candidate.get(key), dict):
            state[key] = candidate[key]
    return state


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
    path = path or state_path()
    _private_parent(path)
    state["schema_version"] = 1
    state["updated_at"] = int(time.time())
    descriptor, temporary = tempfile.mkstemp(
        prefix="work-units-", suffix=".json", dir=path.parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def append_event(event: dict[str, Any]) -> None:
    """Write metadata only; callers must never put messages or prompts here."""
    path = event_log_path()
    _private_parent(path)
    safe = {"ts": int(time.time()), **event}
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe, ensure_ascii=False) + "\n")
    except OSError:
        pass


def session_key(provider: str, session_id: str) -> str:
    return f"{provider}:{session_id}"


def _process_locator() -> dict[str, Any]:
    """Find the inherited terminal TTY without retaining command-line text."""
    pid = os.getppid()
    for _ in range(12):
        try:
            result = subprocess.run(
                ["ps", "-o", "pid=,ppid=,tty=", "-p", str(pid)],
                text=True,
                capture_output=True,
                timeout=1,
                check=False,
            )
            fields = result.stdout.split()
            if result.returncode != 0 or len(fields) < 3:
                break
            current_pid, parent_pid, tty = fields[0], fields[1], fields[2]
        except (OSError, subprocess.TimeoutExpired):
            break
        if tty not in {"?", "??"}:
            normalized_tty = tty if tty.startswith("/dev/") else f"/dev/{tty}"
            return {"terminal_tty": normalized_tty, "parent_pid": int(current_pid)}
        if parent_pid == current_pid:
            break
        pid = int(parent_pid)
    return {}


def capture_session_locator(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist only stable terminal identity metadata needed for an exact return."""
    locator: dict[str, Any] = {}
    for field in LOCATOR_FIELDS:
        value = payload.get(field)
        if field == "parent_pid" and isinstance(value, int) and value > 0:
            locator[field] = value
        elif field != "parent_pid" and isinstance(value, str) and value.strip():
            locator[field] = value
    terminal_program = os.environ.get("TERM_PROGRAM", "")
    if not locator.get("terminal_app"):
        locator["terminal_app"] = {
            "Apple_Terminal": "Terminal",
            "iTerm.app": "iTerm2",
            "WarpTerminal": "Warp",
        }.get(terminal_program, "")
    if not locator.get("terminal_session_id"):
        session = os.environ.get("TERM_SESSION_ID") or os.environ.get("ITERM_SESSION_ID")
        if session:
            locator["terminal_session_id"] = session
    locator.update({key: value for key, value in _process_locator().items() if not locator.get(key)})
    return {key: locator[key] for key in LOCATOR_FIELDS if locator.get(key) not in {None, ""}}


def _valid_identity(provider: str, session_id: str) -> bool:
    return provider in VALID_PROVIDERS and bool(session_id.strip())


def is_subagent_event(payload: dict[str, Any]) -> bool:
    """Reject explicit child-agent events before they can create a Work Unit."""
    event_name = str(payload.get("hook_event_name") or "")
    if event_name in {"SubagentStart", "SubagentStop", "TeammateIdle", "TaskCompleted"}:
        return True
    return bool(payload.get("agent_id") or payload.get("agent_type") or payload.get("teammate_name"))


def ignore_subagent_event(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Record a suppressed child event without creating a Work Unit."""
    session_id = str(payload.get("session_id") or payload.get("thread_id") or "").strip()
    append_event(
        {
            "status": "ignored_subagent",
            "provider": provider,
            "session_id": session_id,
            "event": str(payload.get("hook_event_name") or ""),
        }
    )
    return {"status": "ignored_subagent", "changed": False}


def attach_accounting(unit_id: str, accounting: dict[str, Any]) -> dict[str, Any]:
    """Persist end-only accounting; a running unit is never eligible."""
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        unit = state["units"].get(unit_id)
        if not isinstance(unit, dict) or unit.get("state") == STATE_RUNNING:
            return {"status": "ignored_accounting", "changed": False}
        if "token_accounting" in unit:
            return {"status": "duplicate_accounting", "unit": unit, "changed": False}
        unit["token_accounting"] = accounting
        return {"status": "accounting_recorded", "unit": unit, "changed": True}

    result = _with_lock(operation)
    append_event(
        {
            "status": result["status"],
            "unit_id": unit_id,
            "provider": str(accounting.get("provider") or ""),
            "accounting_status": str(accounting.get("status") or ""),
        }
    )
    return result

def attach_summary(unit_id: str, summary: str | None) -> dict[str, Any]:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        unit = state['units'].get(unit_id)
        if not isinstance(unit, dict): return {'status': 'ignored_summary', 'changed': False}
        unit['summary'] = summary or unit.get('summary') or '处理中…'
        unit['summary_status'] = 'ready' if summary else 'failed'
        unit['summary_weak_marker'] = None if summary else '摘要生成失败'
        return {'status': 'summary_patched', 'unit': unit, 'changed': True}
    result = _with_lock(operation)
    append_event({"status": result["status"], "unit_id": unit_id, "summary_status": "ready" if summary else "failed"})
    return result

def attach_initial_summary(unit_id: str, summary: str) -> dict[str, Any]:
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        unit = state['units'].get(unit_id)
        if not isinstance(unit, dict): return {'status': 'ignored_summary', 'changed': False}
        unit['summary'], unit['summary_status'] = summary, 'pending'
        return {'status': 'summary_initial', 'unit': unit, 'changed': True}
    result = _with_lock(operation)
    append_event({"status": result["status"], "unit_id": unit_id, "summary_status": "pending"})
    return result


def acknowledge_unit(unit_id: str) -> dict[str, Any]:
    """Hide a completed Work Unit from the settlement queue without deleting it."""
    def operation(state: dict[str, Any]) -> dict[str, Any]:
        unit = state["units"].get(unit_id)
        if not isinstance(unit, dict) or unit.get("state") == STATE_RUNNING:
            return {"status": "ignored_acknowledgement", "changed": False}
        if unit.get("seen_at"):
            return {"status": "duplicate_acknowledgement", "unit": unit, "changed": False}
        unit["seen_at"] = time.time()
        return {"status": "acknowledged", "unit": unit, "changed": True}

    result = _with_lock(operation)
    append_event({"status": result["status"], "unit_id": unit_id})
    return result


def snooze_unit(unit_id: str, seconds: int) -> dict[str, Any]:
    """Temporarily suppress a blocked call card; the Work Unit remains queued."""
    bounded_seconds = max(60, min(int(seconds), 24 * 60 * 60))

    def operation(state: dict[str, Any]) -> dict[str, Any]:
        unit = state["units"].get(unit_id)
        if not isinstance(unit, dict) or unit.get("state") != STATE_BLOCKED:
            return {"status": "ignored_snooze", "changed": False}
        unit["snoozed_until"] = time.time() + bounded_seconds
        return {"status": "snoozed", "unit": unit, "changed": True}

    result = _with_lock(operation)
    append_event({"status": result["status"], "unit_id": unit_id, "seconds": bounded_seconds})
    return result


def _unit_id(provider: str, session_id: str, turn_id: str, sequence: int) -> str:
    if provider == "codex" and turn_id:
        return f"codex:{session_id}:{turn_id}"
    return f"{provider}:{session_id}:{sequence}"


def _with_lock(operation: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    lock = lock_path()
    _private_parent(lock)
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        state = load_state()
        result = operation(state)
        if result.get("changed"):
            save_state(state)
        return result


def begin_work_unit(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Move one main-task Work Unit into running without retaining its prompt."""
    session_id = str(payload.get("session_id") or payload.get("thread_id") or "").strip()
    turn_id = str(payload.get("turn_id") or "").strip()
    cwd = str(payload.get("cwd") or "").strip()
    if not _valid_identity(provider, session_id):
        append_event({"status": "ignored_missing_session", "provider": provider})
        return {"status": "ignored_missing_session", "changed": False}
    if is_subagent_event(payload):
        append_event({"status": "ignored_subagent", "provider": provider, "session_id": session_id})
        return {"status": "ignored_subagent", "changed": False}

    def operation(state: dict[str, Any]) -> dict[str, Any]:
        key = session_key(provider, session_id)
        if provider == "codex" and turn_id:
            unit_id = _unit_id(provider, session_id, turn_id, 0)
            existing = state["units"].get(unit_id)
            if isinstance(existing, dict):
                return {"status": "duplicate_start", "unit": existing, "changed": False}
        else:
            sequence = int(state["next_sequence_by_session"].get(key, 0)) + 1
            state["next_sequence_by_session"][key] = sequence
            unit_id = _unit_id(provider, session_id, turn_id, sequence)
        unit = {
            "id": unit_id,
            "provider": provider,
            "session_id": session_id,
            "turn_id": turn_id or None,
            "cwd": cwd,
            "transcript_path": str(payload.get("transcript_path") or "").strip(),
            "session_locator": capture_session_locator(payload),
            "state": STATE_RUNNING,
            "started_at": time.time(),
        }
        state["units"][unit_id] = unit
        state["active_by_session"][key] = unit_id
        return {"status": STATE_RUNNING, "unit": unit, "changed": True}

    result = _with_lock(operation)
    if result["status"] == STATE_RUNNING:
        append_event(
            {
                "status": STATE_RUNNING,
                "provider": provider,
                "session_id": session_id,
                "unit_id": result["unit"]["id"],
            }
        )
    return result


def _explicit_block_reason(payload: dict[str, Any]) -> str:
    for key in ("error", "stop_reason", "reason", "outcome", "status"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip().casefold() in {
            "error",
            "failed",
            "blocked",
            "needs_input",
            "needs-input",
            "incomplete",
        }:
            return f"hook_{key}_{value.strip().casefold()}"
    return ""


def finish_work_unit(
    provider: str,
    payload: dict[str, Any],
    fallback_classifier: Callable[[str], tuple[str, str]],
) -> dict[str, Any]:
    """Finish the active main Work Unit as done or blocked, exactly once."""
    session_id = str(payload.get("session_id") or payload.get("thread_id") or "").strip()
    turn_id = str(payload.get("turn_id") or "").strip()
    event_name = str(payload.get("hook_event_name") or "").strip()
    if not _valid_identity(provider, session_id):
        append_event({"status": "ignored_missing_session", "provider": provider})
        return {"status": "ignored_missing_session", "changed": False}
    if is_subagent_event(payload):
        append_event({"status": "ignored_subagent", "provider": provider, "session_id": session_id})
        return {"status": "ignored_subagent", "changed": False}

    if event_name == "StopFailure":
        target_state, reason = STATE_BLOCKED, "claude_stop_failure"
    elif explicit_reason := _explicit_block_reason(payload):
        target_state, reason = STATE_BLOCKED, explicit_reason
    else:
        message = payload.get("last_assistant_message")
        classification, marker = fallback_classifier(message if isinstance(message, str) else "")
        target_state = STATE_BLOCKED if classification == "attention" else STATE_DONE
        reason = f"fallback_{marker}"

    def operation(state: dict[str, Any]) -> dict[str, Any]:
        key = session_key(provider, session_id)
        unit_id = ""
        if provider == "codex" and turn_id:
            candidate = _unit_id(provider, session_id, turn_id, 0)
            if candidate in state["units"]:
                unit_id = candidate
        unit_id = unit_id or str(state["active_by_session"].get(key) or "")
        unit = state["units"].get(unit_id)
        if not isinstance(unit, dict):
            return {"status": "ignored_missing_start", "changed": False}
        if unit.get("state") in {STATE_BLOCKED, STATE_DONE}:
            return {"status": "duplicate_finish", "unit": unit, "changed": False}
        unit["state"] = target_state
        unit["ended_at"] = time.time()
        unit["outcome_reason"] = reason
        state["active_by_session"].pop(key, None)
        return {"status": target_state, "unit": unit, "changed": True}

    result = _with_lock(operation)
    log = {"status": result["status"], "provider": provider, "session_id": session_id}
    if "unit" in result:
        log["unit_id"] = result["unit"]["id"]
    if result["status"] in VALID_STATES - {STATE_RUNNING}:
        log["reason"] = reason
    append_event(log)
    return result
