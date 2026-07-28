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

## Workbench 与账本的连接

`workbench.html` **不再自己算钱**，成本数据一律读同目录的 `ledger.json`。

刷新数据：

```bash
python3 -m ledger report --json > ledger.json
```

本地查看（页面用 `fetch` 读 JSON，必须经 HTTP，不能用 `file://`）：

```bash
python3 -m http.server 8790 --bind 127.0.0.1
# 打开 http://127.0.0.1:8790/workbench.html
```

`ledger.json` 是派生数据，已在 `.gitignore` 里，不入库。页面加载不到它时会显示上面这条生成命令，不会静默显示旧数字。

项目分组来自 `ledger/registry.py` 里每个 `Project` 的 `group` 字段——加新项目只改 registry，页面自动跟随。
中栏的实时嵌入与进度时间轴目前只属于 `trading-orchestrator`；选中别的项目时，页面会明确标注这一点。
