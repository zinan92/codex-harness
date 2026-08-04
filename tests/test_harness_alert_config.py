from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("harness_alert_config", ROOT / "src" / "harness_alert_config.py")
assert spec and spec.loader
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


SKY = "/Applications/SkyComputerUseClient"
NOTIFIER = "/Users/wendy/.codex/harness/notifications/codex_harness_notify.py"


class HarnessAlertConfigTests(unittest.TestCase):
    def test_add_preserves_sky_callback_and_is_idempotent(self) -> None:
        original = f'notify = ["{SKY}", "turn-ended"]\nmodel = "gpt-5.6-sol"\n'
        updated = config.add_notifier(original, NOTIFIER)
        self.assertIn("--previous-notify", updated)
        self.assertEqual(config.read_notify(updated), [SKY, "turn-ended", "--previous-notify", f'["{NOTIFIER}"]'])
        self.assertEqual(config.add_notifier(updated, NOTIFIER), updated)

    def test_add_preserves_existing_previous_callback(self) -> None:
        original = f'notify = ["{SKY}", "turn-ended", "--previous-notify", "[\\"/old/callback\\"]"]\n'
        updated = config.add_notifier(original, NOTIFIER)
        values = config.read_notify(updated)
        assert values is not None
        self.assertEqual(values[:2], [SKY, "turn-ended"])
        self.assertEqual(values[3], f'["/old/callback", "{NOTIFIER}"]')

    def test_add_migrates_legacy_notifier_in_known_chain(self) -> None:
        legacy = "/Users/wendy/.codex/hooks/codex_spoken_notify.py"
        original = f'notify = ["{SKY}", "turn-ended", "--previous-notify", "[\\"{legacy}\\"]"]\n'
        values = config.read_notify(config.add_notifier(original, NOTIFIER))
        assert values is not None
        self.assertEqual(values[3], f'["{NOTIFIER}"]')

    def test_add_migrates_legacy_direct_notifier(self) -> None:
        legacy = "/Users/wendy/.codex/hooks/codex_spoken_notify.py"
        self.assertEqual(config.read_notify(config.add_notifier(f'notify = ["{legacy}"]\n', NOTIFIER)), [NOTIFIER])

    def test_multiline_notify_is_rejected(self) -> None:
        original = f'notify = [\n  "{SKY}",\n  "turn-ended",\n]\n'
        with self.assertRaises(config.NotifyConfigError):
            config.add_notifier(original, NOTIFIER)

    def test_remove_keeps_sky_and_other_previous_callback(self) -> None:
        original = f'notify = ["{SKY}", "turn-ended", "--previous-notify", "[\\"/old/callback\\", \\"{NOTIFIER}\\"]"]\n'
        updated = config.remove_notifier(original, NOTIFIER)
        self.assertEqual(config.read_notify(updated), [SKY, "turn-ended", "--previous-notify", '["/old/callback"]'])

    def test_remove_last_previous_callback_restores_sky_shape(self) -> None:
        original = f'notify = ["{SKY}", "turn-ended", "--previous-notify", "[\\"{NOTIFIER}\\"]"]\n'
        self.assertEqual(config.read_notify(config.remove_notifier(original, NOTIFIER)), [SKY, "turn-ended"])

    def test_unknown_callback_is_rejected(self) -> None:
        with self.assertRaises(config.NotifyConfigError):
            config.add_notifier('notify = ["/unknown/callback", "turn-ended"]\n', NOTIFIER)


if __name__ == "__main__":
    unittest.main()
