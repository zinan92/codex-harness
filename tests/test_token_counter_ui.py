from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("token_counter_ui", ROOT / "src" / "token_counter_ui.py")
assert SPEC and SPEC.loader
ui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ui)


class TokenCounterUiTests(unittest.TestCase):
    def state(self) -> dict[str, object]:
        return {"generated_at": "2026-08-02T10:00:00+00:00", "reporting_timezone": "Asia/Shanghai", "threads": {
            "one": {"thread_id": "one-secret", "project": {"project_id": "research", "name": "Research"}, "status": "available", "total_tokens": 1500, "ended_at": 1785664800, "daily": {"2026-08-01": {"total_tokens": 1500}}, "activity_label": "must never render raw task content"},
            "two": {"thread_id": "two-secret", "project": {"project_id": "uncategorized", "name": "Uncategorized"}, "status": "unavailable", "daily": {}},
        }}

    def test_projection_contains_accounting_without_activity_content(self) -> None:
        html = ui.render(self.state(), Path("/private/threads.json"))
        self.assertIn("Thread ledger", html)
        self.assertIn("CODEX HARNESS / LOCAL ONLY", html)
        self.assertIn("Research", html)
        self.assertIn("1.5K", html)
        self.assertIn("Uncategorized", html)
        self.assertNotIn("must never render raw task content", html)
        self.assertNotIn("/private/threads.json", html)

    def test_missing_state_has_an_explicit_safe_empty_state(self) -> None:
        html = ui.render(None, Path("/private/threads.json"))
        self.assertIn("No ledger found.", html)
        self.assertIn("/private/threads.json", html)


if __name__ == "__main__":
    unittest.main()
