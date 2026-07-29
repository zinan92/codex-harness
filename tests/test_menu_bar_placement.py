from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


class MenuBarPlacementTests(unittest.TestCase):
    def test_call_and_settlement_use_the_shared_screen_clamped_panel(self) -> None:
        root = Path(__file__).parents[1]
        source = (root / "src" / "CodexNotificationSettings.swift").read_text(encoding="utf-8")
        self.assertNotIn("NSPopover", source)
        self.assertIn("present(.call(first))", source)
        self.assertIn("present(.settlement)", source)
        self.assertIn("JinglePanelLayout.frame", source)
        self.assertIn("if present(.call(first)) { calledUnitIDs.insert(first.id) }", source)
        self.assertIn("NSWorkspace.didActivateApplicationNotification", source)

    def test_panel_geometry_fixtures_are_executable(self) -> None:
        root = Path(__file__).parents[1]
        binary = Path("/tmp/jingle-panel-layout-tests")
        subprocess.run(
            ["swiftc", str(root / "src" / "JinglePanelLayout.swift"), str(root / "tests" / "JinglePanelLayoutTests.swift"), "-o", str(binary)],
            check=True,
        )
        completed = subprocess.run([str(binary)], check=True, text=True, capture_output=True)
        self.assertIn("passed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
