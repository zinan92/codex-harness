#!/usr/bin/env bash
set -euo pipefail

echo "Codex Harness has no service, notification callback, hook, or LaunchAgent to unload."
echo "Its ledger is deliberately retained at ~/.codex/harness/ so accounting is not destroyed."
echo "To remove it manually, move that directory to a user-selected backup location."
