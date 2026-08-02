"""Strict model-output schema. A malformed judgement is a failed run, not a guess."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .config import SOPS


class SchemaError(ValueError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError("{} must be a non-empty string".format(field))
    return value.strip()


def _strings(
    value: Any,
    field: str,
    minimum: int = 0,
    maximum: int | None = None,
    *,
    unique: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise SchemaError("{} must be an array of non-empty strings".format(field))
    if len(value) < minimum or (maximum is not None and len(value) > maximum):
        raise SchemaError("{} must contain {}{} items".format(
            field, minimum, " to {}".format(maximum) if maximum is not None else " or more"
        ))
    values = tuple(item.strip() for item in value)
    if unique and len(set(values)) != len(values):
        raise SchemaError("{} must not contain duplicate values".format(field))
    return values


def _object_from_response(payload: Any) -> dict[str, Any]:
    """Accept Claude's outer ``--output-format json`` envelope or a raw test payload."""
    candidate = payload
    if isinstance(payload, dict) and "result" in payload:
        candidate = payload["result"]
    if isinstance(candidate, str):
        candidate = candidate.strip()
        if candidate.startswith("```"):
            candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
            candidate = candidate.rsplit("```", 1)[0].strip()
        try:
            candidate = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise SchemaError("model result is not JSON") from exc
    if not isinstance(candidate, dict):
        raise SchemaError("model result must be a JSON object")
    return candidate


@dataclass(frozen=True)
class Contract:
    outcome: str
    acceptance: tuple[str, ...]
    in_scope: tuple[str, ...]
    out_scope: tuple[str, ...]
    forbidden: tuple[str, ...]

    @classmethod
    def from_json(cls, value: Any) -> "Contract":
        if not isinstance(value, dict):
            raise SchemaError("contract must be an object")
        return cls(
            outcome=_text(value.get("outcome"), "contract.outcome"),
            acceptance=_strings(value.get("acceptance"), "contract.acceptance", 3, 7, unique=True),
            in_scope=_strings(value.get("in_scope"), "contract.in_scope", 1, unique=True),
            out_scope=_strings(value.get("out_scope", []), "contract.out_scope", unique=True),
            forbidden=_strings(value.get("forbidden", []), "contract.forbidden", unique=True),
        )

    def as_json(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "acceptance": list(self.acceptance),
            "in_scope": list(self.in_scope),
            "out_scope": list(self.out_scope),
            "forbidden": list(self.forbidden),
        }


@dataclass(frozen=True)
class Story:
    title: str
    demo_path: tuple[str, ...]

    @classmethod
    def from_json(cls, value: Any) -> "Story":
        if not isinstance(value, dict):
            raise SchemaError("each story must be an object")
        return cls(
            title=_text(value.get("title"), "story.title"),
            demo_path=_strings(value.get("demo_path"), "story.demo_path", 2, 5),
        )

    def as_json(self) -> dict[str, object]:
        return {"title": self.title, "demo_path": list(self.demo_path)}


@dataclass(frozen=True)
class Triage:
    profile: str
    rationale: str
    contract: Contract | None
    stories: tuple[Story, ...]

    @classmethod
    def from_response(cls, payload: Any) -> "Triage":
        value = _object_from_response(payload)
        profile = _text(value.get("complexity"), "complexity")
        if profile not in SOPS:
            raise SchemaError("complexity must be one of: {}".format(", ".join(SOPS)))
        rationale = _text(value.get("rationale"), "rationale")
        sop = SOPS[profile]
        if sop.contract_required and "contract" not in value:
            raise SchemaError("{} requires a contract".format(profile))
        contract = Contract.from_json(value["contract"]) if sop.contract_required else None
        stories = tuple(Story.from_json(item) for item in value.get("stories", []))
        if sop.stories_required and not stories:
            raise SchemaError("complex requires at least one story")
        if not sop.stories_required and stories:
            raise SchemaError("{} must not emit stories".format(profile))
        return cls(profile=profile, rationale=rationale, contract=contract, stories=stories)

    def as_json(self) -> dict[str, object]:
        return {
            "complexity": self.profile,
            "rationale": self.rationale,
            "contract": self.contract.as_json() if self.contract else None,
            "stories": [story.as_json() for story in self.stories],
        }


@dataclass(frozen=True)
class Review:
    verdict: str
    summary: str
    evidence: tuple[str, ...]

    @classmethod
    def from_response(cls, payload: Any) -> "Review":
        """Parse Claude output and reject malformed pass/fail review verdicts."""
        value = _object_from_response(payload)
        verdict = _text(value.get("verdict"), "verdict")
        if verdict not in {"pass", "fail"}:
            raise SchemaError("review.verdict must be pass or fail")
        return cls(
            verdict=verdict,
            summary=_text(value.get("summary"), "review.summary"),
            evidence=_strings(value.get("evidence", []), "review.evidence"),
        )
