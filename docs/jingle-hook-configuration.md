# Jingle lifecycle hook configuration

Jingle currently uses Codex lifecycle hooks. The hook command
persists only provider, session/turn IDs, cwd, timestamps, state, and a short
deterministic outcome reason. It does not persist prompts or assistant output.

`src/jingle_hook.py` requires its sibling `jingle_lifecycle.py`. The installer
copies both to `~/.codex/hooks/`, but it deliberately does **not** edit either
global hook configuration: adding global hooks is a user-visible configuration
change and must be opted into separately.

## Codex CLI

Codex 0.146 supports `UserPromptSubmit` and `Stop` hooks. Add this as
`~/.codex/hooks.json` (or use the equivalent inline `[hooks]` TOML), adjusting
the path if needed. Codex asks you to trust a newly added command hook through
`/hooks` before it runs:

```json
{
  "description": "Jingle local lifecycle state",
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "/usr/bin/python3 $HOME/.codex/hooks/jingle_hook.py --provider codex"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "/usr/bin/python3 $HOME/.codex/hooks/jingle_hook.py --provider codex"}]}]
  }
}
```

`UserPromptSubmit` creates `running`; `Stop` resolves it to `done` unless its
explicit hook outcome or the existing deterministic attention fallback marks it
`blocked`. Codex's current `Stop` event is the reliable end signal. The lifecycle
hook launches Jingle's detached local delivery after it has made that decision:
`done` is the success sound only; `blocked` is the attention sound plus speech.
If the existing Codex `notify` callback is still installed, both paths use the
same turn id and its existing at-most-once lock suppresses the duplicate.

## Claude Code is intentionally not connected

Jingle currently ignores `--provider claude` before it reads or writes lifecycle
state. Remove any Jingle-owned commands from `~/.claude/settings.json`; existing
Claude ledger rows remain as local history but cannot affect Jingle's count,
cards, audio, or call panel.

## Local verification without changing global configuration

```bash
runtime_dir="$(mktemp -d)"
JINGLE_STATE_PATH="$runtime_dir/work-units.json" \
JINGLE_LOCK_PATH="$runtime_dir/work-units.lock" \
JINGLE_EVENT_LOG_PATH="$runtime_dir/events.jsonl" \
python3 src/jingle_hook.py --provider codex --print-result <<'JSON'
{"hook_event_name":"UserPromptSubmit","session_id":"demo","turn_id":"turn-1","cwd":"/tmp/demo"}
JSON
```

The result is `running`. Feed a matching `Stop` payload to produce `done` or
`blocked`; inspect the isolated state file and event log to verify it contains
no prompt or assistant message body.
