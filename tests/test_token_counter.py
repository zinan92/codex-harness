from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("token_counter", ROOT / "src" / "token_counter.py")
assert SPEC and SPEC.loader
counter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(counter)


def line(timestamp: str, record_type: str, payload: dict[str, object]) -> str:
    return json.dumps({"timestamp": timestamp, "type": record_type, "payload": payload})


class TokenCounterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.sessions = self.root / "sessions"
        self.sessions.mkdir()
        self.projects = [{"project_id": "root", "name": "Root", "aliases": [{"prefix": "/work"}]}, {"project_id": "nested", "name": "Nested", "aliases": [{"prefix": "/work/nested"}]}]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, name: str, rows: list[str]) -> None:
        (self.sessions / name).write_text("\n".join(rows), encoding="utf-8")

    def test_cumulative_snapshots_are_deduplicated_per_thread_and_allocated_by_snapshot_day(self) -> None:
        self.write("one.jsonl", [
            line("2026-08-01T15:59:00Z", "session_meta", {"id": "thread-1", "cwd": "/work/nested"}),
            line("2026-08-01T15:59:30Z", "event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 10}}}),
            line("2026-08-01T15:59:30Z", "event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 10}}}),
            line("2026-08-01T16:01:00Z", "event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 150, "cached_input_tokens": 70, "output_tokens": 30}}}),
        ])
        rows = counter.extract_threads(counter.session_files((self.sessions,)), self.projects)
        row = rows["thread-1"]
        self.assertEqual(row["project"]["project_id"], "nested")
        self.assertEqual(row["total_tokens"], 180)
        self.assertEqual(row["daily"]["2026-08-01"]["total_tokens"], 110)
        self.assertEqual(row["daily"]["2026-08-02"]["total_tokens"], 70)

    def test_multiple_session_meta_records_in_one_file_create_distinct_threads(self) -> None:
        self.write("multiple.jsonl", [
            line("2026-08-01T10:00:00Z", "session_meta", {"id": "one", "cwd": "/work"}),
            line("2026-08-01T10:01:00Z", "event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 4, "cached_input_tokens": 1, "output_tokens": 2}}}),
            line("2026-08-01T10:02:00Z", "session_meta", {"id": "two", "cwd": "/outside"}),
            line("2026-08-01T10:03:00Z", "event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 7, "cached_input_tokens": 2, "output_tokens": 3}}}),
        ])
        rows = counter.extract_threads(counter.session_files((self.sessions,)), self.projects)
        self.assertEqual(rows["one"]["total_tokens"], 6)
        self.assertEqual(rows["two"]["project"]["project_id"], "uncategorized")

    def test_unavailable_and_project_attribution_are_honest_and_frozen(self) -> None:
        self.write("missing.jsonl", [line("2026-08-01T10:00:00Z", "session_meta", {"id": "missing", "cwd": "/work"})])
        rows = counter.extract_threads(counter.session_files((self.sessions,)), self.projects)
        self.assertEqual(rows["missing"]["status"], "unavailable")
        old = {"threads": {"missing": {"project": {"project_id": "historic", "name": "Historic", "source": "cwd_prefix"}}}}
        counter.freeze_attribution(rows, old)
        self.assertEqual(rows["missing"]["project"]["project_id"], "historic")

    def test_scanner_skips_prompt_bodies_without_parsing_them(self) -> None:
        self.write("privacy.jsonl", [
            '{"timestamp":"2026-08-01T10:00:00Z","type":"response_item","payload":not-json}',
            line("2026-08-01T10:01:00Z", "session_meta", {"id": "safe", "cwd": "/work"}),
        ])
        rows = counter.extract_threads(counter.session_files((self.sessions,)), self.projects)
        self.assertEqual(rows["safe"]["status"], "unavailable")

    def test_cumulative_reset_starts_a_new_auditable_epoch(self) -> None:
        self.write("reset.jsonl", [
            line("2026-08-01T10:00:00Z", "session_meta", {"id": "reset", "cwd": "/work"}),
            line("2026-08-01T10:01:00Z", "event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 20, "cached_input_tokens": 5, "output_tokens": 3}}}),
            line("2026-08-01T10:02:00Z", "event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 4, "cached_input_tokens": 1, "output_tokens": 2}}}),
        ])
        row = counter.extract_threads(counter.session_files((self.sessions,)), self.projects)["reset"]
        self.assertEqual(row["cumulative_reset_count"], 1)
        self.assertEqual(row["total_tokens"], 29)

    def test_summary_counts_threads_once(self) -> None:
        state = {"threads": {"a": {"status": "available", "fresh_input_tokens": 1, "cached_input_tokens": 2, "output_tokens": 3, "reasoning_output_tokens": 0, "total_tokens": 6, "daily": {"2026-08-01": {"total_tokens": 6}}}, "b": {"status": "unavailable"}}}
        self.assertEqual(counter.summary(state), {"threads": 2, "available_threads": 1, "reporting_timezone": "Asia/Shanghai", "tokens": {"fresh_input_tokens": 1, "cached_input_tokens": 2, "output_tokens": 3, "reasoning_output_tokens": 0, "total_tokens": 6}, "daily_total_tokens": {"2026-08-01": 6}})


if __name__ == "__main__":
    unittest.main()
