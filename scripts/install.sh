#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Codex Jingle currently supports macOS only." >&2
  exit 1
fi

for command_name in swiftc codesign; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    echo "Install Xcode Command Line Tools with: xcode-select --install" >&2
    exit 1
  fi
done

if [[ ! -x "/usr/bin/python3" ]]; then
  echo "Missing required command: /usr/bin/python3" >&2
  echo "Install Xcode Command Line Tools with: xcode-select --install" >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "$script_dir/.." && pwd)"
codex_dir="$HOME/.codex"
hook_dir="$codex_dir/hooks"
sound_dir="$hook_dir/sounds"
config_path="$codex_dir/config.toml"
notifier_path="$hook_dir/codex_spoken_notify.py"
lifecycle_path="$hook_dir/jingle_lifecycle.py"
lifecycle_hook_path="$hook_dir/jingle_hook.py"
accounting_path="$hook_dir/jingle_accounting.py"
summary_path="$hook_dir/jingle_summary.py"
control_path="$hook_dir/jingle_control.py"
resume_path="$hook_dir/jingle_resume.py"
workflow_path="$hook_dir/jingle_workflow.py"
projects_path="$codex_dir/jingle/projects.json"
app_path="$HOME/Applications/Codex 通知设置.app"
launch_agent_label="io.github.zinan92.codex-jingle"
launch_agent_path="$HOME/Library/LaunchAgents/$launch_agent_label.plist"
launch_agent_template="$repo_dir/assets/$launch_agent_label.plist.template"
user_id="$(id -u)"
staging_dir="$(mktemp -d "${TMPDIR:-/tmp}/codex-jingle.XXXXXX")"

cleanup() {
  rm -rf "$staging_dir"
}
trap cleanup EXIT

mkdir -p "$hook_dir" "$sound_dir" "$HOME/Applications"
chmod 700 "$codex_dir" "$hook_dir" "$sound_dir"

install -m 755 "$repo_dir/src/codex_spoken_notify.py" "$notifier_path"
install -m 644 "$repo_dir/src/jingle_lifecycle.py" "$lifecycle_path"
install -m 755 "$repo_dir/src/jingle_hook.py" "$lifecycle_hook_path"
install -m 644 "$repo_dir/src/jingle_accounting.py" "$accounting_path"
install -m 644 "$repo_dir/src/jingle_summary.py" "$summary_path"
install -m 755 "$repo_dir/src/jingle_control.py" "$control_path"
install -m 755 "$repo_dir/src/jingle_resume.py" "$resume_path"
install -m 755 "$repo_dir/src/jingle_workflow.py" "$workflow_path"
if [[ ! -f "$projects_path" ]]; then
  mkdir -p "$codex_dir/jingle"
  install -m 600 "$repo_dir/assets/jingle-projects.json" "$projects_path"
fi
install -m 644 "$repo_dir/assets/sounds/"* "$sound_dir/"

new_app="$staging_dir/Codex 通知设置.app"
mkdir -p "$new_app/Contents/MacOS"
swiftc -O -parse-as-library \
  -framework AppKit \
  -framework SwiftUI \
  "$repo_dir/src/JinglePanelLayout.swift" \
  "$repo_dir/src/CodexNotificationSettings.swift" \
  -o "$new_app/Contents/MacOS/CodexNotificationSettings"
install -m 644 \
  "$repo_dir/src/CodexNotificationSettings-Info.plist" \
  "$new_app/Contents/Info.plist"
codesign --force --deep --sign - "$new_app" >/dev/null

previous_app="$staging_dir/previous.app"
if [[ -e "$app_path" ]]; then
  mv "$app_path" "$previous_app"
fi
if ! mv "$new_app" "$app_path"; then
  if [[ -e "$previous_app" ]]; then
    mv "$previous_app" "$app_path"
  fi
  echo "Failed to install the settings app; the previous app was restored." >&2
  exit 1
fi

if [[ -f "$config_path" ]]; then
  backup_path="$config_path.codex-jingle.$(date +%Y%m%d-%H%M%S).bak"
  cp -p "$config_path" "$backup_path"
  echo "Backed up Codex config: $backup_path"
fi

/usr/bin/python3 - "$config_path" "$notifier_path" <<'PY'
import json
import os
from pathlib import Path
import re
import sys
import tempfile

config_path = Path(sys.argv[1])
notifier_path = str(Path(sys.argv[2]).resolve())
replacement = f"notify = [{json.dumps(notifier_path)}]"
text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
pattern = re.compile(r"(?m)^notify\s*=.*$")
if pattern.search(text):
    text = pattern.sub(replacement, text, count=1)
else:
    text = replacement + "\n" + text

config_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
fd, temp_name = tempfile.mkstemp(prefix="config-", suffix=".toml", dir=config_path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(text)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(temp_name, 0o600)
    os.replace(temp_name, config_path)
finally:
    try:
        os.unlink(temp_name)
    except FileNotFoundError:
        pass
PY

/usr/bin/python3 "$notifier_path" --show-settings >/dev/null
codesign --verify --deep --strict "$app_path"

mkdir -p "$HOME/Library/LaunchAgents"
launch_agent_temp="$staging_dir/$launch_agent_label.plist"
/usr/bin/python3 - "$launch_agent_template" "$launch_agent_temp" "$app_path" <<'PY'
from pathlib import Path
import sys

template, destination, app_path = map(Path, sys.argv[1:])
contents = template.read_text(encoding="utf-8").replace("__JINGLE_APP_PATH__", str(app_path))
destination.write_text(contents, encoding="utf-8")
PY
plutil -lint "$launch_agent_temp" >/dev/null
mv "$launch_agent_temp" "$launch_agent_path"
launchctl bootout "gui/$user_id/$launch_agent_label" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$user_id" "$launch_agent_path"
launchctl kickstart -k "gui/$user_id/$launch_agent_label"

echo
echo "Codex Jingle installed."
echo "Settings app: $app_path"
echo "Lifecycle hook helpers: $lifecycle_hook_path"
echo "Menu-bar runtime: $launch_agent_label"
echo "See docs/jingle-hook-configuration.md to opt into Codex/Claude hooks."
echo "Restart Codex once so it reloads the notify callback."
