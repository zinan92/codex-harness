from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock
import unittest


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "src" / "jingle_accounting.py"
SPEC = importlib.util.spec_from_file_location("jingle_accounting", MODULE_PATH)
assert SPEC and SPEC.loader
accounting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(accounting)


def unit(provider: str, fixture: str) -> dict[str, object]:
    return {
        "provider": provider,
        "state": "done",
        "started_at": accounting.parse_timestamp("2026-07-29T10:01:00Z"),
        "ended_at": accounting.parse_timestamp("2026-07-29T10:06:00Z"),
        "transcript_path": str(ROOT / "tests" / "fixtures" / fixture),
    }


class JingleAccountingTests(unittest.TestCase):
    def test_codex_uses_cumulative_delta_not_a_sum_of_cumulative_records(self) -> None:
        result = accounting.collect_accounting(unit("codex", "codex-cumulative.jsonl"))
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["source"], "cumulative_delta")
        self.assertEqual(result["input_tokens"], 30)
        self.assertEqual(result["cached_input_tokens"], 20)
        self.assertIsNone(result["cache_write_input_tokens"])
        self.assertEqual(result["output_tokens"], 20)
        self.assertEqual(result["total_tokens"], 70)

    def test_codex_clamps_cached_input_before_fresh_input_math(self) -> None:
        snapshot = accounting.normalized_codex_snapshot(
            {"input_tokens": 7, "cached_input_tokens": 99, "output_tokens": 1}
        )
        self.assertEqual(snapshot["cached_input_tokens"], 7)
        self.assertEqual(snapshot["fresh_input_tokens"], 0)

    def test_claude_sums_window_deltas_once_per_message_id(self) -> None:
        result = accounting.collect_accounting(unit("claude", "claude-usage.jsonl"))
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["source"], "window_usage_sum")
        self.assertEqual(result["input_tokens"], 5)
        self.assertEqual(result["cached_input_tokens"], 17)
        self.assertEqual(result["cache_write_input_tokens"], 5)
        self.assertEqual(result["output_tokens"], 24)
        self.assertEqual(result["total_tokens"], 51)
        self.assertEqual(result["duplicate_usage_messages_suppressed"], 1)

    def test_running_or_missing_history_is_unavailable_without_token_values(self) -> None:
        running = unit("codex", "codex-cumulative.jsonl")
        running["state"] = "running"
        self.assertEqual(accounting.collect_accounting(running)["reason"], "work_unit_still_running")
        missing = unit("claude", "missing.jsonl")
        self.assertEqual(accounting.collect_accounting(missing)["reason"], "missing_transcript")

    def test_history_is_read_once_at_completion(self) -> None:
        history = ROOT / "tests" / "fixtures" / "codex-cumulative.jsonl"
        original_read_text = Path.read_text
        with mock.patch.object(
            Path, "read_text", autospec=True, side_effect=original_read_text
        ) as read_text:
            accounting.collect_accounting(unit("codex", "codex-cumulative.jsonl"))
        self.assertEqual(read_text.call_count, 1)
        self.assertEqual(read_text.call_args.args[0], history)


if __name__ == "__main__":
    unittest.main()
