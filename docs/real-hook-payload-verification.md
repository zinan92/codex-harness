# Real hook payload verification

Verified on 2026-07-29 using one real, non-destructive main-task turn per CLI.
The capture program retained field names and types only; prompts, assistant text,
and all secret-bearing content were excluded. Temporary Codex global and project
hook files were removed immediately after the runs.

| Provider | CLI version | Observed events | Required fields present |
| --- | --- | --- | --- |
| Codex | 0.146.0 | `UserPromptSubmit`, `Stop` | `session_id`, `turn_id`, `cwd`, `transcript_path` |
| Claude Code | 2.1.220 | `UserPromptSubmit`, `Stop` | `session_id`, `cwd`, `transcript_path`; no `turn_id` |

Codex `Stop` additionally carried `stop_hook_active` and a final-message field.
Claude `Stop` carried `stop_hook_active`, `background_tasks`, `session_crons`,
and a final-message field. Claude's absent `turn_id` confirms the implemented
provider asymmetry: its Work Unit is joined by the active provider + session
record, while Codex uses provider + session + turn.

No real subagent event was produced by the one-turn non-interactive probes.
That is expected for these commands: neither instructed the model to spawn one.
The adapter's explicit `agent_id` / `agent_type` and `SubagentStop` suppression
remains unit-tested; a future interactive multi-agent exercise can add live
subagent evidence without altering the main-task payload contract.
