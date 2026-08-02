#!/usr/bin/env bash
set -euo pipefail

# Token Counter is deliberately passive: installing it copies a local scanner
# and mapping file only. It registers no Codex callback, hook, notification,
# LaunchAgent, network client, or recurring job.
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_dir="$HOME/.codex"
runtime_dir="$HOME/.codex/token-counter"
counter_path="$runtime_dir/token_counter.py"
projects_path="$runtime_dir/projects.json"

mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"
install -m 700 "$repo_dir/src/token_counter.py" "$counter_path"
legacy_projects_path="$codex_dir/jingle/projects.json"
/usr/bin/python3 - "$projects_path" "$repo_dir/assets/token-counter-projects.json" "$legacy_projects_path" <<'PY'
import json
import os
from pathlib import Path
import sys
import tempfile

destination, template, legacy = map(Path, sys.argv[1:])
def read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and isinstance(value.get("projects"), list) else {"projects": []}
    except (OSError, json.JSONDecodeError):
        return {"projects": []}

current = read(destination) if destination.exists() else read(template)
known = {str(project.get("project_id")) for project in current["projects"] if isinstance(project, dict)}
for project in read(legacy)["projects"]:
    if isinstance(project, dict) and str(project.get("project_id")) not in known:
        current["projects"].append(project)
        known.add(str(project.get("project_id")))
destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix="projects-", suffix=".json", dir=destination.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(current, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, destination)
finally:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
PY

/usr/bin/python3 "$counter_path" scan --remap-uncategorized
echo "Token Counter installed at $runtime_dir. It is local and passive."
echo "Run: /usr/bin/python3 $counter_path scan"
