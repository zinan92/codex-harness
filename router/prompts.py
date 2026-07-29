"""Prompts make the human-approved SOP explicit to every model call."""

from __future__ import annotations

import json

from .schema import Contract, Story, Triage


def triage_prompt(task: str) -> str:
    return """You are the TokenRouter triage and contract writer. Classify the task as exactly one of simple, medium, or complex. Do not predict cost, select a model, use historical success rates, or propose escalation.

Fixed SOPs:
- simple: one Codex implementation call, one machine gate, then one Opus review.
- medium: write a contract, then one Codex implementation call, one machine gate, then one Opus review.
- complex: write a contract and serial stories; Codex implements each story in order, the machine gate runs after every story, then Opus reviews the whole result.

For medium and complex, contract must contain outcome, 3-7 observable acceptance paths, in_scope, out_scope, and forbidden. For complex, every story must have a title and a 2-5 step demo_path. No story may rely on another story running in parallel.

Return JSON only, with this shape:
{"complexity":"simple|medium|complex","rationale":"...","contract":null|{"outcome":"...","acceptance":["..."],"in_scope":["..."],"out_scope":["..."],"forbidden":["..."]},"stories":[{"title":"...","demo_path":["..."]}]}

Task:
""" + task


def developer_prompt(
    task: str,
    triage: Triage,
    story: Story | None,
    previous_failure: str = "",
) -> str:
    scope = {
        "task": task,
        "profile": triage.profile,
        "contract": triage.contract.as_json() if triage.contract else None,
        "story": story.as_json() if story else None,
        "previous_failure": previous_failure,
    }
    return """You are the implementation worker in a fixed TokenRouter SOP. Implement exactly the assigned task in the current workspace. Respect the contract and, when present, implement only the supplied story. Do not change acceptance criteria, do not create a new plan, do not delegate, push, delete data, or change permissions. Do not commit unless the assignment explicitly requires a scoped local commit so the repository's required machine gate can inspect a clean workspace. Run focused checks that are useful to the implementation. The orchestrator will run the required machine gate after this call.

Assignment JSON (the `previous_failure` field is empty on the first attempt; when present, fix it before completing the assignment):
""" + json.dumps(scope, ensure_ascii=False, indent=2)


def review_prompt(task: str, triage: Triage) -> str:
    scope = {
        "task": task,
        "profile": triage.profile,
        "contract": triage.contract.as_json() if triage.contract else None,
        "stories": [story.as_json() for story in triage.stories],
    }
    return """You are the final reviewer after a passing machine gate. Inspect the current workspace against the assignment below. Do not edit files. Return JSON only: {"verdict":"pass|fail","summary":"...","evidence":["..."]}. A failing review is recorded for the orchestrator's fixed, bounded retry policy; do not select a model, suggest a more expensive model, or alter that policy.

Assignment JSON:
""" + json.dumps(scope, ensure_ascii=False, indent=2)
