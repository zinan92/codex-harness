"""The v0 personnel and SOP are constants, never cost-driven choices."""

from __future__ import annotations

from dataclasses import dataclass


TRIAGE_MODEL = "claude-fable-5"
DEVELOPER_MODEL = "gpt-5.3-codex-spark"
REVIEWER_MODEL = "opus"
MACHINE_GATE = ("bash", "scripts/check.sh")

# Attempt/round ceilings are contractual: retries never escalate to another model.
SIMPLE_MAX_ATTEMPTS = 2
MEDIUM_IMPL_MAX_ATTEMPTS = 2
MEDIUM_REVIEW_MAX_ROUNDS = 2


@dataclass(frozen=True)
class Sop:
    """A fixed sequence selected only by Fable's complexity classification."""

    name: str
    contract_required: bool
    stories_required: bool
    gate_after_each_story: bool


SOPS = {
    "simple": Sop("simple", contract_required=False, stories_required=False, gate_after_each_story=False),
    "medium": Sop("medium", contract_required=True, stories_required=False, gate_after_each_story=False),
    "complex": Sop("complex", contract_required=True, stories_required=True, gate_after_each_story=True),
}
