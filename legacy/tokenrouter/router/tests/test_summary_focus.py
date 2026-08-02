from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from router.summary import aggregate_runs


class SummaryFocusTests(unittest.TestCase):
    def make_receipt(self, directory: Path, filename: str, payload: object) -> None:
        (directory / filename).write_text(json.dumps(payload), encoding="utf-8")

    def test_summary_aggregates_normal_completed_runs(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            runs_dir = Path(workspace)
            self.make_receipt(
                runs_dir,
                "run-success.json",
                {
                    "run_id": "r1",
                    "status": "succeeded",
                    "events": [
                        {"kind": "triage_complete", "complexity": "complex"},
                        {"kind": "model_call", "cost_cents": 11},
                        {"kind": "model_call", "cost_cents": 4},
                    ],
                },
            )
            self.make_receipt(
                runs_dir,
                "run-failed.json",
                {
                    "run_id": "r2",
                    "profile": "simple",
                    "status": "failed_review",
                    "events": [{"kind": "model_call", "cost_cents": 22}],
                },
            )
            self.make_receipt(
                runs_dir,
                "run-running.json",
                {
                    "run_id": "r3",
                    "status": "running",
                    "events": [
                        {"kind": "triage_complete", "complexity": "complex"},
                        {"kind": "model_call", "cost_cents": 99},
                    ],
                },
            )

            summary = aggregate_runs(runs_dir)
            self.assertEqual(2, summary["completed_runs"])
            self.assertEqual({"complex": 1, "simple": 1}, summary["by_profile"])
            self.assertEqual({"failed_review": 1, "succeeded": 1}, summary["by_status"])
            self.assertEqual(37, summary["total_cost_cents"])
            self.assertEqual(0, summary["invalid_receipts"]["malformed_json"])
            self.assertEqual(0, summary["invalid_receipts"]["invalid_structure"])

    def test_summary_skips_malformed_and_invalid_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            runs_dir = Path(workspace)
            (runs_dir / "malformed.json").write_text("{", encoding="utf-8")
            (runs_dir / "empty.json").write_text("", encoding="utf-8")
            (runs_dir / "invalid-structure.json").write_text("[]", encoding="utf-8")
            self.make_receipt(
                runs_dir,
                "invalid-status.json",
                {"run_id": "r5", "events": [{"kind": "triage_complete", "complexity": "simple"}]},
            )
            self.make_receipt(
                runs_dir,
                "valid.json",
                {
                    "run_id": "r6",
                    "status": "failed",
                    "events": [
                        {"kind": "triage_complete", "complexity": "simple"},
                        {"kind": "model_call", "cost_cents": 15},
                    ],
                },
            )

            summary = aggregate_runs(runs_dir)
            self.assertEqual(1, summary["completed_runs"])
            self.assertEqual({"simple": 1}, summary["by_profile"])
            self.assertEqual({"failed": 1}, summary["by_status"])
            self.assertEqual(2, summary["invalid_receipts"]["malformed_json"])
            self.assertEqual(2, summary["invalid_receipts"]["invalid_structure"])
            self.assertEqual(15, summary["total_cost_cents"])

    def test_summary_excludes_dry_run_runs_from_counts_and_cost(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            runs_dir = Path(workspace)
            self.make_receipt(
                runs_dir,
                "run-dry-run.json",
                {
                    "run_id": "r1",
                    "status": "succeeded",
                    "message": "dry run complete",
                    "events": [
                        {"kind": "triage_complete", "complexity": "complex"},
                        {"kind": "model_call", "cost_cents": 99},
                    ],
                },
            )
            self.make_receipt(
                runs_dir,
                "run-live.json",
                {
                    "run_id": "r2",
                    "status": "succeeded",
                    "events": [
                        {"kind": "triage_complete", "complexity": "simple"},
                        {"kind": "model_call", "cost_cents": 13},
                    ],
                },
            )
            summary = aggregate_runs(runs_dir)
            self.assertEqual(1, summary["completed_runs"])
            self.assertEqual({"simple": 1}, summary["by_profile"])
            self.assertEqual({"succeeded": 1}, summary["by_status"])
            self.assertEqual(13, summary["total_cost_cents"])

    def test_summary_invalid_runs_dir_matches_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            runs_dir = Path(workspace)
            file_path = runs_dir / "not-a-directory.txt"
            file_path.write_text("{}", encoding="utf-8")

            expected = aggregate_runs(runs_dir)
            for runs_dir_path in (runs_dir / "does-not-exist", file_path):
                actual = aggregate_runs(runs_dir_path)
                self.assertEqual(expected, actual)

    def test_summary_invalid_runs_dir_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            runs_dir = Path(workspace)
            file_path = runs_dir / "not-a-directory.txt"
            file_path.write_text("{}", encoding="utf-8")

            first = aggregate_runs(file_path)
            second = aggregate_runs(file_path)
            self.assertEqual(first, second)
