#!/usr/bin/env bash
set -euo pipefail

codex_dir="$HOME/.codex"
hook_dir="$codex_dir/hooks"
config_path="$codex_dir/config.toml"
notifier_path="$hook_dir/codex_spoken_notify.py"
lifecycle_path="$hook_dir/jingle_lifecycle.py"
lifecycle_hook_path="$hook_dir/jingle_hook.py"
app_path="$HOME/Applications/Codex 通知设置.app"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

/usr/bin/python3 - "$config_path" "$notifier_path" <<'PY'
from pathlib import Path
import re
import sys

config_path = Path(sys.argv[1])
notifier_path = re.escape(str(Path(sys.argv[2]).resolve()))
if config_path.exists():
    text = config_path.read_text(encoding="utf-8")
    pattern = re.compile(rf'(?m)^notify\s*=\s*\[\s*["\x27]{notifier_path}["\x27]\s*\]\s*\n?')
    updated = pattern.sub("", text, count=1)
    if updated != text:
        config_path.write_text(updated, encoding="utf-8")
        config_path.chmod(0o600)
PY

rm -f "$notifier_path"
rm -f "$lifecycle_path" "$lifecycle_hook_path"
while IFS= read -r asset_name; do
  rm -f "$hook_dir/sounds/$asset_name"
done < <(find "$repo_dir/assets/sounds" -maxdepth 1 -type f -exec basename {} \;)
rm -rf "$app_path"

if [[ "${1:-}" == "--purge-settings" ]]; then
  rm -rf "$codex_dir/spoken-notify"
  echo "Removed app, callback, bundled sounds, and local settings/cache."
else
  echo "Removed app, callback, and bundled sounds. Local settings/cache were preserved."
fi

echo "Restart Codex once so it reloads config.toml."
