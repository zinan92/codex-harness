from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from router.__main__ import main
from router.summary import aggregate_runs


class RouterSummaryTests(unittest.TestCase):
    def make_receipt(self, directory: Path, filename: str, payload: object) -> None:
        (directory / filename).write_text(json.dumps(payload), encoding="utf-8")

    def test_aggregate_runs_summarizes_completed_non_dry_run_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            runs_dir = Path(workspace)
            self.make_receipt(runs_dir, "run-completed-simple.json", {
                "run_id": "r1",
                "status": "succeeded",
                "events": [
                    {"kind": "triage_complete", "complexity": "simple"},
                    {"kind": "model_call", "cost_cents": 12},
                    {"kind": "model_call", "cost_cents": 8},
                ],
            })
            self.make_receipt(runs_dir, "run-completed-complex.json", {
                "run_id": "r2",
                "status": "failed_review",
                "events": [
                    {"kind": "triage_complete", "complexity": "complex"},
                    {"kind": "model_call", "cost_cents": 35},
                ],
            })
            self.make_receipt(runs_dir, "run-dry.json", {
                "run_id": "r3",
                "status": "planned",
                "message": "dry run: no implementation was invoked",
                "events": [
                    {"kind": "run_finished", "status": "planned", "message": "dry run: no implementation was invoked"},
                    {"kind": "model_call", "cost_cents": 1000},
                ],
            })

            summary = aggregate_runs(runs_dir)
            self.assertEqual(2, summary["completed_runs"])
            self.assertEqual({"complex": 1, "simple": 1}, summary["by_profile"])
            self.assertEqual({"succeeded": 1, "failed_review": 1}, summary["by_status"])
            self.assertEqual(55, summary["total_cost_cents"])
            self.assertEqual(0, summary["invalid_receipts"]["malformed_json"])

    def test_summary_skips_invalid_receipts_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            runs_dir = Path(workspace)
            (runs_dir / "malformed.json").write_text("{not-json}", encoding="utf-8")
            self.make_receipt(runs_dir, "missing-status.json", {
                "run_id": "r4",
                "events": [{"kind": "triage_complete", "complexity": "medium"}],
            })
            self.make_receipt(runs_dir, "valid.json", {
                "run_id": "r5",
                "status": "succeeded",
                "events": [
                    {"kind": "triage_complete", "complexity": "medium"},
                    {"kind": "model_call", "cost_cents": 77},
                ],
            })

            summary = aggregate_runs(runs_dir)
            self.assertEqual(1, summary["completed_runs"])
            self.assertEqual({"medium": 1}, summary["by_profile"])
            self.assertEqual(1, summary["invalid_receipts"]["malformed_json"])
            self.assertEqual(1, summary["invalid_receipts"]["invalid_structure"])
            self.assertEqual(77, summary["total_cost_cents"])

    @patch("router.__main__.print")
    def test_summary_cli_is_deterministic_without_task_or_workspace(self, mock_print) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            runs_dir = Path(workspace)
            self.make_receipt(runs_dir, "run-1.json", {
                "run_id": "r1",
                "status": "succeeded",
                "events": [
                    {"kind": "triage_complete", "complexity": "complex"},
                    {"kind": "model_call", "cost_cents": 5},
                ],
            })

            first = main(["--summary", "--runs-dir", str(runs_dir)])
            second = main(["--summary", "--runs-dir", str(runs_dir)])

            self.assertEqual(0, first)
            self.assertEqual(0, second)
            args1, _kwargs1 = mock_print.call_args_list[0]
            args2, _kwargs2 = mock_print.call_args_list[1]
            first_output = args1[0]
            second_output = args2[0]
            self.assertEqual(first_output, second_output)
            self.assertEqual(
                json.dumps({
                    "completed_runs": 1,
                    "total_cost_cents": 5,
                    "by_profile": {"complex": 1},
                    "by_status": {"succeeded": 1},
                    "invalid_receipts": {"invalid_structure": 0, "malformed_json": 0},
                }, ensure_ascii=False, sort_keys=True),
                first_output,
            )
            self.assertEqual(
                {"completed_runs": 1, "total_cost_cents": 5, "by_profile": {"complex": 1},
                 "by_status": {"succeeded": 1}, "invalid_receipts": {"invalid_structure": 0, "malformed_json": 0}},
                json.loads(first_output)
            )
