#!/usr/bin/env bash
set -euo pipefail

# Codex Harness is deliberately passive: installing it copies a local scanner
# and mapping file only. It registers no callback, hook, notification,
# LaunchAgent, network client, or recurring job.
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_dir="$HOME/.codex"
runtime_dir="$codex_dir/harness"
legacy_runtime="$codex_dir/token-counter"
counter_path="$runtime_dir/codex_harness.py"
ledger_path="$runtime_dir/token_counter.py"
ui_path="$runtime_dir/token_counter_ui.py"
harness_ui_path="$runtime_dir/codex_harness_ui.py"
projects_path="$runtime_dir/projects.json"

mkdir -p "$runtime_dir"
chmod 700 "$runtime_dir"

# Preserve the old Token Counter ledger/config in place while making the new
# namespace authoritative. This is intentionally copy-only and idempotent so a
# failed cutover never destroys the previous accounting surface.
for name in projects.json threads.json; do
  if [[ ! -e "$runtime_dir/$name" && -e "$legacy_runtime/$name" ]]; then
    cp -p "$legacy_runtime/$name" "$runtime_dir/$name"
  fi
done

install -m 700 "$repo_dir/src/codex_harness.py" "$counter_path"
install -m 700 "$repo_dir/src/token_counter.py" "$ledger_path"
install -m 700 "$repo_dir/src/token_counter_ui.py" "$ui_path"
install -m 700 "$repo_dir/src/codex_harness_ui.py" "$harness_ui_path"

legacy_projects_path="$codex_dir/jingle/projects.json"
old_counter_projects_path="$legacy_runtime/projects.json"
/usr/bin/python3 - "$projects_path" "$repo_dir/assets/codex-harness-projects.json" "$legacy_projects_path" "$old_counter_projects_path" <<'PY'
import json
import os
from pathlib import Path
import sys
import tempfile

destination, template, *legacy_paths = map(Path, sys.argv[1:])

def read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and isinstance(value.get("projects"), list) else {"projects": []}
    except (OSError, json.JSONDecodeError):
        return {"projects": []}

current = read(destination) if destination.exists() else read(template)
normalized_projects = []
seen_ids = set()
for project in current["projects"]:
    if not isinstance(project, dict):
        continue
    project = dict(project)
    if project.get("project_id") == "token-counter":
        project["project_id"] = "codex-harness"
        project["name"] = "Codex Harness"
        aliases = list(project.get("aliases") or [])
        if not any(isinstance(alias, dict) and alias.get("prefix") == "/Users/wendy/codex-harness" for alias in aliases):
            aliases.append({"prefix": "/Users/wendy/codex-harness"})
        project["aliases"] = aliases
    project_id = str(project.get("project_id"))
    if project_id in seen_ids:
        continue
    seen_ids.add(project_id)
    normalized_projects.append(project)
current["projects"] = normalized_projects
known = {str(project.get("project_id")) for project in current["projects"] if isinstance(project, dict)}
for path in legacy_paths:
    for project in read(path)["projects"]:
        if not isinstance(project, dict):
            continue
        if project.get("project_id") == "token-counter":
            project = dict(project)
            project["project_id"] = "codex-harness"
            project["name"] = "Codex Harness"
        if str(project.get("project_id")) not in known:
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
echo "Codex Harness installed at $runtime_dir. It is local and passive."
echo "Run: /usr/bin/python3 $counter_path scan"
echo "UI:  /usr/bin/python3 $harness_ui_path"
