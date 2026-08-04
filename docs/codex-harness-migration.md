# Codex Harness migration receipt

## Source repositories

| Source | Destination | State |
|---|---|---|
| Codex Jingle | Codex Harness root history | historical lineage retained |
| Token Router | `legacy/tokenrouter/` | archived context, not imported into runtime |
| TokenPulse | `legacy/tokenpulse/` | full Git history imported; modules legacy/opt-in |

The active repository is the former `token-counter` repository. GitHub renames
it to `codex-harness`; the old URL remains a redirect. There is no separate
Codex Jingle remote repository to archive because it had already become the
Token Counter repository.

## Runtime cutover

The authoritative local runtime is `~/.codex/harness/`. Installation copies
the old `~/.codex/token-counter/threads.json` and project mapping only when the
new files are absent, then scans into the new namespace. The old directory,
Jingle state, and historical files are intentionally preserved.

The active launcher is the manual command:

```text
/usr/bin/python3 ~/.codex/harness/codex_harness.py scan
/usr/bin/python3 ~/.codex/harness/codex_harness.py ui
```

No Codex Harness LaunchAgent is installed. The former TokenPulse widget and
former Jingle LaunchAgent must be stopped during final cutover; their source
and local state remain available for rollback.

The Jingle completion sound/speech engine remains available as an explicit
opt-in through `scripts/enable-alert.sh`. It is chained behind the existing
Computer Use `turn-ended` callback and does not use `hooks.json` or a
LaunchAgent.

## Accounting receipt

The scan completed on 2026-08-04 with 981 discovered threads and 877 threads
with usable usage snapshots. The ledger contains only deterministic metadata;
the scanner does not read prompt or response bodies. Historic `token-counter`
project IDs are normalized to `codex-harness` in the new runtime while the old
runtime remains untouched.

## Rollback

If the new runtime is rejected, use the preserved
`~/.codex/token-counter/` scripts and ledger. Do not delete either directory;
the migration is copy-only by design.
