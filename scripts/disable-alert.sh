#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON_BIN:-$(command -v python3 || true)}"
if [[ -z "$python_bin" ]] || ! "$python_bin" -c 'import tomllib' >/dev/null 2>&1; then
  echo "Codex Harness alerts require Python 3.11+ (tomllib). Set PYTHON_BIN to a compatible python3." >&2
  exit 1
fi
codex_dir="$HOME/.codex"
config_path="$codex_dir/config.toml"
notifier_path="$codex_dir/harness/notifications/codex_harness_notify.py"
backup_dir="$codex_dir/harness/backups/$(date +%Y%m%d-%H%M%S)-completion-alert-disable"

mkdir -p "$backup_dir"
chmod 700 "$codex_dir/harness" "$backup_dir"
if [[ -f "$config_path" ]]; then
  cp -p "$config_path" "$backup_dir/config.toml"
fi

PYTHONPATH="$repo_dir/src" "$python_bin" - "$config_path" "$notifier_path" <<'PY'
import os
from pathlib import Path
import sys
import tempfile

from harness_alert_config import remove_notifier

config_path, notifier_path = map(Path, sys.argv[1:])
if not config_path.exists():
    print("Codex config not found; nothing to disable.")
    raise SystemExit(0)
text = config_path.read_text(encoding="utf-8")
updated = remove_notifier(text, str(notifier_path.resolve()))
if updated == text:
    print("Codex Harness completion alert was not configured.")
    raise SystemExit(0)
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

echo "Codex Harness completion alert disabled."
echo "Backup: $backup_dir"
echo "Restart Codex once so it reloads config.toml."
