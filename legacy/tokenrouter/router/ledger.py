"""Append-only, post-hoc run receipts kept separate from the protected legacy ledger."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_run_id() -> str:
    return "run-{}-{}".format(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), secrets.token_hex(4))


class RunStore:
    def __init__(self, root: Path):
        self.root = root
        self.runs = root / "runs"
        self.receipts = root / "ledger.jsonl"

    def start(self, task: str, workspace: Path) -> dict[str, Any]:
        run = {
            "run_id": new_run_id(),
            "started_at": utc_now(),
            "task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest(),
            "workspace": str(workspace),
            "status": "running",
            "events": [],
        }
        self.save(run)
        self.event(run, "run_started", {"workspace": str(workspace)})
        return run

    def event(self, run: dict[str, Any], kind: str, details: dict[str, Any]) -> None:
        event = {"at": utc_now(), "kind": kind, **details}
        run["events"].append(event)
        self._append({"run_id": run["run_id"], **event})
        self.save(run)

    def finish(self, run: dict[str, Any], status: str, message: str = "") -> None:
        run["status"] = status
        run["finished_at"] = utc_now()
        run["message"] = message
        self.event(run, "run_finished", {"status": status, "message": message})

    def save(self, run: dict[str, Any]) -> None:
        self.runs.mkdir(parents=True, exist_ok=True)
        target = self.runs / "{}.json".format(run["run_id"])
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)

    def _append(self, event: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.receipts.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
