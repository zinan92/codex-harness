from __future__ import annotations

from pathlib import Path
import unittest


class MenuBarPlacementTests(unittest.TestCase):
    def test_popovers_open_below_the_menu_bar_item(self) -> None:
        source = (Path(__file__).parents[1] / "src" / "CodexNotificationSettings.swift").read_text(encoding="utf-8")
        self.assertEqual(source.count("preferredEdge: .maxY"), 2)
        self.assertNotIn("preferredEdge: .minY", source)


if __name__ == "__main__":
    unittest.main()
