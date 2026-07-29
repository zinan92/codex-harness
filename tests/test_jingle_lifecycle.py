from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
LIFECYCLE_PATH = ROOT / "src" / "jingle_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("jingle_lifecycle", LIFECYCLE_PATH)
assert SPEC and SPEC.loader
lifecycle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lifecycle
SPEC.loader.exec_module(lifecycle)


def classifier(message: str) -> tuple[str, str]:
    return ("attention", "needs_input") if "need input" in message else ("success", "normal")


class JingleLifecycleTests(unittest.TestCase):
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

    def payload(self, event: str, **extra: object) -> dict[str, object]:
        return {
            "hook_event_name": event,
            "session_id": "session-1",
            "turn_id": "turn-1",
            "cwd": "/tmp/project-a",
            **extra,
        }

    def test_codex_main_task_flows_running_then_done_without_tokens(self) -> None:
        started = lifecycle.begin_work_unit(
            "codex",
            self.payload("UserPromptSubmit", terminal_app="Terminal", terminal_tty="/dev/ttys014", parent_pid=431),
        )
        self.assertEqual(started["status"], lifecycle.STATE_RUNNING)
        self.assertNotIn("token", started["unit"])
        self.assertEqual(
            started["unit"]["session_locator"],
            {"terminal_app": "Terminal", "terminal_tty": "/dev/ttys014", "parent_pid": 431},
        )
        ended = lifecycle.finish_work_unit(
            "codex", self.payload("Stop", last_assistant_message="Completed."), classifier
        )
        self.assertEqual(ended["status"], lifecycle.STATE_DONE)
        self.assertEqual(ended["unit"]["outcome_reason"], "fallback_normal")

    def test_message_fallback_marks_waiting_for_input_blocked(self) -> None:
        lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit"))
        ended = lifecycle.finish_work_unit(
            "codex", self.payload("Stop", last_assistant_message="I need input."), classifier
        )
        self.assertEqual(ended["status"], lifecycle.STATE_BLOCKED)
        self.assertEqual(ended["unit"]["outcome_reason"], "fallback_needs_input")

    def test_claude_stop_failure_is_blocked_without_message_classification(self) -> None:
        lifecycle.begin_work_unit("claude", self.payload("UserPromptSubmit"))
        ended = lifecycle.finish_work_unit(
            "claude", self.payload("StopFailure", error="rate_limit"), classifier
        )
        self.assertEqual(ended["status"], lifecycle.STATE_BLOCKED)
        self.assertEqual(ended["unit"]["outcome_reason"], "claude_stop_failure")

    def test_claude_uses_active_session_unit_when_hook_has_no_turn_id(self) -> None:
        start = self.payload("UserPromptSubmit")
        start.pop("turn_id")
        started = lifecycle.begin_work_unit("claude", start)
        end = self.payload("Stop", last_assistant_message="Completed.")
        end.pop("turn_id")
        ended = lifecycle.finish_work_unit("claude", end, classifier)
        self.assertEqual(ended["unit"]["id"], started["unit"]["id"])

    def test_subagent_events_never_create_or_finish_a_unit(self) -> None:
        child = self.payload("UserPromptSubmit", agent_id="agent-child", agent_type="explorer")
        self.assertEqual(lifecycle.begin_work_unit("claude", child)["status"], "ignored_subagent")
        self.assertEqual(
            lifecycle.finish_work_unit("claude", self.payload("SubagentStop", agent_id="child"), classifier)["status"],
            "ignored_subagent",
        )
        self.assertEqual(lifecycle.load_state()["units"], {})

    def test_duplicate_end_is_suppressed(self) -> None:
        lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit"))
        lifecycle.finish_work_unit("codex", self.payload("Stop", last_assistant_message="Completed."), classifier)
        duplicate = lifecycle.finish_work_unit("codex", self.payload("Stop", last_assistant_message="Completed."), classifier)
        self.assertEqual(duplicate["status"], "duplicate_finish")

    def test_acknowledge_hides_completed_unit_without_deleting_its_ledger(self) -> None:
        started = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit"))
        lifecycle.finish_work_unit(
            "codex", self.payload("Stop", last_assistant_message="Completed."), classifier
        )
        acknowledged = lifecycle.acknowledge_unit(started["unit"]["id"])
        self.assertEqual(acknowledged["status"], "acknowledged")
        unit = lifecycle.load_state()["units"][started["unit"]["id"]]
        self.assertIn("seen_at", unit)
        self.assertEqual(unit["state"], lifecycle.STATE_DONE)

    def test_snooze_only_applies_to_blocked_units_and_uses_bounded_duration(self) -> None:
        started = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit"))
        lifecycle.finish_work_unit(
            "codex", self.payload("Stop", last_assistant_message="I need input."), classifier
        )
        snoozed = lifecycle.snooze_unit(started["unit"]["id"], 600)
        self.assertEqual(snoozed["status"], "snoozed")
        self.assertGreater(snoozed["unit"]["snoozed_until"], snoozed["unit"]["ended_at"])
        self.assertEqual(lifecycle.snooze_unit(started["unit"]["id"], 0)["status"], "snoozed")

    def test_state_and_event_log_are_private_and_do_not_store_messages(self) -> None:
        secret = "never-write-this-assistant-message"
        lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", prompt="never-write-this-prompt"))
        lifecycle.finish_work_unit("codex", self.payload("Stop", last_assistant_message=secret), classifier)
        state_file = Path(self.environ["JINGLE_STATE_PATH"])
        log_file = Path(self.environ["JINGLE_EVENT_LOG_PATH"])
        self.assertEqual(stat.S_IMODE(state_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(log_file.stat().st_mode), 0o600)
        self.assertNotIn(secret, state_file.read_text(encoding="utf-8"))
        self.assertNotIn(secret, log_file.read_text(encoding="utf-8"))

    def test_locator_capture_keeps_only_identity_metadata(self) -> None:
        locator = lifecycle.capture_session_locator(
            {
                "terminal_app": "Terminal",
                "terminal_tty": "/dev/ttys999",
                "terminal_session_id": "ABC",
                "parent_pid": 99,
                "prompt": "do not retain this",
            }
        )
        self.assertEqual(locator["terminal_tty"], "/dev/ttys999")
        self.assertNotIn("prompt", locator)

    def test_cli_emits_a_machine_readable_result_for_a_hook_fixture(self) -> None:
        payload = self.payload("UserPromptSubmit")
        completed = subprocess.run(
            [sys.executable, str(ROOT / "src" / "jingle_hook.py"), "--provider", "codex", "--print-result"],
            input=json.dumps(payload), text=True, capture_output=True, check=False,
            env={**os.environ, **self.environ},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], lifecycle.STATE_RUNNING)

        child = self.payload("SubagentStop", agent_id="agent-child", agent_type="explorer")
        completed = subprocess.run(
            [sys.executable, str(ROOT / "src" / "jingle_hook.py"), "--provider", "claude", "--print-result"],
            input=json.dumps(child), text=True, capture_output=True, check=False,
            env={**os.environ, **self.environ},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "ignored_subagent")


if __name__ == "__main__":
    unittest.main()
