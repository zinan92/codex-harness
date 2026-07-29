"""Asynchronous, best-effort card summaries; never used for state classification."""
from __future__ import annotations
import json, os, re, subprocess, sys
from pathlib import Path
from urllib import request, error

DEFAULT_KEY_PATH = Path('/Users/wendy/park-hands/_secrets/deepseek api.md')

def first_line(text: str) -> str:
    value = next((line.strip() for line in text.splitlines() if line.strip()), '')
    return re.sub(r'\s+', ' ', value)[:24] or '处理中…'

def last_assistant_text(provider: str, transcript_path: str) -> str:
    try: lines = Path(transcript_path).read_text(encoding='utf-8').splitlines()
    except OSError: return ''
    found = ''
    for line in lines:
        try: item = json.loads(line)
        except json.JSONDecodeError: continue
        if provider == 'codex':
            payload = item.get('payload', {}) if isinstance(item, dict) else {}
            if item.get('type') == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'assistant':
                found = '\n'.join(str(part.get('text') or '') for part in payload.get('content', []) if isinstance(part, dict) and part.get('type') == 'output_text') or found
        elif isinstance(item, dict):
            message = item.get('message', {})
            if item.get('type') == 'assistant' and isinstance(message, dict) and message.get('role') == 'assistant':
                found = '\n'.join(str(part.get('text') or '') for part in message.get('content', []) if isinstance(part, dict) and part.get('type') == 'text') or found
    return found

def read_key() -> str:
    path = Path(os.environ.get('JINGLE_DEEPSEEK_KEY_PATH', str(DEFAULT_KEY_PATH)))
    try: return path.read_text(encoding='utf-8').strip()
    except OSError: return ''

def summarize(text: str) -> str:
    if not text: return ''
    key = read_key()
    if not key: return ''
    body = json.dumps({'model':'deepseek-chat','temperature':0.2,'max_tokens':60,'messages':[{'role':'system','content':'将内容概括为一句具体中文陈述，24字以内，不要空话。'},{'role':'user','content':text}]}, ensure_ascii=False).encode()
    call = request.Request('https://api.deepseek.com/chat/completions', data=body, headers={'Authorization': f'Bearer {key}','Content-Type':'application/json'})
    try:
        with request.urlopen(call, timeout=12) as response:
            value = json.loads(response.read())
        return first_line(str(value['choices'][0]['message']['content']))
    except (OSError, error.URLError, error.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError): return ''

def launch(unit_id: str, provider: str, transcript_path: str) -> None:
    try:
        subprocess.Popen([sys.executable, str(Path(__file__)), '--worker', unit_id, provider, transcript_path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        from jingle_lifecycle import attach_summary
        attach_summary(unit_id, None)

def main() -> int:
    if len(sys.argv) != 5 or sys.argv[1] != '--worker': return 0
    from jingle_lifecycle import attach_summary
    unit_id, provider, transcript_path = sys.argv[2:]
    result = summarize(last_assistant_text(provider, transcript_path))
    attach_summary(unit_id, result or None)
    return 0
if __name__ == '__main__': raise SystemExit(main())
