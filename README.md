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

## Workbench 的三个数据文件

| 文件 | 内容 | 刷新方式 |
|---|---|---|
| `ledger.json` | 钱 + 时间（活跃日/小时） | `python3 -m ledger report --json > ledger.json` |
| `outputs.json` | 产出（PR / 提交 / 昨日合并） | `python3 scripts/build_outputs.py` |
| `status/<项目>.json` | 模块进度 + 状态追踪 | **agent 定期评估**，提示词见 `status/PROMPT.md` |

前两个是机器实算的派生数据（已 gitignore，不入库）；第三个是判断性评估，**入库**（评估本身是有价值的历史）。

页面布局：顶部 banner（项目数/总消耗）→ 左栏项目 List（金额·活跃天数）→ 中上模块进度 →
中主体项目成品（有嵌入则嵌入，无则占位说明）→ 右栏状态追踪 / 产出统计 / 消耗统计 / 参考链接。

本地查看（页面用 `fetch`，必须经 HTTP）：

```bash
python3 -m http.server 8790 --bind 127.0.0.1
# 打开 http://127.0.0.1:8790/workbench.html
```

项目分组与 repo 路径都在 `ledger/registry.py`——加新项目只改 registry，页面自动跟随。
