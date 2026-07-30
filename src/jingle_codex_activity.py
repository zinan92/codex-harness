#!/usr/bin/python3
"""Read only the local Codex activity metadata needed to reconcile Jingle.

This bridge deliberately exposes no prompt, preview, or database ``title``.
Codex's SQLite title often is the first user prompt. A separately maintained
session-index name is used only as a short, non-persisted display label.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterable


CODEX_DIR = Path.home() / ".codex"
STATE_DATABASES = (CODEX_DIR / "state_5.sqlite", CODEX_DIR / "sqlite" / "state_5.sqlite")
SESSION_INDEX_PATH = CODEX_DIR / "session_index.jsonl"


def safe_session_name(value: object) -> str:
    """Accept only a short one-line session-index label for display."""
    raw = str(value or "").strip()
    if not raw or "\n" in raw or "\r" in raw or len(raw) > 48:
        return ""
    return raw if all(character.isprintable() for character in raw) else ""


def load_session_names(path: Path, session_ids: set[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    if not path.is_file() or not session_ids:
        return names
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    candidate = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(candidate, dict):
                    continue
                session_id = str(candidate.get("id") or "")
                if session_id not in session_ids:
                    continue
                if name := safe_session_name(candidate.get("thread_name")):
                    names[session_id] = name
    except OSError:
        pass
    return names


def read_activity(
    session_ids: Iterable[str],
    databases: Iterable[Path] = STATE_DATABASES,
    session_index_path: Path = SESSION_INDEX_PATH,
) -> dict[str, dict[str, Any]]:
    """Return Codex's current non-sensitive thread metadata for requested IDs."""
    requested = {str(session_id).strip() for session_id in session_ids if str(session_id).strip()}
    if not requested:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    placeholders = ",".join("?" for _ in requested)
    for database in databases:
        if not database.is_file():
            continue
        try:
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=0.15)
            try:
                connection.execute("PRAGMA query_only = ON")
                connection.execute("PRAGMA busy_timeout = 150")
                for row in connection.execute(
                    f"SELECT id, updated_at, archived, cwd FROM threads WHERE id IN ({placeholders})",
                    tuple(requested),
                ):
                    thread_id, updated_at, archived, cwd = row
                    rows[str(thread_id)] = {
                        "updated_at": float(updated_at or 0),
                        "archived": bool(archived),
                        "cwd": str(cwd or ""),
                    }
            finally:
                connection.close()
        except (OSError, sqlite3.Error):
            continue
    names = load_session_names(session_index_path, requested)
    for session_id, row in rows.items():
        if name := names.get(session_id):
            row["display_name"] = name
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", action="append", default=[])
    arguments = parser.parse_args()
    print(json.dumps({"sessions": read_activity(arguments.session_id)}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
