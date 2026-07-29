#!/usr/bin/python3
"""Return a Jingle Work Unit to its originating Codex or Claude session."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Callable


Run = Callable[..., subprocess.CompletedProcess[str]]


def shell_command(program: str, session_id: str, cwd: str) -> str:
    """Build the user-visible Terminal command without interpolating shell text."""
    quoted_cwd = shlex.quote(cwd)
    quoted_session = shlex.quote(session_id)
    return f"cd {quoted_cwd} && {program} resume {quoted_session}"


def terminal_script(command: str) -> str:
    return "tell application \"Terminal\"\nactivate\ndo script " + json.dumps(command) + "\nend tell"


def run_osascript_text(script: str, run: Run = subprocess.run) -> str | None:
    try:
        result = run(
            ["osascript", "-e", script], text=True, capture_output=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def run_osascript(script: str, run: Run = subprocess.run) -> bool:
    return run_osascript_text(script, run) is not None


def resume_codex(session_id: str, cwd: str, run: Run = subprocess.run) -> dict[str, str]:
    if shutil.which("codex") and run_osascript(terminal_script(shell_command("codex", session_id, cwd)), run):
        return {"status": "codex_resumed", "message": "已在 Terminal 打开 Codex 会话。"}

    app = os.environ.get("JINGLE_CODEX_APP", "ChatGPT")
    try:
        opened = run(["open", "-a", app, cwd], text=True, capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        opened = None
    if opened and opened.returncode == 0:
        return {"status": "codex_app_opened", "message": "无法启动指定会话，已打开 Codex 项目。"}
    return {"status": "failed", "message": "无法打开 Codex 会话或项目。"}


def focus_claude_terminal(session_id: str, cwd: str, run: Run = subprocess.run) -> bool:
    """Best-effort focus based on the session id or project directory in window titles."""
    project = Path(cwd).name
    script = f'''tell application "System Events"
repeat with appName in {{"Terminal", "iTerm2", "Warp"}}
    if exists process appName then
        tell process appName
            repeat with terminalWindow in windows
                try
                    set labelText to name of terminalWindow
                    if labelText contains {json.dumps(session_id)} then
                        set frontmost to true
                        perform action "AXRaise" of terminalWindow
                        return "focused"
                    else if {json.dumps(project)} is not "" and labelText contains {json.dumps(project)} then
                        set frontmost to true
                        perform action "AXRaise" of terminalWindow
                        return "focused"
                    end if
                end try
            end repeat
        end tell
    end if
end repeat
return "not-found"
end tell'''
    return run_osascript_text(script, run) == "focused"


def copy_claude_resume(session_id: str, run: Run = subprocess.run) -> bool:
    command = f"claude --resume {session_id}"
    try:
        result = run(["pbcopy"], input=command, text=True, capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def resume_claude(session_id: str, cwd: str, run: Run = subprocess.run) -> dict[str, str]:
    if focus_claude_terminal(session_id, cwd, run):
        return {"status": "claude_focused", "message": "已聚焦原 Claude 终端会话。"}
    if copy_claude_resume(session_id, run):
        return {"status": "claude_resume_copied", "message": "未找到原终端；已复制 claude --resume 命令，请粘贴执行。"}
    return {"status": "failed", "message": "未找到原 Claude 终端，且无法复制 resume 命令。"}


def route(provider: str, session_id: str, cwd: str, run: Run = subprocess.run) -> dict[str, str]:
    if not session_id or not cwd:
        return {"status": "failed", "message": "该 Work Unit 缺少 session 或项目路径。"}
    if provider == "codex":
        return resume_codex(session_id, cwd, run)
    if provider == "claude":
        return resume_claude(session_id, cwd, run)
    return {"status": "failed", "message": "不支持的会话提供方。"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=("codex", "claude"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--cwd", required=True)
    args = parser.parse_args()
    print(json.dumps(route(args.provider, args.session_id, args.cwd), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
