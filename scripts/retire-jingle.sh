#!/usr/bin/env bash
set -euo pipefail

# One-way runtime cutover, with a timestamped backup.  This command leaves the
# old app, helpers, plist, and historical state in place; it only disables their
# registration points after checking their exact current shapes.
codex_dir="$HOME/.codex"
config_path="$codex_dir/config.toml"
hooks_path="$codex_dir/hooks.json"
backup_dir="$codex_dir/token-counter/backups/$(date +%Y%m%d-%H%M%S)-jingle-retirement"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
[[ -f "$config_path" ]] && cp -p "$config_path" "$backup_dir/config.toml"
[[ -f "$hooks_path" ]] && cp -p "$hooks_path" "$backup_dir/hooks.json"

/usr/bin/python3 - "$config_path" "$hooks_path" <<'PY'
from pathlib import Path
import re
import sys

config_path, hooks_path = map(Path, sys.argv[1:])
if config_path.exists():
    text = config_path.read_text(encoding="utf-8")
    old = re.compile(r'(?m)^notify\s*=\s*\[("[^"]*SkyComputerUseClient"),\s*"turn-ended",\s*"--previous-notify",\s*"(?:[^"\\]|\\.)*codex_spoken_notify\.py(?:[^"\\]|\\.)*"\]\s*$')
    updated, count = old.subn(r'notify = [\1, "turn-ended"]', text, count=1)
    if "codex_spoken_notify.py" in text and count != 1:
        raise SystemExit("refusing to edit an unrecognised Jingle notify configuration")
    if count:
        config_path.write_text(updated, encoding="utf-8")
if hooks_path.exists():
    text = hooks_path.read_text(encoding="utf-8")
    if "jingle_hook.py" in text:
        # The shipped Jingle hooks file contains only Jingle lifecycle commands.
        # Refuse to erase any unrelated user-owned hook registration.
        if '"description": "Jingle local lifecycle state"' not in text:
            raise SystemExit("refusing to edit an unrecognised Jingle hooks configuration")
        hooks_path.write_text("{}\n", encoding="utf-8")
PY

user_id="$(id -u)"
if command -v launchctl >/dev/null 2>&1; then
  launchctl bootout "gui/$user_id/io.github.zinan92.codex-jingle" >/dev/null 2>&1 || true
fi

echo "Jingle runtime registrations retired; backup: $backup_dir"
echo "Old Jingle files and state were preserved. Restart Codex to reload config.toml and hooks.json."
