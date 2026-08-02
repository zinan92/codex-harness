# Token Counter

Token Counter is a local, read-only ledger for Codex threads. Its job is narrow:
for every discoverable Codex thread, record token usage and the product it worked
on. It does not route model work, estimate costs, send notifications, open tasks,
summarise with an external model, or keep a background service alive.

## What is recorded

`python3 src/token_counter.py scan` scans `~/.codex/sessions` and
`~/.codex/archived_sessions`. It writes `~/.codex/token-counter/threads.json`
with one row per `session_meta.payload.id`:

- `thread_id`, `cwd`, start/end timestamp, and a frozen project mapping;
- fresh input, cached input, output, reasoning output, and Codex-declared total;
- daily token increments allocated to the timestamp of each cumulative snapshot
  in `Asia/Shanghai` (override with `TOKEN_COUNTER_TIMEZONE`);
- an honest `unavailable` status when a session has no usable usage snapshot.

The ledger never stores prompt text, response text, or an LLM-generated summary.
`project` is a deterministic longest-cwd-prefix match from
`~/.codex/token-counter/projects.json`; unknown paths remain visible as
`Uncategorized`.

When Codex supplies `last_token_usage`, Token Counter uses that event's exact
increment. Older records without it use a cumulative-delta fallback and carry
their source in the private row, so cache re-estimation cannot silently inflate
the ledger.

## Use

```bash
./scripts/install.sh
/usr/bin/python3 ~/.codex/token-counter/token_counter.py scan
/usr/bin/python3 ~/.codex/token-counter/token_counter.py summary
```

The scanner uses only Python's standard library and makes no network request.
It is intentionally manual in v1: `scan` is the explicit refresh boundary.

## Jingle retirement

Existing Codex Jingle installations are not deleted. After Token Counter has
scanned real local sessions successfully, run this one-time cutover:

```bash
./scripts/retire-jingle.sh
```

It backs up `~/.codex/config.toml` and `~/.codex/hooks.json`, removes only the
known Jingle notification/lifecycle registrations, and unloads the Jingle
LaunchAgent. The old app, helpers, plist, and historic state remain available
for forensic recovery.

## Legacy

`legacy/tokenrouter` preserves TokenRouter's original Git history and source.
It is archived context only: its model-routing CLI is not imported, installed,
or called by Token Counter.
