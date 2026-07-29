# Jingle workflow boundary and notification policy

Jingle never infers `/go` from assistant prose. A wrapper that starts a multi-step workflow must
write one explicit marker before its first internal turn and one after its final turn:

```bash
python3 "$HOME/.codex/hooks/jingle_workflow.py" --provider codex --session-id "$SESSION_ID" --cwd "$PWD" --start
# run the workflow's internal turns
python3 "$HOME/.codex/hooks/jingle_workflow.py" --provider codex --session-id "$SESSION_ID" --finish
```

Use `--blocked` rather than `--finish` when the workflow itself ends waiting for Park. Internal
`done` turns retain their Work Unit ledger entries and accounting, but stay out of Jingle's
attention group until the explicit finish marker releases the final terminal result. An internal
`blocked` remains immediately actionable.

`~/.codex/jingle/projects.json` can set `notification_policy` on a project. A normal independent
completion enters Jingle's queue with a quiet success sound; only a blocked decision interrupts
with a call card and speech:

| Policy | done | blocked |
|---|---|---|
| `task_terminal` (default) | queue + success sound | call + voice |
| `workflow_terminal` | ledger only | call + voice |
| `blocked_only` | suppressed from attention | call + voice |

Unmapped paths and invalid policies fail closed to `task_terminal`. The three Work Unit states
remain `running`, `blocked`, and `done`; this policy adds no fourth state or third sound.

`needs_attention` is written when a Work Unit reaches its terminal state. Rows created before
this policy was installed stay ledger-only, so upgrading Jingle never resurrects historical
completion noise.
