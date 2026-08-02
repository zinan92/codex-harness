# Token Counter Registry

## Now

Token Counter is the canonical local, read-only Codex thread ledger. Its source
of truth is timestamped `session_meta` and `token_count` events in Codex JSONL
history. The active projection is one thread row per session ID, with snapshot
deltas allocated to event day and product attribution frozen at ingestion.

It has no Jingle notification, voice, attention queue, popup, callback, hook,
LaunchAgent, network summariser, routing model, cost prediction, or autonomous
refresh path.

## Next

Use `python3 src/token_counter.py scan` after work, then inspect the summary or
the private `~/.codex/token-counter/threads.json` ledger. Add project aliases in
`~/.codex/token-counter/projects.json` when a product should not be
`Uncategorized`.

## Legacy boundary

The old TokenRouter code is retained below `legacy/tokenrouter` only for history
and evidence. It must not become an import, command, scheduled job, or default
runtime dependency of Token Counter.
