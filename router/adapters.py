"""Local CLI adapters. They intentionally expose no retry or escalation policy."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Sequence

from .config import DEVELOPER_MODEL, MACHINE_GATE, REVIEWER_MODEL, TRIAGE_MODEL


@dataclass(frozen=True)
class CallResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int
    payload: Any = None
    cost_usd: float | None = None
    cost_cents: int | None = None


def _run(args: Sequence[str], cwd: Path) -> CallResult:
    try:
        completed = subprocess.run(
            list(args), cwd=cwd, text=True, capture_output=True, timeout=3600, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CallResult(False, "", str(exc), 127)
    return CallResult(completed.returncode == 0, completed.stdout, completed.stderr, completed.returncode)


def _cost(payload: Any) -> float | None:
    value = payload.get("total_cost_usd") if isinstance(payload, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


class ClaudeAdapter:
    """Fable and Opus use Claude's structured CLI envelope and its direct cost receipt."""

    def invoke(self, *, prompt: str, model: str, workspace: Path) -> CallResult:
        binary = os.environ.get("TR_CLAUDE_BIN", "claude")
        result = _run(
            (binary, "-p", prompt, "--model", model, "--output-format", "json"), workspace
        )
        if not result.ok:
            return result
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return CallResult(False, result.stdout, "Claude returned invalid JSON", result.returncode)
        return CallResult(True, result.stdout, result.stderr, result.returncode, payload, _cost(payload))

    def triage(self, prompt: str, workspace: Path) -> CallResult:
        return self.invoke(prompt=prompt, model=TRIAGE_MODEL, workspace=workspace)

    def review(self, prompt: str, workspace: Path) -> CallResult:
        return self.invoke(prompt=prompt, model=REVIEWER_MODEL, workspace=workspace)


class CodexAdapter:
    """Codex is non-interactive; its costs are attached afterwards by the workflow."""

    def implement(self, prompt: str, workspace: Path) -> CallResult:
        binary = os.environ.get("TR_CODEX_BIN", "codex")
        return _run(
            (binary, "exec", "--skip-git-repo-check", "-m", DEVELOPER_MODEL, prompt), workspace
        )


class MachineGate:
    """The approved repository machine gate; its exit code is the only gate verdict."""

    def check(self, workspace: Path) -> CallResult:
        return _run(MACHINE_GATE, workspace)
