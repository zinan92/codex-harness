from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class InstallManifestTests(unittest.TestCase):
    def test_installer_is_a_passive_local_scanner_install(self) -> None:
        installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn('"$repo_dir/src/token_counter.py"', installer)
        self.assertIn('"$repo_dir/assets/token-counter-projects.json"', installer)
        for forbidden in ("jingle_hook.py", "codex_spoken_notify.py", "launchctl", "notify =", "urlopen"):
            self.assertNotIn(forbidden, installer)

    def test_uninstaller_retains_private_ledger_instead_of_destroying_accounting(self) -> None:
        uninstaller = (ROOT / "scripts" / "uninstall.sh").read_text(encoding="utf-8")
        self.assertIn("ledger is deliberately retained", uninstaller)
        self.assertNotIn("rm -", uninstaller)

    def test_retirement_script_is_precise_and_keeps_old_files(self) -> None:
        retirement = (ROOT / "scripts" / "retire-jingle.sh").read_text(encoding="utf-8")
        self.assertIn("codex_spoken_notify.py", retirement)
        self.assertIn("jingle_hook.py", retirement)
        self.assertIn("launchctl bootout", retirement)
        self.assertIn("refusing to edit an unrecognised", retirement)
        self.assertNotIn("rm -", retirement)


if __name__ == "__main__":
    unittest.main()
