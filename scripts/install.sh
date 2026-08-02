#!/usr/bin/env bash
set -euo pipefail

# Token Counter is deliberately passive: installing it copies a local scanner
# and mapping file only. It registers no Codex callback, hook, notification,
# LaunchAgent, network client, or recurring job.
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="$HOME/.codex/token-counter"
counter_path="$runtime_dir/token_counter.py"
projects_path="$runtime_dir/projects.json"

mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"
install -m 700 "$repo_dir/src/token_counter.py" "$counter_path"
if [[ ! -f "$projects_path" ]]; then
  install -m 600 "$repo_dir/assets/token-counter-projects.json" "$projects_path"
fi

/usr/bin/python3 "$counter_path" scan
echo "Token Counter installed at $runtime_dir. It is local and passive."
echo "Run: /usr/bin/python3 $counter_path scan"
