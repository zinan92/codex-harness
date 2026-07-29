"""Pure-standard-library aggregation utilities for router run receipts."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ProfileCounter = defaultdict[str, int]
StatusCounter = defaultdict[str, int]


UNKNOWN_PROFILE = "unclassified"


def _iter_receipts(runs_dir: Path) -> list[Path]:
    return sorted(p for p in Path(runs_dir).iterdir() if p.suffix == ".json")


def _read_receipt(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _as_profile(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _extract_profile(run: dict[str, Any]) -> str:
    if (profile := _as_profile(run.get("profile"))) is not None:
        return profile

    events = run.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("kind") != "triage_complete":
                continue
            profile = _as_profile(event.get("complexity"))
            if profile is not None:
                return profile

    return UNKNOWN_PROFILE


def _extract_status(run: dict[str, Any]) -> str | None:
    status = _as_profile(run.get("status"))
    if status is not None:
        return status

    events = run.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("kind") != "run_finished":
                continue
            status = _as_profile(event.get("status"))
            if status is not None:
                return status
    return None


def _is_dry_run_receipt(run: dict[str, Any]) -> bool:
    for message in [run.get("message"), run.get("result")]:
        if isinstance(message, str) and "dry run" in message.lower():
            return True

    events = run.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("kind") != "run_finished":
                continue
            message = event.get("message")
            if isinstance(message, str) and "dry run" in message.lower():
                return True
    return False


def _is_completed_status(status: str) -> bool:
    return status not in {"running", "planned"}


def _to_int_cents(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    return None


def _extract_cost_cents(run: dict[str, Any]) -> int:
    events = run.get("events")
    if not isinstance(events, list):
        return 0

    total = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("kind") != "model_call":
            continue
        cents = event.get("cost_cents")
        amount = _to_int_cents(cents)
        if amount is None:
            continue
        total += amount
    return total


def _ordered(mapping: defaultdict[str, int]) -> dict[str, int]:
    return {key: mapping[key] for key in sorted(mapping)}


def _ordered_nested(mapping: dict[str, int]) -> dict[str, int]:
    return {key: mapping[key] for key in sorted(mapping)}


def _empty_summary() -> dict[str, Any]:
    """Return the canonical zero summary used when runs_dir is empty, missing, or not a directory."""
    return {
        "completed_runs": 0,
        "total_cost_cents": 0,
        "by_profile": {},
        "by_status": {},
        "invalid_receipts": _ordered_nested({
            "malformed_json": 0,
            "invalid_structure": 0,
        }),
    }


def aggregate_runs(runs_dir: Path) -> dict[str, Any]:
    """Aggregate completed, non-dry-run run receipts into a deterministic summary."""
    if not runs_dir.is_dir():
        return _empty_summary()

    profile_counts: ProfileCounter = defaultdict(int)
    status_counts: StatusCounter = defaultdict(int)
    invalid_receipts = {
        "malformed_json": 0,
        "invalid_structure": 0,
    }

    completed_runs = 0
    total_cost_cents = 0

    for path in _iter_receipts(runs_dir):
        try:
            data = _read_receipt(path)
        except (OSError, json.JSONDecodeError):
            invalid_receipts["malformed_json"] += 1
            continue

        if not isinstance(data, dict):
            invalid_receipts["invalid_structure"] += 1
            continue

        status = _extract_status(data)
        if not isinstance(status, str):
            invalid_receipts["invalid_structure"] += 1
            continue

        if _is_dry_run_receipt(data):
            continue

        if not _is_completed_status(status):
            continue

        profile = _extract_profile(data)
        profile_counts[profile] += 1
        status_counts[status] += 1
        completed_runs += 1
        total_cost_cents += _extract_cost_cents(data)

    return {
        "completed_runs": completed_runs,
        "total_cost_cents": total_cost_cents,
        "by_profile": _ordered(profile_counts),
        "by_status": _ordered(status_counts),
        "invalid_receipts": _ordered_nested({
            "malformed_json": invalid_receipts["malformed_json"],
            "invalid_structure": invalid_receipts["invalid_structure"],
        }),
    }
