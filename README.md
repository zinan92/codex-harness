# Codex Harness

Codex Harness is the local accounting layer for work done in the Codex App.
Its primary job is simple: for every discoverable Codex thread, record how many
tokens were used and which product/workspace the thread belonged to. The same
repository also carries the historical Jingle, Token Router, and TokenPulse
modules so the product has one name and one migration path.

## Active product

The active v1 surface is intentionally local and read-only:

- one row per Codex `session_meta.payload.id`;
- fresh, cached, output, reasoning, and Codex-declared total tokens;
- daily increments in `Asia/Shanghai` by default;
- deterministic longest-CWD-prefix project attribution;
- explicit `available`/`unavailable` accounting status;
- a local HTML view of totals, seven-day activity, projects, and recent thread IDs.

Codex Harness does not route model work, predict future cost, upload prompts or
responses, call an external summariser, or make an autonomous model choice.
Cost and quota displays are reporting features only when a future module adds
them; they never affect routing.

## Install and run

```bash
git clone https://github.com/zinan92/codex-harness.git
cd codex-harness
./scripts/install.sh

# Scan local Codex history and print a JSON summary.
/usr/bin/python3 ~/.codex/harness/codex_harness.py scan
/usr/bin/python3 ~/.codex/harness/codex_harness.py summary

# Serve the read-only local view at http://127.0.0.1:8765.
/usr/bin/python3 ~/.codex/harness/codex_harness_ui.py
# or: /usr/bin/python3 ~/.codex/harness/codex_harness.py ui
```

The installer has no LaunchAgent, hook, notification, network client, or
recurring job. It copies the old `~/.codex/token-counter/threads.json` and
`projects.json` into `~/.codex/harness/` only when the new files do not exist;
the old directory is left intact for rollback. Existing
`~/.codex/jingle/projects.json` aliases are merged into the new project map.

## Optional completion alert

The former Jingle “真狗” alert is still available as a Codex Harness module,
but it is opt-in. It is a local `turn-ended` callback, not a LaunchAgent:

```bash
# Enable the callback and preserve the existing Computer Use notification.
./scripts/enable-alert.sh

# Restart Codex once, then play a real local test sound/speech.
python3 ~/.codex/harness/notifications/codex_harness_notify.py \
  --test-title "Codex Harness 测试" --status success

# Failed/blocked/needs-confirmation style alert.
python3 ~/.codex/harness/notifications/codex_harness_notify.py \
  --test-title "需要确认" --status attention

# Disable only the Harness callback and keep the other notify command.
./scripts/disable-alert.sh
```

After enabling, every main Codex turn that reaches `turn-ended` produces the
success sound without speech. A final message containing a deterministic
failure, blocked, missing-evidence, or pending-confirmation marker uses the
attention sound and, when speech is enabled, announces the task/status.
Subagent completions are ignored. The notifier reads/writes only local metadata
and keeps its settings, deduplication state, and event log under
`~/.codex/harness/notifications/`. Existing
`~/.codex/spoken-notify/` data is copied only when the new files are absent;
nothing is deleted.

If enabling refuses to modify the current `notify` shape, stop and inspect the
timestamped backup rather than overwriting an unrelated callback. Restart
Codex after either enable or disable so it reloads `config.toml`.

## Data and privacy contract

The scanner reads `~/.codex/sessions` and
`~/.codex/archived_sessions`. It parses only `session_meta` and `token_count`
records, never stores prompt/response bodies, and makes no network request.
Project names come from `~/.codex/harness/projects.json`; unknown paths remain
visible as `Uncategorized`. Historic attribution is frozen unless the caller
explicitly requests `--remap-uncategorized`.

The private ledger lives at:

```text
~/.codex/harness/threads.json
~/.codex/harness/projects.json
```

Both files are owner-only. The scanner writes atomically and records its source
(`last_token_usage` or cumulative delta) so repeated Codex snapshots cannot be
silently counted twice.

## One repository, clear module boundaries

```text
src/codex_harness.py          # canonical CLI
src/token_counter.py          # audited ledger implementation/compatibility import
src/codex_harness_ui.py       # canonical UI entry point
src/token_counter_ui.py       # UI implementation/compatibility import
legacy/tokenrouter/            # archived model-routing history; never active
legacy/tokenpulse/             # imported TokenPulse history; opt-in/legacy modules
```

The former TokenPulse capabilities (Claude accounting, Telegram nudges,
game-like levels, share cards, ranking, and furnace automation) remain under
`legacy/tokenpulse` for history and selective future extraction. They are not
installed or started by Codex Harness v1. The former Jingle callback and
notification files remain for forensic recovery; the retirement script removes
only their known registrations and keeps backups.

## Development

```bash
python3 -m unittest discover tests -v
```

The accounting contract must be reconciled against representative real Codex
sessions before changing the ingestion path. A green unit-test run does not
replace the local scan and UI smoke checks.

## Migration and rollback

The GitHub repository is now `zinan92/codex-harness`. GitHub redirects the old
`token-counter` URL, and the repository retains the Jingle and Token Router
history. Token Router is archived; TokenPulse is retained as imported legacy
source until the Codex Harness runtime acceptance gate is complete.

To roll back the local runtime, stop using `~/.codex/harness/` and run the
preserved files under `~/.codex/token-counter/`. No historic ledger or local
configuration is deleted by the installer or retirement scripts.
