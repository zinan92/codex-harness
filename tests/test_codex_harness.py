from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("codex_harness", ROOT / "src" / "codex_harness.py")
assert spec and spec.loader
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class CodexHarnessTests(unittest.TestCase):
    def test_canonical_entrypoint_delegates_to_the_single_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "threads.json"
            state.write_text(json.dumps({"schema_version": 1, "threads": {}}), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = harness.main(["summary", "--state", str(state)])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["threads"], 0)

    def test_ui_command_uses_harness_branding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "threads.json"
            state.write_text(json.dumps({"schema_version": 1, "threads": {}}), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = harness.main(["ui", "--html", "--state", str(state)])
            self.assertEqual(result, 0)
            self.assertIn("CODEX HARNESS / LOCAL ONLY", output.getvalue())


if __name__ == "__main__":
    unittest.main()
