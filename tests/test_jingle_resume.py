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


LOCATOR = {"terminal_app": "Terminal", "terminal_tty": "/dev/ttys014", "parent_pid": 431}


class ResumeTests(unittest.TestCase):
    def test_exact_terminal_tty_is_the_only_focus_match(self) -> None:
        with mock.patch.object(resume, "run_osascript_text", return_value="focused:/dev/ttys014") as script:
            self.assertTrue(resume.focus_terminal_locator(LOCATOR))
        source = script.call_args.args[0]
        self.assertIn('tty of terminalTab is "/dev/ttys014"', source)
        self.assertNotIn("project", source.casefold())

    def test_matching_osascript_exit_without_the_original_tty_is_not_success(self) -> None:
        with mock.patch.object(resume, "run_osascript_text", return_value="focused:/dev/ttys015"):
            self.assertFalse(resume.focus_claude_terminal("session-a", "/same/cwd", LOCATOR))

    def test_two_claude_sessions_with_one_cwd_fail_instead_of_creating_a_fallback(self) -> None:
        with mock.patch.object(resume, "focus_terminal_locator", return_value=False) as focus:
            result = resume.route("claude", "session-a", "/same/cwd", LOCATOR)
        focus.assert_called_once_with(LOCATOR, mock.ANY)
        self.assertEqual(result["status"], "failed")
        self.assertIn("未打开任何新项目或会话", result["message"])

    def test_codex_focuses_exact_terminal_or_fails_without_opening_a_project(self) -> None:
        with mock.patch.object(resume, "focus_terminal_locator", return_value=True):
            focused = resume.route("codex", "session-1", "/tmp/project", LOCATOR)
        self.assertEqual(focused["status"], "codex_focused")

        with mock.patch.object(resume, "focus_terminal_locator", return_value=False):
            fallback = resume.route("codex", "session-1", "/tmp/project", LOCATOR)
        self.assertEqual(fallback["status"], "failed")
        self.assertIn("未打开任何新项目或会话", fallback["message"])

    def test_route_has_no_command_that_creates_or_resumes_a_session(self) -> None:
        source = (ROOT / "src" / "jingle_resume.py").read_text(encoding="utf-8")
        self.assertNotIn('"open"', source)
        self.assertNotIn('"pbcopy"', source)
        self.assertNotIn("codex resume", source)
        self.assertNotIn("claude --resume", source)

    def test_malformed_locator_degrades_to_an_empty_object(self) -> None:
        self.assertEqual(resume.parse_locator("not-json"), {})
        self.assertEqual(resume.parse_locator("[]"), {})

    def test_missing_identity_is_visible_failure(self) -> None:
        self.assertEqual(resume.route("claude", "", "/tmp/project")["status"], "failed")


if __name__ == "__main__":
    unittest.main()
