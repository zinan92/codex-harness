#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Codex Harness completion alerts currently require macOS (afplay/say)." >&2
  exit 1
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-$(command -v python3 || true)}"
if [[ -z "$python_bin" ]] || ! "$python_bin" -c 'import tomllib' >/dev/null 2>&1; then
  echo "Codex Harness alerts require Python 3.11+ (tomllib). Set PYTHON_BIN to a compatible python3." >&2
  exit 1
fi
codex_dir="$HOME/.codex"
runtime_dir="$codex_dir/harness/notifications"
legacy_runtime="$codex_dir/spoken-notify"
config_path="$codex_dir/config.toml"
notifier_path="$runtime_dir/codex_harness_notify.py"
backup_dir="$codex_dir/harness/backups/$(date +%Y%m%d-%H%M%S)-completion-alert-enable"
legacy_launch_agent="$HOME/Library/LaunchAgents/io.github.zinan92.codex-jingle.plist"

mkdir -p "$runtime_dir/sounds" "$backup_dir"
chmod 700 "$codex_dir" "$codex_dir/harness" "$runtime_dir" "$runtime_dir/sounds" "$backup_dir"

if [[ -f "$config_path" ]]; then
  cp -p "$config_path" "$backup_dir/config.toml"
fi

# Copy-only migration of the former notifier state. The old directory remains
# the rollback source and is never removed by this command.
for name in settings.json state.json events.jsonl; do
  if [[ ! -e "$runtime_dir/$name" && -e "$legacy_runtime/$name" ]]; then
    cp -p "$legacy_runtime/$name" "$runtime_dir/$name"
    chmod 600 "$runtime_dir/$name"
  fi
done

install -m 700 "$repo_dir/src/codex_spoken_notify.py" "$notifier_path"
for sound in "$repo_dir/assets/sounds/"*.wav; do
  install -m 600 "$sound" "$runtime_dir/sounds/"
done

# The retired Jingle settings app is not part of the alert path. If an old
# LaunchAgent plist has reappeared, unload and quarantine that exact plist so
# it cannot run a second notification state machine beside Harness.
user_id="$(id -u)"
launchctl bootout "gui/$user_id/io.github.zinan92.codex-jingle" >/dev/null 2>&1 || true
if [[ -e "$legacy_launch_agent" ]]; then
  mv "$legacy_launch_agent" "$backup_dir/"
fi

PYTHONPATH="$repo_dir/src" "$python_bin" - "$config_path" "$notifier_path" <<'PY'
import os
from pathlib import Path
import sys
import tempfile

from harness_alert_config import add_notifier

config_path, notifier_path = map(Path, sys.argv[1:])
text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
updated = add_notifier(text, str(notifier_path.resolve()))
config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix="config-", suffix=".toml", dir=config_path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(updated)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, config_path)
finally:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
PY

"$python_bin" "$notifier_path" --show-settings >/dev/null
echo "Codex Harness completion alert enabled."
echo "Backup: $backup_dir"
echo "Restart Codex once so it reloads config.toml."
echo "Test: $python_bin $notifier_path --test-title 'Codex Harness 测试' --status success"
