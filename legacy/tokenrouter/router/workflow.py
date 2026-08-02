"""Serial v0 workflow: classify -> fixed SOP -> machine gate -> review -> receipt."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from .config import (
    DEVELOPER_MODEL,
    MEDIUM_IMPL_MAX_ATTEMPTS,
    MEDIUM_REVIEW_MAX_ROUNDS,
    REVIEWER_MODEL,
    SIMPLE_MAX_ATTEMPTS,
    SOPS,
    TRIAGE_MODEL,
)
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

    def _implement_and_gate(
        self,
        *,
        run: dict[str, Any],
        task: str,
        triage: Triage,
        story: Story | None,
        workspace: Path,
        story_index: int | None,
        review_round: int | None,
        max_attempts: int,
        previous_failure: str = "",
    ) -> tuple[bool, str]:
        """Run bounded implementation/gate attempts, returning the final failure context."""
        failure_context = previous_failure
        for attempt in range(1, max_attempts + 1):
            before = _codex_snapshot()
            implementation = self.developer.implement(
                developer_prompt(task, triage, story, failure_context), workspace
            )
            cost_cents = _codex_delta(before, _codex_snapshot())
            self.store.event(run, "model_call", {
                "role": "developer", "model": DEVELOPER_MODEL, "ok": implementation.ok,
                "returncode": implementation.returncode, "story": story_index,
                "review_round": review_round, "attempt": attempt, "cost_cents": cost_cents,
            })
            if not implementation.ok:
                failure_context = implementation.stderr or implementation.stdout or "Codex implementation failed"
                self.store.event(run, "implementation_retry", {
                    "story": story_index, "review_round": review_round, "attempt": attempt,
                    "reason": failure_context, "will_retry": attempt < max_attempts,
                })
                continue

            gate = self.gate.check(workspace)
            self.store.event(run, "machine_gate", {
                "ok": gate.ok, "returncode": gate.returncode, "story": story_index,
                "review_round": review_round, "attempt": attempt,
                "command": list(getattr(self.gate, "command", ())),
            })
            if gate.ok:
                return True, ""
            failure_context = gate.stderr or gate.stdout or "machine gate failed"
            self.store.event(run, "machine_gate_retry", {
                "story": story_index, "review_round": review_round, "attempt": attempt,
                "reason": failure_context, "will_retry": attempt < max_attempts,
            })
        return False, failure_context

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
        initial_attempts = SIMPLE_MAX_ATTEMPTS if triage.profile == "simple" else MEDIUM_IMPL_MAX_ATTEMPTS
        if triage.profile == "complex":
            for index, story in enumerate(stories, start=1):
                passed, failure = self._implement_and_gate(
                    run=run, task=task, triage=triage, story=story, workspace=workspace,
                    story_index=index, review_round=None, max_attempts=MEDIUM_IMPL_MAX_ATTEMPTS,
                )
                if not passed:
                    return self._finish(run, "failed_machine_gate", triage.profile, failure)
            review_rounds = 1
        else:
            review_rounds = MEDIUM_REVIEW_MAX_ROUNDS if triage.profile == "medium" else 1

        review_feedback = ""
        for review_round in range(1, review_rounds + 1):
            if triage.profile != "complex":
                passed, failure = self._implement_and_gate(
                    run=run, task=task, triage=triage, story=None, workspace=workspace,
                    story_index=None, review_round=review_round, max_attempts=initial_attempts,
                    previous_failure=review_feedback,
                )
                if not passed:
                    return self._finish(run, "failed_machine_gate", triage.profile, failure)

            review_call = self.reviewer.review(review_prompt(task, triage), workspace)
            self.store.event(run, "model_call", {
                "role": "reviewer", "model": REVIEWER_MODEL, "ok": review_call.ok,
                "returncode": review_call.returncode, "review_round": review_round,
                "cost_cents": _usd_cents(review_call.cost_usd),
            })
            if not review_call.ok:
                return self._finish(run, "failed_review", triage.profile,
                                    review_call.stderr or "Opus review call failed")
            try:
                review = Review.from_response(review_call.payload)
            except SchemaError as exc:
                return self._finish(run, "failed_review", triage.profile, str(exc))
            self.store.event(run, "review_complete", {
                "round": review_round, "verdict": review.verdict,
                "summary": review.summary, "evidence": list(review.evidence),
            })
            if review.verdict == "pass":
                return self._finish(run, "succeeded", triage.profile, review.summary)
            review_feedback = "Review round {} rejected the work. Summary: {}\nEvidence: {}".format(
                review_round, review.summary, "\n".join(review.evidence)
            )
            self.store.event(run, "review_retry", {
                "round": review_round, "summary": review.summary,
                "evidence": list(review.evidence), "will_retry": review_round < review_rounds,
            })
        return self._finish(run, "failed_review", triage.profile, review_feedback)
