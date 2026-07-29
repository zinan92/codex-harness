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

## TokenRouter v0

在同一仓库内，路由器的可执行入口是：

```sh
python3 -m router "把 X 改成 Y" --workspace /要修改的项目
# 只让 Fable 判难度、生成合同／stories，不修改目标工作区：
python3 -m router "把 X 改成 Y" --workspace /要修改的项目 --dry-run
```

v0 的判断权只在 `claude-fable-5`：它把任务分为 `simple`、`medium`、`complex`，选择对应的固定 SOP，**不会**估算成本、读取历史成功率或按金额选模型。

- `simple`：Codex 实现／机器闸（最多 2 次）→ Opus 审核。
- `medium`：Fable 写合同 → Codex 实现／机器闸（每轮最多 2 次）→ Opus 审核（最多 2 轮）。机器闸失败和审核打回都会把原因带进下一次实现。
- `complex`：Fable 写合同和可演示 stories → Codex 按 story 串行实现（每条复用中等任务的 2 次实现／机器闸上限）→ Opus 审核。

实现模型固定为 `gpt-5.3-codex-spark`，审核模型固定为 `opus`；重试也绝不换更贵的模型。到达上述硬上限、任何模型调用失败或审核仍打回时，流程停止并在 `router/runs/` 写明原因。没有并发或 Telegram 告警。Fable 与 Opus 的 CLI 回执成本、以及 Codex 调用前后从既有只读 collector 得到的增量成本，写入本地 append-only `router/ledger.jsonl`。两者均为运行数据，不进 Git；因此 `--dry-run` 仍会留下路由收据，但绝不修改目标工作区。

仓库边界不允许安装同名的全局裸 `tr` 命令（系统已有该文本转换命令）；本轮安全入口是上面的 `python3 -m router`。裸命令的安装决策已记录在 `BLOCKED.md`。

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

## 质量闸

改动前后各跑一次，一条命令回答「这仓库现在健康吗」：

```bash
bash scripts/check.sh              # 红了就别提交
bash scripts/check.sh --fix-hint   # 每种失败怎么修
```

检查六项：python 测试（21 例）、node 页面测试（17 例）、账本不变量（归类合计 == 全量合计）、
快照不变量（每份快照内部自洽）、工作树干净、gitleaks 无泄漏。任一失败即非零退出并指明是哪项。

页面纯函数在 `assets/pure.js`（`money` / `esc` / `validateStatus` / `sparkPoints`），
node 零依赖直接跑测试；`esc()` 逃逸引号，守着「agent 写的数据渲染进页面」这条信任边界。

## 定时刷新与趋势

一条命令刷新全部四份数据:

```bash
bash scripts/refresh.sh   # ledger.json → outputs.json → snapshots/<日期>.json → trend.json
```

`set -euo pipefail` + 原子写(先写 `.tmp` 再 `mv`):任一步失败即非零退出、错误进 stderr,**且不会毁掉上一次的好文件**。

**自动化(可选,需你确认后自己装)**:每天凌晨刷新的 launchd 模板在 `scripts/com.wendy.tokenrouter-refresh.plist`。装载:

```bash
cp scripts/com.wendy.tokenrouter-refresh.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.wendy.tokenrouter-refresh.plist
launchctl kickstart -k gui/$(id -u)/com.wendy.tokenrouter-refresh   # 立即试跑一次
```

**快照 vs 派生数据的关键区别**:`ledger.json`/`outputs.json`/`trend.json` 是派生数据(随时可重算,已 gitignore);
`snapshots/<日期>.json` 是**历史事实**——会话日志会滚动清理,过去某天的数字之后重算不出来,所以快照**入库**。
趋势只能从开始留快照那天算起,越早跑越早有数据。

项目分组与 repo 路径都在 `ledger/registry.py`——加新项目只改 registry，页面自动跟随。
