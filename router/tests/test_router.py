from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from router.adapters import CallResult
from router.ledger import RunStore
from router.schema import SchemaError, Triage
from router.workflow import Workflow


def triage_payload(profile="medium", stories=None):
    result = {
        "complexity": profile,
        "rationale": "The requested observable change determines this fixed SOP.",
        "contract": None,
        "stories": stories or [],
    }
    if profile in {"medium", "complex"}:
        result["contract"] = {
            "outcome": "A user can observe the requested change.",
            "acceptance": ["Open the feature", "Perform the action", "Observe the result"],
            "in_scope": ["the requested feature"],
            "out_scope": ["unrelated refactors"],
            "forbidden": ["data deletion"],
        }
    return {"result": json.dumps(result)}


class FakeTriage:
    def __init__(self, payload):
        self.payload = payload

    def triage(self, prompt, workspace):
        return CallResult(True, "", "", 0, self.payload, 0.01)


class FakeDeveloper:
    def __init__(self):
        self.calls = 0

    def implement(self, prompt, workspace):
        self.calls += 1
        return CallResult(True, "implemented", "", 0)


class FakeGate:
    def __init__(self, outcomes=(True,)):
        self.outcomes = list(outcomes)
        self.calls = 0

    def check(self, workspace):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        return CallResult(outcome, "gate output", "gate error" if not outcome else "", 0 if outcome else 1)


class FakeReviewer:
    def __init__(self, verdict="pass"):
        self.calls = 0
        self.verdict = verdict

    def review(self, prompt, workspace):
        self.calls += 1
        payload = {"result": json.dumps({
            "verdict": self.verdict, "summary": "reviewed", "evidence": ["machine gate passed"],
        })}
        return CallResult(True, "", "", 0, payload, 0.02)


class RouterSchemaTests(unittest.TestCase):
    def test_claude_envelope_parses_complex_contract_and_stories(self):
        payload = triage_payload("complex", [
            {"title": "first visible change", "demo_path": ["Open X", "Do Y", "See Z"]},
            {"title": "second visible change", "demo_path": ["Open X", "Do Q", "See R"]},
        ])
        triage = Triage.from_response(payload)
        self.assertEqual("complex", triage.profile)
        self.assertEqual(2, len(triage.stories))
        self.assertEqual(3, len(triage.contract.acceptance))

    def test_complex_without_contract_fails_closed(self):
        payload = triage_payload("complex", [{"title": "x", "demo_path": ["a", "b"]}])
        payload["result"] = json.dumps({**json.loads(payload["result"]), "contract": None})
        with self.assertRaises(SchemaError):
            Triage.from_response(payload)


class RouterWorkflowTests(unittest.TestCase):
    def make_workflow(self, payload, gate_outcomes=(True,), verdict="pass"):
        self.developer = FakeDeveloper()
        self.gate = FakeGate(gate_outcomes)
        self.reviewer = FakeReviewer(verdict)
        self.tempdir = tempfile.TemporaryDirectory()
        return Workflow(
            triage=FakeTriage(payload), developer=self.developer, gate=self.gate,
            reviewer=self.reviewer, store=RunStore(Path(self.tempdir.name)),
        )

    def tearDown(self):
        if hasattr(self, "tempdir"):
            self.tempdir.cleanup()

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_medium_is_one_implementation_one_gate_one_review(self, _snapshot):
        workflow = self.make_workflow(triage_payload("medium"))
        result = workflow.run(task="change X to Y", workspace=Path.cwd())
        self.assertEqual("succeeded", result.status)
        self.assertEqual(1, self.developer.calls)
        self.assertEqual(1, self.gate.calls)
        self.assertEqual(1, self.reviewer.calls)

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_complex_is_serial_and_stops_at_first_failed_gate(self, _snapshot):
        workflow = self.make_workflow(
            triage_payload("complex", [
                {"title": "one", "demo_path": ["open", "act"]},
                {"title": "two", "demo_path": ["open", "act"]},
            ]), gate_outcomes=(True, False),
        )
        result = workflow.run(task="build a feature", workspace=Path.cwd())
        self.assertEqual("failed_machine_gate", result.status)
        self.assertEqual(2, self.developer.calls)
        self.assertEqual(2, self.gate.calls)
        self.assertEqual(0, self.reviewer.calls)

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_dry_run_stops_after_triage(self, _snapshot):
        workflow = self.make_workflow(triage_payload("simple"))
        result = workflow.run(task="small change", workspace=Path.cwd(), dry_run=True)
        self.assertEqual("planned", result.status)
        self.assertEqual(0, self.developer.calls)
        self.assertEqual(0, self.gate.calls)
        self.assertEqual(0, self.reviewer.calls)
