from __future__ import annotations
import os
from pathlib import Path
import sys, tempfile, unittest
from unittest import mock

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import jingle_hook
import jingle_summary
import codex_spoken_notify
from jingle_lifecycle import load_state

class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); root = Path(self.temp.name)
        self.env = {'JINGLE_STATE_PATH':str(root/'state.json'),'JINGLE_LOCK_PATH':str(root/'state.lock'),'JINGLE_EVENT_LOG_PATH':str(root/'events.jsonl')}
        self.old = {k:os.environ.get(k) for k in self.env}; os.environ.update(self.env)
    def tearDown(self):
        for key, value in self.old.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        self.temp.cleanup()
    def test_initial_card_precedes_detached_summary_launch(self):
        start={'hook_event_name':'UserPromptSubmit','session_id':'s','turn_id':'t','cwd':'/tmp'}
        stop={**start,'hook_event_name':'Stop','last_assistant_message':'Completed.'}
        with mock.patch.object(jingle_summary, 'last_assistant_text', return_value='具体产出已经完成') as text, mock.patch.object(jingle_summary, 'launch') as launch, mock.patch.object(codex_spoken_notify, 'launch_worker') as notify:
            jingle_hook.handle('codex', start)
            result=jingle_hook.handle('codex', stop)
            unit=load_state()['units']['codex:s:t']
            self.assertEqual(unit['summary'], '具体产出已经完成'); self.assertEqual(unit['summary_status'], 'pending')
            text.assert_called_once(); launch.assert_called_once()
            notify.assert_not_called()
            self.assertEqual(result['summary']['status'], 'summary_initial')
    def test_no_key_and_request_failure_keep_fallback_safe(self):
        with mock.patch.dict(os.environ, {'JINGLE_DEEPSEEK_KEY_PATH':'/missing'}, clear=False):
            self.assertEqual(jingle_summary.summarize('有内容'), '')
        with mock.patch.object(jingle_summary, 'read_key', return_value='test-key'), mock.patch.object(jingle_summary.request, 'urlopen', side_effect=OSError):
            self.assertEqual(jingle_summary.summarize('有内容'), '')
        self.assertEqual(jingle_summary.first_line(''), '处理中…')

    def test_success_response_is_short_concrete_card_text(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return '{"choices":[{"message":{"content":"已完成投研面板的本地账本接入与验证"}}]}'.encode('utf-8')
        with mock.patch.object(jingle_summary, 'read_key', return_value='test-key'), mock.patch.object(jingle_summary.request, 'urlopen', return_value=Response()):
            result = jingle_summary.summarize('源文本')
        self.assertEqual(result, '已完成投研面板的本地账本接入与验证'[:24])
        self.assertLessEqual(len(result), 24)

if __name__ == '__main__': unittest.main()
