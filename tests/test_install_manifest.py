from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class InstallManifestTests(unittest.TestCase):
    def test_installer_copies_every_local_jingle_hook_dependency(self) -> None:
        installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        hook_source = (ROOT / "src" / "jingle_hook.py").read_text(encoding="utf-8")
        for module in ("jingle_lifecycle", "jingle_accounting", "jingle_summary", "codex_spoken_notify"):
            self.assertIn(f"from {module} import", hook_source)
            self.assertIn(f'"$repo_dir/src/{module}.py"', installer)

    def test_uninstaller_removes_the_installed_accounting_dependency(self) -> None:
        uninstaller = (ROOT / "scripts" / "uninstall.sh").read_text(encoding="utf-8")
        self.assertIn('accounting_path="$hook_dir/jingle_accounting.py"', uninstaller)
        self.assertIn('"$accounting_path"', uninstaller)


if __name__ == "__main__":
    unittest.main()
