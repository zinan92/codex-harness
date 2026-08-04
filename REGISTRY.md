# Codex Harness Registry

## Now

Codex Harness is the canonical local, read-only accounting surface for Codex
App work. It records one row per Codex thread, token usage by day, and a frozen
deterministic project attribution. The active runtime is `~/.codex/harness/`.

The canonical commands are:

```text
/usr/bin/python3 ~/.codex/harness/codex_harness.py scan
/usr/bin/python3 ~/.codex/harness/codex_harness.py summary
/usr/bin/python3 ~/.codex/harness/codex_harness.py ui
```

There is no active router, notification callback, Telegram nudge, voice
surface, LaunchAgent, network summariser, autonomous refresh, or cost-based
model decision.

## Lineage

- Codex Jingle history is the original lineage of this repository.
- Token Router history is retained at `legacy/tokenrouter` and is archived
  context only.
- TokenPulse history is retained at `legacy/tokenpulse`; its provider,
  motivation, sharing, ranking, and furnace modules are legacy/opt-in and are
  not part of the default runtime.

## Next

Keep the accounting source of truth singular. Any future provider or UI module
must consume the Codex Harness ledger or declare a separate, reconciled source;
it must not silently introduce a second token summation path. Runtime changes
require a real-session scan, UI smoke evidence, and a rollback note.
