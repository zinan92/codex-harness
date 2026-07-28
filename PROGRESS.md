# Ledger progress

- Task 0 complete (2026-07-28): source counts verified: Claude 106 directories; Codex 889 JSONL files (within the stated tolerance).
- Goal: build a standard-library, reproducible local cost ledger by project and channel, with explicit unclassified coverage.
- Order: lock Codex final-cumulative extraction; collect Claude; assign each source key once; report and gaps; fixture tests plus mutation proof.
- Maximum risk: Codex `total_token_usage` is cumulative, so summing JSONL events silently inflates spend; collection must retain only each file's final usable total.
- Task 1 complete: `collect` emits normalized Claude events and exactly one Codex record per scanned JSONL, retaining only the file's final cumulative usage. Acceptance output: `889 106`.
- Task 2 complete: conservative longest-prefix attribution assigns every normalized record once; all unmatched sources go to `未归类`. Invariant acceptance output: `INVARIANT OK 1920872`.
- Task 3 complete: human report now prints project, Claude, Codex, and total columns, renders zero amounts as `无日志`, and ends with the no-log count plus `未归类` amount share. Tail acceptance includes both required terms.
- Task 4 complete: three fixture-only tests cover final Codex cumulative extraction, longest-prefix no-loss attribution, and `未归类` fallback. Mutation proof: changing Codex extraction to sum produced `AssertionError: 90 != 60`; restoring final-only extraction produced `Ran 3 tests ... OK`.
- Final verification complete: fresh full scan printed `INVARIANT OK 1920912`; fixture suite printed `Ran 3 tests ... OK`; protected-path diff with explicit `--` was empty and exited 0. The strict unseparated protected-file command remains blocked only because both specified files are absent, as recorded in `BLOCKED.md`.

## 2026-07-28 · 合仓 + registry 补全（管理者直接执行）

- 账本从 `~/Documents/tokenrouter` 迁入本仓，两个仓库合一；`tokenrouter` 自身的 codex 前缀保留新旧两个路径。
- registry 从 14 个项目扩到 22 个。所有新键均由各自 jsonl 的 `cwd` 字段实测解析，无推测。
- 修正一处 bug：投研面板的 Claude 前缀原为 `-Users-wendy-Documents-equity-research`，实际键是 `-Users-wendy-Documents-----`（Claude 把中文目录名转义成等长横杠），原映射从未命中。
- Claude 侧把 superpowers / codex 的 worktree 路径并入其本体仓库。
- 未归类占比 26.64% → 2.11%；余下 $405 主要是 `/Users/wendy` 根目录会话，无法归属，如实留在未归类。
- 刻意不给「内容制作」等 Codex 独占项目设 Claude 前缀：中文目录的短横杠前缀会误吞同长度的其他项目，宁可不归也不错归。

---

## 2026-07-28/29 · v1.0 成熟化(无人值守连续开发)

计划见 `~/.claude/plans/noble-squishing-ullman.md`。用户 approve 后连续执行 7 个阶段,中途未打断。

### 阶段 1 · 补齐测试网(测试 3 → 38)
此前 `report.py`、`scripts/*`、页面 JS 三层零覆盖。
- `ledger/tests/test_time_stats.py`(7):小时桶去重、跨天范围、空记录、畸形 hour、按项目路由、无法解析计数
- `scripts/tests/test_scripts.py`(10):build_trend 排序与中途出现补零对齐、快照自身不变量、stats_for 的 git 输出解析(打桩,不跑真 git)
- `assets/pure.js` + `assets/tests/pure.test.js`(17):money/esc/validateStatus/sparkPoints 抽成纯函数
  - **`esc()` 从 DOM 实现改为纯字符串实现**——原 DOM 版正是引号漏洞的根源
  - 页面改用 `Pure.*`,消除重复实现

### 阶段 2 · 质量闸 `scripts/check.sh`
六项检查一条命令。**反向验证**:注入 +999.99 差异 → 精确报「账本不变量」失败、退出码 1 → 恢复 → 全绿。不是假绿灯。

### 阶段 3 · 修静默失败
`_hour_bucket` 与 Codex 文件名解析对畸形输入都返回空串——不崩,但**毫无信号**。日志格式一变(如 Codex 改文件命名),活跃天数/小时会静默归零。
- 改为返回无法解析的记录数,冒泡到 `coverage.records_without_time`
- 人话报告:0 条时报「全部可解析」,>0 时警告并给占比
- 实测当前 51,657 条全部可解析;反向验证 7/10 失败时确实报警
- 另:`build_trend` 补零对齐与 `stats_for` 空仓库处理经测试确认**原实现正确,无需修改**

### 阶段 4 · 趋势 sparkline
纯 SVG 无外部库。**< 2 天数据时显示「趋势需要至少 2 天(当前 N 天)」,不画假线**。
验证方式:临时造 3 份假快照确认曲线正确(4 点均匀、低值贴底高值贴顶、tooltip 逐日),**验证后立刻删除,不污染真实历史**。

### 阶段 5 · launchd 已装载
`com.wendy.tokenrouter-refresh` 装入 `~/Library/LaunchAgents` 并 load。kickstart 实测:退出码 0、stdout 有完整输出、stderr 空、快照 `generated_at` 确认由本次刷新产生。每天 3:15 自动跑。
顺带:`logs/` 改为不入库(每次运行都变的派生数据)。

### 阶段 6 · status 评估 1/22 → 5/22
只读各项目仓库,只写本仓 `status/`。每条 note 溯源到具体文件,读不到写「未查证」。
- **投研面板**(7 模块):数据基座/证据摄取最成熟;瓶颈 = N2 规范化建模
- **内容制作**(5 模块):**实为研究/决策工作区而非软件产品**(git 零提交),模块按研究完成度拆;瓶颈 = TradingView 申请需本人签署 License + 159 项产出未版本化
- **New project**(7 模块):跨项目调度台;瓶颈 = loop 引擎开关仍 OFF、**简报已停更 44 天**
- **input-to-park**(6 模块):每日稳定出刊;瓶颈 = 源健康告警(自述「单源故障靠人肉发现」)

### 本轮挖出并修复的缺陷
1. 时间解析静默失败(阶段 3)——已改为可见指标
2. `logs/` 误入库——已 gitignore

### 数据口径变化
无。定价、归类、不变量口径均未动;金额变化仅来自日志自然增长。
