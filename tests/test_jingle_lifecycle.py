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
from unittest import mock


ROOT = Path(__file__).parents[1]
LIFECYCLE_PATH = ROOT / "src" / "jingle_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("jingle_lifecycle", LIFECYCLE_PATH)
assert SPEC and SPEC.loader
lifecycle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lifecycle
SPEC.loader.exec_module(lifecycle)
sys.path.insert(0, str(ROOT / "src"))
import jingle_workflow  # noqa: E402
import codex_spoken_notify  # noqa: E402


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
            "JINGLE_PROJECTS_PATH": str(root / "projects.json"),
        }
        self.previous = {key: os.environ.get(key) for key in self.environ}
        Path(self.environ["JINGLE_PROJECTS_PATH"]).write_text(
            json.dumps({"projects": [{"project_id": "interactive", "aliases": [{"prefix": "/tmp/project-a"}]}]}),
            encoding="utf-8",
        )
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
        self.assertTrue(ended["unit"]["needs_attention"])
        self.assertTrue(ended["delivery_eligible"])

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

    def test_claude_session_end_reconciles_an_unfinished_unit_as_blocked(self) -> None:
        lifecycle.begin_work_unit("claude", self.payload("UserPromptSubmit"))
        ended = lifecycle.finish_work_unit("claude", self.payload("SessionEnd"), classifier)
        self.assertEqual(ended["status"], lifecycle.STATE_BLOCKED)
        self.assertEqual(ended["unit"]["outcome_reason"], "claude_session_end")
        self.assertTrue(ended["delivery_eligible"])

    def test_session_end_after_normal_claude_stop_is_ignored(self) -> None:
        lifecycle.begin_work_unit("claude", self.payload("UserPromptSubmit"))
        lifecycle.finish_work_unit("claude", self.payload("Stop", last_assistant_message="Completed."), classifier)
        ignored = lifecycle.finish_work_unit("claude", self.payload("SessionEnd"), classifier)
        self.assertEqual(ignored["status"], "ignored_missing_start")

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

    def test_next_start_supersedes_unseen_terminal_item_but_keeps_ledger_row(self) -> None:
        first = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="turn-1"))
        lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="turn-1", last_assistant_message="Completed."), classifier)
        second = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="turn-2"))
        units = lifecycle.load_state()["units"]
        self.assertEqual(len(units), 2)
        self.assertIn("superseded_at", units[first["unit"]["id"]])
        self.assertNotIn("superseded_at", units[second["unit"]["id"]])

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

    def test_quarantine_historical_unmapped_done_preserves_mapped_and_blocked_ledger_rows(self) -> None:
        mapped = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="mapped"))["unit"]
        lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="mapped", last_assistant_message="Completed."), classifier)
        legacy = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="legacy", cwd="/tmp/old-noise"))["unit"]
        lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="legacy", cwd="/tmp/old-noise", last_assistant_message="Completed."), classifier)
        blocked = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="blocked", cwd="/tmp/old-noise"))["unit"]
        lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="blocked", cwd="/tmp/old-noise", last_assistant_message="I need input."), classifier)

        state = lifecycle.load_state()
        state["units"][legacy["id"]].update({"notification_policy": "task_terminal", "attention_suppressed": False, "needs_attention": True})
        state["units"][legacy["id"]]["cwd"] = "/"
        mapped_before = dict(state["units"][mapped["id"]])
        blocked_before = dict(state["units"][blocked["id"]])
        lifecycle.save_state(state)

        result = lifecycle.quarantine_historical_completion_noise()
        self.assertEqual(result["status"], "quarantined_historical_completions")
        self.assertEqual(result["count"], 1)
        updated = lifecycle.load_state()["units"]
        self.assertTrue(updated[legacy["id"]]["attention_suppressed"])
        self.assertFalse(updated[legacy["id"]]["needs_attention"])
        self.assertEqual(updated[legacy["id"]]["attention_suppressed_reason"], "unmapped_completion_quarantine")
        self.assertEqual(updated[mapped["id"]], mapped_before)
        self.assertEqual(updated[blocked["id"]], blocked_before)
        self.assertEqual(lifecycle.quarantine_historical_completion_noise()["count"], 0)

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

    def test_workflow_suppresses_internal_done_until_explicit_finish(self) -> None:
        self.assertEqual(lifecycle.start_workflow("codex", "session-1", "/tmp/project-a")["status"], "workflow_started")
        first = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="one"))
        first_done = lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="one", last_assistant_message="Completed."), classifier)
        self.assertTrue(first_done["unit"]["attention_suppressed"])
        second = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="two"))
        second_done = lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="two", last_assistant_message="Completed."), classifier)
        self.assertTrue(second_done["unit"]["attention_suppressed"])
        terminal = lifecycle.finish_workflow("codex", "session-1")
        self.assertEqual(terminal["status"], lifecycle.STATE_DONE)
        self.assertEqual(terminal["unit"]["id"], second["unit"]["id"])
        self.assertFalse(terminal["unit"]["attention_suppressed"])
        self.assertFalse(terminal["unit"]["needs_attention"])
        self.assertIn(first["unit"]["id"], lifecycle.load_state()["units"])

    def test_explicit_workflow_blocked_marker_delivers_once_without_prompt_text(self) -> None:
        lifecycle.start_workflow("codex", "session-1", "/tmp/project-a")
        started = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="waiting"))
        lifecycle.finish_work_unit(
            "codex", self.payload("Stop", turn_id="waiting", last_assistant_message="Completed internal step."), classifier
        )
        terminal = lifecycle.finish_workflow("codex", "session-1", lifecycle.STATE_BLOCKED)
        with mock.patch.object(jingle_workflow, "launch_worker") as notify:
            jingle_workflow.deliver_blocked_workflow(terminal)
            jingle_workflow.deliver_blocked_workflow({**terminal, "status": lifecycle.STATE_DONE})
        notify.assert_called_once_with(
            started["unit"]["turn_id"],
            "session-1",
            "project-a：workflow 需要决定",
            "jingle_workflow",
            codex_spoken_notify.STATUS_ATTENTION,
        )

    def test_blocked_only_suppresses_done_but_not_blocked(self) -> None:
        done_start = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="done", notification_policy="blocked_only"))
        done = lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="done", last_assistant_message="Completed."), classifier)
        self.assertTrue(done["unit"]["attention_suppressed"])
        self.assertFalse(done["unit"]["needs_attention"])
        self.assertFalse(done["delivery_eligible"])
        blocked_start = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="blocked", notification_policy="blocked_only"))
        blocked = lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="blocked", last_assistant_message="I need input."), classifier)
        self.assertFalse(blocked["unit"]["attention_suppressed"])
        self.assertTrue(blocked["unit"]["needs_attention"])
        self.assertTrue(blocked["delivery_eligible"])
        self.assertIn(done_start["unit"]["id"], lifecycle.load_state()["units"])
        self.assertIn(blocked_start["unit"]["id"], lifecycle.load_state()["units"])

    def test_project_policy_whitelist_defaults_mapped_to_task_terminal_and_unmapped_to_blocked_only(self) -> None:
        projects = Path(self.temporary.name) / "projects.json"
        projects.write_text(json.dumps({"projects": [
            {"project_id": "interactive", "aliases": [{"provider": "claude", "prefix": "/tmp/project-a"}]},
            {"project_id": "quiet", "notification_policy": "blocked_only", "aliases": [{"provider": "codex", "prefix": "/tmp/quiet"}]},
        ]}), encoding="utf-8")
        previous = os.environ.get("JINGLE_PROJECTS_PATH")
        os.environ["JINGLE_PROJECTS_PATH"] = str(projects)
        try:
            self.assertEqual(lifecycle.notification_policy({"cwd": "/tmp/project-a"}, "claude"), "task_terminal")
            self.assertEqual(lifecycle.notification_policy({"cwd": "/tmp/quiet"}, "codex"), "blocked_only")
            self.assertEqual(lifecycle.notification_policy({"cwd": "/tmp/unmapped"}, "codex"), "blocked_only")
        finally:
            if previous is None: os.environ.pop("JINGLE_PROJECTS_PATH", None)
            else: os.environ["JINGLE_PROJECTS_PATH"] = previous

    def test_unmapped_done_is_ledger_only_but_unmapped_blocked_still_delivers(self) -> None:
        done_start = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="unmapped-done", cwd="/tmp/park-intel"))
        done = lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="unmapped-done", cwd="/tmp/park-intel", last_assistant_message="Completed."), classifier)
        blocked_start = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id="unmapped-blocked", cwd="/tmp/park-intel"))
        blocked = lifecycle.finish_work_unit("codex", self.payload("Stop", turn_id="unmapped-blocked", cwd="/tmp/park-intel", last_assistant_message="I need input."), classifier)
        self.assertEqual(done_start["unit"]["notification_policy"], lifecycle.POLICY_BLOCKED_ONLY)
        self.assertTrue(done["unit"]["attention_suppressed"])
        self.assertFalse(done["delivery_eligible"])
        self.assertTrue(blocked_start["unit"]["notification_policy"] == lifecycle.POLICY_BLOCKED_ONLY)
        self.assertFalse(blocked["unit"]["attention_suppressed"])
        self.assertTrue(blocked["delivery_eligible"])

    def test_empty_and_root_cwds_never_create_visible_work_units(self) -> None:
        for index, cwd in enumerate(("", "/")):
            result = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", turn_id=f"invalid-{index}", cwd=cwd))
            self.assertEqual(result["status"], "ignored_invalid_cwd")
        self.assertEqual(lifecycle.load_state()["units"], {})

    def test_legacy_invalid_cwd_is_forced_ledger_only_when_finished(self) -> None:
        started = lifecycle.begin_work_unit("codex", self.payload("UserPromptSubmit", cwd="/tmp/project-a"))
        state = lifecycle.load_state()
        state["units"][started["unit"]["id"]]["cwd"] = "/"
        lifecycle.save_state(state)
        ended = lifecycle.finish_work_unit("codex", self.payload("Stop", cwd="/", last_assistant_message="I need input."), classifier)
        self.assertTrue(ended["unit"]["attention_suppressed"])
        self.assertFalse(ended["unit"]["needs_attention"])
        self.assertFalse(ended["delivery_eligible"])

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
        self.assertEqual(json.loads(completed.stdout)["status"], "ignored_provider")


if __name__ == "__main__":
    unittest.main()
