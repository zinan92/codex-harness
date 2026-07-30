from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
import jingle_codex_activity as activity  # noqa: E402


class CodexActivityTests(unittest.TestCase):
    def test_reads_liveness_fields_and_safe_session_index_name_without_raw_title(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "state.sqlite"
            index = root / "session_index.jsonl"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, updated_at INTEGER, archived INTEGER, cwd TEXT)"
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?)",
                ("active", "do not expose this raw prompt", 200, 0, "/tmp/trading"),
            )
            connection.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?)",
                ("archived", "also private", 100, 1, "/tmp/archive"),
            )
            connection.commit()
            connection.close()
            index.write_text(
                "\n".join((
                    json.dumps({"id": "active", "thread_name": "交易系统"}, ensure_ascii=False),
                    json.dumps({"id": "archived", "thread_name": "first"}, ensure_ascii=False),
                    json.dumps({"id": "archived", "thread_name": "最后名称"}, ensure_ascii=False),
                )),
                encoding="utf-8",
            )

            result = activity.read_activity(["active", "archived", "missing"], (database,), index)

        self.assertEqual(result["active"], {
            "updated_at": 200.0,
            "archived": False,
            "cwd": "/tmp/trading",
            "display_name": "交易系统",
        })
        self.assertTrue(result["archived"]["archived"])
        self.assertEqual(result["archived"]["display_name"], "最后名称")
        self.assertNotIn("missing", result)
        self.assertNotIn("title", result["active"])

    def test_rejects_multiline_or_oversized_session_index_names(self) -> None:
        self.assertEqual(activity.safe_session_name("短名称"), "短名称")
        self.assertEqual(activity.safe_session_name("one\ntwo"), "")
        self.assertEqual(activity.safe_session_name("x" * 49), "")


if __name__ == "__main__":
    unittest.main()
