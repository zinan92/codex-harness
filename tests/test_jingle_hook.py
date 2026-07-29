from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from unittest import mock
import unittest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
import jingle_hook  # noqa: E402
import jingle_summary  # noqa: E402


class JingleHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.environ = {
            "JINGLE_STATE_PATH": str(root / "work-units.json"),
            "JINGLE_LOCK_PATH": str(root / "work-units.lock"),
            "JINGLE_EVENT_LOG_PATH": str(root / "events.jsonl"),
        }
        self.previous = {key: os.environ.get(key) for key in self.environ}
        os.environ.update(self.environ)

    def tearDown(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temporary.cleanup()

    def test_accounting_is_called_once_only_after_a_finished_work_unit(self) -> None:
        start = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": "/tmp/project",
        }
        stop = {**start, "hook_event_name": "Stop", "last_assistant_message": "Completed."}
        expected = {"provider": "codex", "status": "unavailable", "reason": "missing_transcript"}
        with (
            mock.patch.object(jingle_hook, "collect_accounting", return_value=expected) as collect,
            mock.patch.object(jingle_summary, "launch") as launch,
        ):
            running = jingle_hook.handle("codex", start)
            self.assertEqual(running["status"], "running")
            self.assertNotIn("token_accounting", running["unit"])
            collect.assert_not_called()

            done = jingle_hook.handle("codex", stop)
            self.assertEqual(done["status"], "done")
            collect.assert_called_once()
            self.assertEqual(done["accounting"]["status"], "accounting_recorded")
            launch.assert_called_once()

            duplicate = jingle_hook.handle("codex", stop)
            self.assertEqual(duplicate["status"], "duplicate_finish")
            collect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
