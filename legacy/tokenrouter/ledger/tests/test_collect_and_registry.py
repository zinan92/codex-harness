import json
import tempfile
import unittest
from pathlib import Path

from ledger.collect import collect_codex
from ledger.registry import Project, UNCLASSIFIED, aggregate


class CodexCollectionTests(unittest.TestCase):
    def test_codex_file_uses_final_cumulative_usage_not_event_sum(self):
        """A later cumulative value replaces, rather than adds to, the prior one."""
        events = [
            {"type": "session_meta", "payload": {"cwd": "/fixture/project"}},
            {"type": "event_msg", "payload": {"info": {"total_token_usage": {
                "input_tokens": 100, "cached_input_tokens": 70, "output_tokens": 5,
            }}}},
            {"type": "event_msg", "payload": {"info": {"total_token_usage": {
                "input_tokens": 240, "cached_input_tokens": 180, "output_tokens": 9,
            }}}},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "session.jsonl"
            path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
            collected = collect_codex((Path(temporary),))
        self.assertEqual(collected["files"], 1)
        record = collected["records"][0]
        self.assertEqual(record["source_key"], "/fixture/project")
        self.assertEqual(record["input_tokens"], 60)
        self.assertEqual(record["cached_input_tokens"], 180)
        self.assertEqual(record["output_tokens"], 9)


class RegistryTests(unittest.TestCase):
    def test_longest_prefix_assigns_once_and_conserves_all_cents(self):
        projects = (
            Project("broad", codex_prefixes=("/work",)),
            Project("specific", codex_prefixes=("/work/specific",)),
        )
        records = [
            {"channel": "codex", "source_key": "/work/other", "cost_cents": 13},
            {"channel": "codex", "source_key": "/work/specific/task", "cost_cents": 29},
            {"channel": "claude", "source_key": "no-match", "cost_cents": 7},
        ]
        rows, grand_total = aggregate(records, projects)
        by_name = {row["name"]: row for row in rows}
        self.assertEqual(grand_total, 49)
        self.assertEqual(sum(row["cost_cents"] for row in rows), grand_total)
        self.assertEqual(by_name["broad"]["cost_cents"], 13)
        self.assertEqual(by_name["specific"]["cost_cents"], 29)
        self.assertEqual(by_name[UNCLASSIFIED]["cost_cents"], 7)

    def test_unclassified_bucket_catches_unknown_source(self):
        projects = (Project("known", codex_prefixes=("/known",)),)
        records = [{"channel": "codex", "source_key": "/unknown", "cost_cents": 91}]
        rows, grand_total = aggregate(records, projects)
        unclassified = next(row for row in rows if row["name"] == UNCLASSIFIED)
        self.assertEqual(unclassified["cost_cents"], 91)
        self.assertEqual(unclassified["records"], 1)
        self.assertEqual(grand_total, 91)

    def test_archived_flag_flows_through_but_still_counts_toward_total(self):
        projects = (
            Project("quiet", codex_prefixes=("/quiet",), archived=True, archive_reason="长期停摆"),
            Project("active", codex_prefixes=("/active",), archived=False),
        )
        records = [
            {"channel": "codex", "source_key": "/quiet/task", "cost_cents": 4},
            {"channel": "codex", "source_key": "/active/task", "cost_cents": 500},
        ]
        rows, grand_total = aggregate(records, projects)
        by_name = {row["name"]: row for row in rows}
        self.assertTrue(by_name["quiet"]["archived"])
        self.assertEqual(by_name["quiet"]["archive_reason"], "长期停摆")
        self.assertFalse(by_name["active"]["archived"])
        self.assertEqual(by_name["active"]["archive_reason"], "")
        self.assertFalse(by_name[UNCLASSIFIED]["archived"])
        self.assertEqual(grand_total, 504)
        self.assertEqual(sum(row["cost_cents"] for row in rows), grand_total)

    def test_archive_reason_distinguishes_idle_from_not_a_product(self):
        """A high-spend project can still be archived for being 'not a product'."""
        projects = (
            Project("workspace", codex_prefixes=("/ws",), archived=True, archive_reason="非产品·内部工具"),
        )
        records = [{"channel": "codex", "source_key": "/ws/task", "cost_cents": 411200}]
        rows, _ = aggregate(records, projects)
        row = next(r for r in rows if r["name"] == "workspace")
        self.assertTrue(row["archived"])
        self.assertEqual(row["archive_reason"], "非产品·内部工具")
        self.assertEqual(row["cost_cents"], 411200)
