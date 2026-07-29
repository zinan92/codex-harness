#!/usr/bin/python3
"""Return a Jingle Work Unit to its originating session without false success."""

from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any, Callable


Run = Callable[..., subprocess.CompletedProcess[str]]


def run_osascript_text(script: str, run: Run = subprocess.run) -> str | None:
    try:
        result = run(["osascript", "-e", script], text=True, capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def terminal_tty_script(tty: str) -> str:
    """Focus exactly one Terminal tab by its TTY, not a project-title guess."""
    quoted_tty = json.dumps(tty)
    return f'''tell application "Terminal"
repeat with terminalWindow in windows
    repeat with terminalTab in tabs of terminalWindow
        if tty of terminalTab is {quoted_tty} then
            activate
            set selected tab of terminalWindow to terminalTab
            set index of terminalWindow to 1
            return "focused:" & tty of terminalTab
        end if
    end repeat
end repeat
return "not-found"
end tell'''


def focus_terminal_locator(locator: dict[str, Any] | None, run: Run = subprocess.run) -> bool:
    """Return true only when the stored terminal identity is verified again."""
    locator = locator or {}
    terminal_app = str(locator.get("terminal_app") or "")
    terminal_tty = str(locator.get("terminal_tty") or "")
    if terminal_app != "Terminal" or not terminal_tty:
        return False
    return run_osascript_text(terminal_tty_script(terminal_tty), run) == f"focused:{terminal_tty}"


def resume_codex(session_id: str, cwd: str, locator: dict[str, Any] | None = None, run: Run = subprocess.run) -> dict[str, str]:
    if focus_terminal_locator(locator, run):
        return {"status": "codex_focused", "message": "已聚焦原 Codex 终端会话。"}
    return {"status": "failed", "message": "未定位原 Codex 会话，未打开任何新项目或会话。"}


def focus_claude_terminal(session_id: str, cwd: str, locator: dict[str, Any] | None = None, run: Run = subprocess.run) -> bool:
    """Kept as a provider-named wrapper so tests prove there is no cwd fallback."""
    return focus_terminal_locator(locator, run)


def resume_claude(session_id: str, cwd: str, locator: dict[str, Any] | None = None, run: Run = subprocess.run) -> dict[str, str]:
    if focus_claude_terminal(session_id, cwd, locator, run):
        return {"status": "claude_focused", "message": "已聚焦原 Claude 终端会话。"}
    return {"status": "failed", "message": "未定位原 Claude 会话，未打开任何新项目或会话。"}


def route(provider: str, session_id: str, cwd: str, locator: dict[str, Any] | None = None, run: Run = subprocess.run) -> dict[str, str]:
    if not session_id:
        return {"status": "failed", "message": "该 Work Unit 缺少 session id，未执行跳转。"}
    if provider == "codex":
        return resume_codex(session_id, cwd, locator, run)
    if provider == "claude":
        return resume_claude(session_id, cwd, locator, run)
    return {"status": "failed", "message": "不支持的会话提供方。"}


def parse_locator(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=("codex", "claude"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--locator-json", default="{}")
    args = parser.parse_args()
    print(json.dumps(route(args.provider, args.session_id, args.cwd, parse_locator(args.locator_json)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
