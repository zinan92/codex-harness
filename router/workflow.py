"""Serial v0 workflow: classify -> fixed SOP -> machine gate -> review -> receipt."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from .config import DEVELOPER_MODEL, REVIEWER_MODEL, SOPS, TRIAGE_MODEL
from .prompts import developer_prompt, review_prompt, triage_prompt
from .schema import Review, SchemaError, Story, Triage


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    profile: str | None
    message: str = ""


def _usd_cents(value: float | None) -> int | None:
    if value is None:
        return None
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _codex_snapshot() -> dict[str, int]:
    """Read the existing collector before/after a child call; never modify it or its sources."""
    try:
        from ledger.collect import collect_codex

        return {record["source_file"]: int(record["cost_cents"]) for record in collect_codex()["records"]}
    except (ImportError, OSError, KeyError, TypeError, ValueError):
        return {}


def _codex_delta(before: dict[str, int], after: dict[str, int]) -> int | None:
    if not before and not after:
        return None
    return sum(max(0, cost - before.get(path, 0)) for path, cost in after.items())


class Workflow:
    def __init__(self, *, triage: Any, developer: Any, gate: Any, reviewer: Any, store: Any):
        self.triage_adapter = triage
        self.developer = developer
        self.gate = gate
        self.reviewer = reviewer
        self.store = store

    def _finish(self, run: dict[str, Any], status: str, profile: str | None, message: str) -> RunResult:
        self.store.finish(run, status, message)
        return RunResult(run["run_id"], status, profile, message)

    def run(self, *, task: str, workspace: Path, dry_run: bool = False) -> RunResult:
        run = self.store.start(task, workspace)
        triage_call = self.triage_adapter.triage(triage_prompt(task), workspace)
        self.store.event(run, "model_call", {
            "role": "triage", "model": TRIAGE_MODEL, "ok": triage_call.ok,
            "returncode": triage_call.returncode, "cost_cents": _usd_cents(triage_call.cost_usd),
        })
        if not triage_call.ok:
            return self._finish(run, "failed_triage", None, triage_call.stderr or "Fable call failed")
        try:
            triage = Triage.from_response(triage_call.payload)
        except SchemaError as exc:
            return self._finish(run, "failed_triage", None, str(exc))
        self.store.event(run, "triage_complete", triage.as_json())
        if dry_run:
            return self._finish(run, "planned", triage.profile, "dry run: no implementation was invoked")

        stories: tuple[Story | None, ...] = triage.stories if SOPS[triage.profile].stories_required else (None,)
        for index, story in enumerate(stories, start=1):
            before = _codex_snapshot()
            implementation = self.developer.implement(developer_prompt(task, triage, story), workspace)
            cost_cents = _codex_delta(before, _codex_snapshot())
            self.store.event(run, "model_call", {
                "role": "developer", "model": DEVELOPER_MODEL, "ok": implementation.ok,
                "returncode": implementation.returncode, "story": index if story else None,
                "cost_cents": cost_cents,
            })
            if not implementation.ok:
                return self._finish(run, "failed_implementation", triage.profile,
                                    implementation.stderr or "Codex implementation failed")
            gate = self.gate.check(workspace)
            self.store.event(run, "machine_gate", {
                "ok": gate.ok, "returncode": gate.returncode, "story": index if story else None,
            })
            if not gate.ok:
                return self._finish(run, "failed_machine_gate", triage.profile,
                                    gate.stderr or gate.stdout or "machine gate failed")

        review_call = self.reviewer.review(review_prompt(task, triage), workspace)
        self.store.event(run, "model_call", {
            "role": "reviewer", "model": REVIEWER_MODEL, "ok": review_call.ok,
            "returncode": review_call.returncode, "cost_cents": _usd_cents(review_call.cost_usd),
        })
        if not review_call.ok:
            return self._finish(run, "failed_review", triage.profile,
                                review_call.stderr or "Opus review call failed")
        try:
            review = Review.from_response(review_call.payload)
        except SchemaError as exc:
            return self._finish(run, "failed_review", triage.profile, str(exc))
        self.store.event(run, "review_complete", {
            "verdict": review.verdict, "summary": review.summary, "evidence": list(review.evidence),
        })
        if review.verdict == "fail":
            return self._finish(run, "failed_review", triage.profile, review.summary)
        return self._finish(run, "succeeded", triage.profile, review.summary)
