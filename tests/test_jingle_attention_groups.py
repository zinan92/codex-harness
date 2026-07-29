from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class AttentionGroupContractTests(unittest.TestCase):
    def test_replay_fixture_has_one_current_unit_per_session_and_three_project_groups(self) -> None:
        data = json.loads((ROOT / "tests/fixtures/jingle-attention-work-units.json").read_text(encoding="utf-8"))
        latest: dict[tuple[str, str], dict[str, object]] = {}
        for unit in data["units"].values():
            key = (unit["provider"], unit["session_id"])
            if unit["started_at"] > latest.get(key, {}).get("started_at", -1):
                latest[key] = unit
        self.assertEqual({unit["id"] for unit in latest.values()}, {"cl-current", "cx-current", "cl-blocked", "unmapped-one", "unmapped-two"})
        self.assertNotIn("cl-old", {unit["id"] for unit in latest.values()})
        projects = json.loads((ROOT / "tests/fixtures/jingle-attention-projects.json").read_text(encoding="utf-8"))["projects"]

        def project_id(unit: dict[str, object]) -> str:
            for project in projects:
                for alias in project["aliases"]:
                    if alias.get("provider") in {None, unit["provider"]} and str(unit["cwd"]).startswith(alias["prefix"]):
                        return project["project_id"]
            return f"unmapped:{unit['cwd']}"

        self.assertEqual({project_id(unit) for unit in latest.values()}, {"token-router", "unmapped:/workspace/a/shared", "unmapped:/workspace/b/shared"})

    def test_native_model_uses_explicit_group_identity_and_supersession(self) -> None:
        source = (ROOT / "src/CodexNotificationSettings.swift").read_text(encoding="utf-8")
        self.assertIn('case projectID = "project_id"', source)
        self.assertIn('"unmapped:\\(normalized)"', source)
        self.assertIn("currentBySession", source)
        self.assertIn("attentionGroups", source)
        self.assertIn('$0.state == "blocked"', source)
        self.assertNotIn('Text("做完了")', source)
        self.assertNotIn('Text("还在跑")', source)
        self.assertIn("panel.isOpaque = true", source)
        self.assertIn("panel.backgroundColor = .windowBackgroundColor", source)
        lifecycle = (ROOT / "src/jingle_lifecycle.py").read_text(encoding="utf-8")
        self.assertIn('existing["superseded_at"]', lifecycle)


if __name__ == "__main__":
    unittest.main()
