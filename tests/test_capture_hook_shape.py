from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[1]

class CaptureHookShapeTests(unittest.TestCase):
    def test_capture_redacts_message_bodies_and_reports_required_field_presence(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'shape.jsonl'
            payload = {'hook_event_name':'Stop','session_id':'s','turn_id':'t','cwd':'/tmp','transcript_path':'/tmp/t.jsonl','prompt':'do not persist','last_assistant_message':'do not persist'}
            completed = subprocess.run([sys.executable, str(ROOT/'tests'/'capture_hook_shape.py')], input=json.dumps(payload), text=True, capture_output=True, env={**os.environ, 'JINGLE_HOOK_SHAPE_LOG':str(destination)}, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            captured = json.loads(destination.read_text())
            self.assertNotIn('prompt', captured['fields'])
            self.assertNotIn('last_assistant_message', captured['fields'])
            self.assertTrue(captured['has']['session_id'])
            self.assertTrue(captured['has']['turn_id'])

if __name__ == '__main__': unittest.main()
