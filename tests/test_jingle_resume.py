from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("jingle_resume", ROOT / "src" / "jingle_resume.py")
assert SPEC and SPEC.loader
resume = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = resume
SPEC.loader.exec_module(resume)


def completed(code: int = 0, output: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, output, "")


class ResumeTests(unittest.TestCase):
    def test_codex_uses_current_specified_session_entry(self) -> None:
        with mock.patch.object(resume.shutil, "which", return_value="/usr/local/bin/codex"), mock.patch.object(resume, "run_osascript", return_value=True) as script:
            result = resume.route("codex", "session-1", "/tmp/project one")
        self.assertEqual(result["status"], "codex_resumed")
        self.assertIn("codex resume session-1", script.call_args.args[0])

    def test_codex_falls_back_to_project_app_when_terminal_launch_fails(self) -> None:
        with mock.patch.object(resume.shutil, "which", return_value="/usr/local/bin/codex"), mock.patch.object(resume, "run_osascript", return_value=False):
            result = resume.route("codex", "session-1", "/tmp/project", run=lambda *args, **kwargs: completed())
        self.assertEqual(result["status"], "codex_app_opened")

    def test_claude_focus_failure_copies_exact_resume_command(self) -> None:
        with mock.patch.object(resume, "focus_claude_terminal", return_value=False), mock.patch.object(resume, "copy_claude_resume", return_value=True):
            result = resume.route("claude", "session-2", "/tmp/project")
        self.assertEqual(result["status"], "claude_resume_copied")
        self.assertIn("已复制", result["message"])

    def test_claude_fallback_copies_only_the_documented_resume_command(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            captured["args"] = args
            captured["input"] = kwargs.get("input")
            return completed()

        self.assertTrue(resume.copy_claude_resume("session-2", fake_run))
        self.assertEqual(captured["args"], (["pbcopy"],))
        self.assertEqual(captured["input"], "claude --resume session-2")

    def test_terminal_focus_requires_a_matching_window_not_merely_osascript_success(self) -> None:
        self.assertFalse(resume.focus_claude_terminal("session-3", "/tmp/project", lambda *args, **kwargs: completed(output="not-found")))

    def test_missing_identity_is_visible_failure(self) -> None:
        self.assertEqual(resume.route("claude", "", "/tmp/project")["status"], "failed")


if __name__ == "__main__":
    unittest.main()
