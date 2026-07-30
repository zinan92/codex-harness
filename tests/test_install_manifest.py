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

    def test_launch_agent_uses_the_app_executable_not_the_bundle(self) -> None:
        installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        uninstaller = (ROOT / "scripts" / "uninstall.sh").read_text(encoding="utf-8")
        template = (ROOT / "assets" / "io.github.zinan92.codex-jingle.plist.template").read_text(encoding="utf-8")
        self.assertIn('launch_agent_executable="$app_path/Contents/MacOS/CodexNotificationSettings"', installer)
        self.assertIn('launchctl bootstrap "gui/$user_id" "$launch_agent_path"', installer)
        self.assertIn('launchctl kickstart -k "gui/$user_id/$launch_agent_label"', installer)
        self.assertIn('launchctl bootout "gui/$user_id/$launch_agent_label"', uninstaller)
        self.assertIn('__JINGLE_EXECUTABLE_PATH__', template)
        self.assertNotIn('__JINGLE_APP_PATH__', template)


if __name__ == "__main__":
    unittest.main()
