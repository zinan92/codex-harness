from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from router.adapters import CallResult
from router.config import DEVELOPER_MODEL
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
        self.prompts = []

    def implement(self, prompt, workspace):
        self.calls += 1
        self.prompts.append(prompt)
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
    def __init__(self, verdicts=("pass",)):
        self.calls = 0
        self.verdicts = list(verdicts)

    def review(self, prompt, workspace):
        self.calls += 1
        verdict = self.verdicts[self.calls - 1]
        payload = {"result": json.dumps({
            "verdict": verdict,
            "summary": "review {}".format(self.calls),
            "evidence": ["evidence {}".format(self.calls)],
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

    def test_contract_rejects_duplicate_normalized_values(self):
        duplicate_cases = {
            "acceptance": ["Open menu", " Open menu ", "Confirm"],
            "in_scope": ["feature area", "  feature area  "],
            "out_scope": ["unrelated change", "   unrelated change"],
            "forbidden": ["delete", " delete "],
        }

        for field, values in duplicate_cases.items():
            with self.subTest(field=field):
                payload = triage_payload("medium")
                payload_dict = json.loads(payload["result"])
                payload_dict["contract"][field] = values
                payload["result"] = json.dumps(payload_dict)
                with self.assertRaises(SchemaError):
                    Triage.from_response(payload)

    def test_contract_distinct_normalized_values_are_accepted(self):
        payload = triage_payload("medium")
        payload_dict = json.loads(payload["result"])
        payload_dict["contract"]["acceptance"] = ["Open menu", " Perform Action ", "Verify result"]
        payload_dict["contract"]["in_scope"] = [" requested feature", "targeted area"]
        payload_dict["contract"]["out_scope"] = ["  unrelated paths", " other modules "]
        payload_dict["contract"]["forbidden"] = [" delete", "modify tests "]
        payload["result"] = json.dumps(payload_dict)

        triage = Triage.from_response(payload)
        self.assertIsNotNone(triage.contract)
        self.assertEqual(("Open menu", "Perform Action", "Verify result"), triage.contract.acceptance)
        self.assertEqual(("requested feature", "targeted area"), triage.contract.in_scope)
        self.assertEqual(("unrelated paths", "other modules"), triage.contract.out_scope)
        self.assertEqual(("delete", "modify tests"), triage.contract.forbidden)


class RouterWorkflowTests(unittest.TestCase):
    def make_workflow(self, payload, gate_outcomes=(True,), verdicts=("pass",)):
        self.developer = FakeDeveloper()
        self.gate = FakeGate(gate_outcomes)
        self.reviewer = FakeReviewer(verdicts)
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = RunStore(Path(self.tempdir.name))
        return Workflow(
            triage=FakeTriage(payload), developer=self.developer, gate=self.gate,
            reviewer=self.reviewer, store=self.store,
        )

    def tearDown(self):
        if hasattr(self, "tempdir"):
            self.tempdir.cleanup()

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_simple_first_attempt_passes_with_one_developer_call(self, _snapshot):
        workflow = self.make_workflow(triage_payload("simple"))
        result = workflow.run(task="change one wording", workspace=Path.cwd())
        self.assertEqual("succeeded", result.status)
        self.assertEqual(1, self.developer.calls)
        self.assertEqual(1, self.gate.calls)
        self.assertEqual(1, self.reviewer.calls)

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_simple_two_failed_gates_stop_after_configured_attempts(self, _snapshot):
        workflow = self.make_workflow(triage_payload("simple"), gate_outcomes=(False, False))
        result = workflow.run(task="change one wording", workspace=Path.cwd())
        self.assertEqual("failed_machine_gate", result.status)
        self.assertEqual(2, self.developer.calls)
        self.assertEqual(2, self.gate.calls)
        self.assertEqual(0, self.reviewer.calls)
        self.assertIn("gate error", self.developer.prompts[1])
        events = json.loads((self.store.runs / "{}.json".format(result.run_id)).read_text())["events"]
        developer_models = [event["model"] for event in events if event["kind"] == "model_call"
                            and event["role"] == "developer"]
        self.assertEqual([DEVELOPER_MODEL, DEVELOPER_MODEL], developer_models)

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_medium_review_rejection_reimplements_with_review_feedback(self, _snapshot):
        workflow = self.make_workflow(
            triage_payload("medium"), gate_outcomes=(True, True), verdicts=("fail", "pass")
        )
        result = workflow.run(task="change X to Y", workspace=Path.cwd())
        self.assertEqual("succeeded", result.status)
        self.assertEqual(2, self.developer.calls)
        self.assertEqual(2, self.gate.calls)
        self.assertEqual(2, self.reviewer.calls)
        self.assertIn("review 1", self.developer.prompts[1])
        self.assertIn("evidence 1", self.developer.prompts[1])

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_medium_two_review_rejections_stop_after_two_developer_calls(self, _snapshot):
        workflow = self.make_workflow(
            triage_payload("medium"), gate_outcomes=(True, True), verdicts=("fail", "fail")
        )
        result = workflow.run(task="change X to Y", workspace=Path.cwd())
        self.assertEqual("failed_review", result.status)
        self.assertEqual(2, self.developer.calls)
        self.assertEqual(2, self.gate.calls)
        self.assertEqual(2, self.reviewer.calls)

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_medium_gate_failure_retries_with_gate_feedback(self, _snapshot):
        workflow = self.make_workflow(triage_payload("medium"), gate_outcomes=(False, True))
        result = workflow.run(task="change X to Y", workspace=Path.cwd())
        self.assertEqual("succeeded", result.status)
        self.assertEqual(2, self.developer.calls)
        self.assertIn("gate error", self.developer.prompts[1])

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_complex_retries_failed_story_gate_before_next_story(self, _snapshot):
        workflow = self.make_workflow(
            triage_payload("complex", [
                {"title": "one", "demo_path": ["open", "act"]},
                {"title": "two", "demo_path": ["open", "act"]},
            ]), gate_outcomes=(True, False, True),
        )
        result = workflow.run(task="build a feature", workspace=Path.cwd())
        self.assertEqual("succeeded", result.status)
        self.assertEqual(3, self.developer.calls)
        self.assertEqual(3, self.gate.calls)
        self.assertEqual(1, self.reviewer.calls)
        self.assertIn("gate error", self.developer.prompts[2])

    @patch("router.workflow._codex_snapshot", return_value={})
    def test_dry_run_stops_after_triage(self, _snapshot):
        workflow = self.make_workflow(triage_payload("simple"))
        result = workflow.run(task="small change", workspace=Path.cwd(), dry_run=True)
        self.assertEqual("planned", result.status)
        self.assertEqual(0, self.developer.calls)
        self.assertEqual(0, self.gate.calls)
        self.assertEqual(0, self.reviewer.calls)
