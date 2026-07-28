# tokenrouter ledger

本地、可复算的 Claude Code 与 Codex 使用账本。只读取 `~/.claude/projects/`、
`~/.codex/sessions/` 和 `~/.codex/archived_sessions/`，不需要 API key 或第三方依赖。

```sh
python3 -m ledger report
python3 -m ledger report --json
python3 -m ledger collect --json
```

Codex 每个 JSONL 文件仅使用其最后一个 `total_token_usage` 累计值；新鲜输入为
`input_tokens - cached_input_tokens`。无法通过 `ledger/registry.py` 的保守最长前缀规则
确认归属的记录会显示在 `未归类`，不会被猜测性归集。
