# Ledger progress

## 2026-07-29 · 可配置 workspace 机器闸 + fixture 实跑

- Task 0 baseline: `bash scripts/check.sh` exited 0 and `python3 -m unittest discover router/tests -v` passed 19/19 before this change.
- Machine gate is now workspace-configurable without a bypass: `MachineGate(command=None)` retains `config.MACHINE_GATE`; `--gate` is parsed with `shlex.split` into a command tuple; its subprocess exit code remains the sole pass/fail signal. Gate events now preserve the exact command for audit.
- Unit coverage: 3 new stubbed cases prove the default configured command, a custom command's actual execution, and CLI parsing/passing of `--gate "echo ok"`. Router suite passed 22/22 after the change.
- Fixture: `router/fixtures/demo_project/` is an isolated pure-function project with its own acceptance command, `python3 -m unittest discover tests -v`, rather than TokenRouter's `bash scripts/check.sh`.
- Real non-dry-run proof (canonical receipt `run-20260729T044728Z-958f8240`): workspace=`/Users/wendy/tokenrouter/router/fixtures/demo_project`; Fable triage=`simple` (62 cents) → Codex implementation=`ok` (41 cents) → gate command=`["python3", "-m", "unittest", "discover", "tests", "-v"]`, exit 0 → Opus review=`pass` (111 cents) → final status=`succeeded`; recorded total=214 cents. Codex changed `greeting(name)` to return `Welcome, {name}!` and synchronized the fixture's exact-return unittest assertion.
- The initial direct call, `run-20260729T044502Z-088fc522`, also completed successfully after its terminal wrapper returned early: simple triage 99 cents → developer 24 cents → the same fixture gate exit 0 → reviewer pass 146 cents → succeeded (269 cents), changing `Hello` to `Welcome`. The canonical second run above made the final exclamation-mark change. This duplicate spend is retained as fact, not represented as a retry or a gate failure.
- Protected-path checks before and after the real calls are clean: `git diff --exit-code -- ledger scripts assets workbench.html ARCHITECTURE.md CLAUDE.md`; no TokenRouter `scripts/check.sh`, legacy `ledger/`, or `snapshots/` file was changed by the fixture runs.

## 2026-07-29 · TokenRouter retry + real-run evidence

- Task 0 baseline: `bash scripts/check.sh` exited 0 (23 Python, 17 Node, ledger/snapshot invariants, clean tree, gitleaks); `python3 -m unittest discover router/tests -v` passed 5/5 before this change.
- Goal: complete both missing original acceptance items in one delivery: fixed retry limits with feedback, then two real non-dry-run runs that exercise simple and medium SOPs.
- Chain: implement constants/prompt/workflow retries → replace conflicting router tests and prove four retry cases → run B1/B2 with real Fable/Codex/Opus → record evidence and final protected-path check.
- Maximum risk: a real model can make an out-of-scope edit or a real B2 can pass first try; use narrow router-only prompts, inspect each receipt, and report an untriggered retry honestly.
- Task A complete: added `SIMPLE_MAX_ATTEMPTS = 2`, `MEDIUM_IMPL_MAX_ATTEMPTS = 2`, and `MEDIUM_REVIEW_MAX_ROUNDS = 2`; failures feed gate output or review summary/evidence into the next fixed-model developer prompt. Router tests are 9/9, including all four requested retry scenarios; commit `2276d60`.
- Gate compatibility decision: the fixed `bash scripts/check.sh` rejects an edited working tree, while the original developer prompt prohibited commits. To permit genuine implement → gate → review runs without changing the gate, the prompt now permits a scoped **local** commit only when the assignment explicitly requires it; no push, deletion, or permission change is permitted. Commit `4e5133f`.
- B1 real run `run-20260729T024629Z-d05dc3a4` (non-dry-run): Fable triage=`simple` (96 cents) → Spark developer attempt 1=`ok` (28 cents) → machine gate=`ok` → Opus review round 1=`pass` (120 cents) → `succeeded`; total recorded cost 244 cents. The real task added the `Review.from_response` docstring and committed only `router/schema.py` as `cac9930`.
- B2 real run `run-20260729T025001Z-5db91080` (non-dry-run): Fable triage=`medium` with contract (63 cents) → Spark developer round 1/attempt 1=`ok` (40 cents) → machine gate=`ok` → Opus review round 1=`pass` (137 cents) → `succeeded`; total recorded cost 240 cents. The real task added normalized-duplicate rejection for all four Contract list fields and regressions, committed only `router/schema.py` and `router/tests/test_router.py` as `fc8efe8`.
- B2 first passed, so its real receipt contains one developer call and no retry event. This is not presented as retry evidence; the retry path remains covered by the deterministic unit tests. No artificial gate failure was introduced.
- Post-B2 direct verification: `python3 -m unittest discover router/tests -v` passed 11/11. Final protected-path and full quality-gate verification are next.

## 2026-07-29 · 5 条真实记录补齐（进行中）

- Task 0 baseline complete: `bash scripts/check.sh` exited 0 and `python3 -m unittest discover router/tests -v` passed 11/11 before this round.
- B3 real run `run-20260729T030604Z-86ed3383`: Fable classified the intentionally multi-part task as `complex`; Spark executed all 4 stories serially and every story machine gate passed; Opus returned `failed_review`. The failure is real and retained: first commit `dbc36eb` bundled the summary module, CLI, README, and a test file instead of one scoped commit per story. It is not counted as a successful complex closure and is recorded in `BLOCKED.md`; no receipt or protected path was changed.
- B4 real run `run-20260729T031701Z-585e623f`: Fable triage=`medium` (65¢) → Spark (58¢) → machine gate=`ok` → Opus=`pass` (142¢) → `succeeded`, 265¢ total. It made `aggregate_runs` return the canonical zero summary for missing/non-directory inputs and added focused regression tests in scoped commit `957df62`.
- B5 real run `run-20260729T032308Z-87008e8b`: Fable triage=`simple` (60¢) → Spark (15¢) → machine gate=`ok` → Opus=`pass` (102¢) → `succeeded`, 177¢ total. It added exactly the `_empty_summary` docstring in scoped commit `7fe5b7c`.
- Task 6 acceptance complete: `python3 -m router --summary` reports 5 completed non-dry-run receipts: `simple=2`, `medium=2`, `complex=1`; statuses `succeeded=4`, `failed_review=1`; total recorded cost 1,497¢. The failed complex run is counted as a real record but never represented as success.
- Final verification: router tests 19/19, `bash scripts/check.sh` all green, and the protected-path diff command is empty. Next: commit this final progress receipt only; do not alter the retained B3 blocker.

## 2026-07-29 · TokenRouter v0 执行

- Task 0 已执行：`codex --version` = 0.146.0，`claude --version` = 2.1.218，均满足最低版本。
- `bash scripts/check.sh` 的五项可运行检查均通过；仅因动工前已有 `snapshots/2026-07-29.json` 未提交改动而以 1 退出。该受保护路径不在本任务允许范围，已记入 `BLOCKED.md`，未修改、未清理。
- 下一项：仅在 `router/` 实现串行 v0（Fable 分诊/合同，Codex 实现，机器闸，Opus 审核，事后账本）；不做告警、并发、历史成功率路由或失败升级。
- 已完成实现：新增标准库 `router` 包和 `python3 -m router` CLI；Fable 对每个任务做 `simple`/`medium`/`complex` 判断，中等/复杂任务强制结构化合同，复杂任务强制串行 stories；Codex 固定实现、既有 `bash scripts/check.sh` 固定机器闸、Opus 固定只读审核。所有失败立即停止并记入独立的本地运行收据；Codex 成本从现有只读 collector 的调用前后差额记账。
- 已完成测试：`/usr/local/bin/python3 -m unittest discover router/tests -v` 通过 5/5；`compileall`、CLI `--help` 与空白检查通过。真实 `--dry-run` 已调用本机 Fable：成功分到 `medium`，写出有效合同与运行收据，直接回执成本为 94¢；未调用 Codex/Opus、未改目标工作区。
- 最终验证完成：ledger 13/13、scripts 10/10、router 5/5、Node 17/17 全绿；`git diff --exit-code -- ledger scripts assets workbench.html` 与 `ARCHITECTURE.md`/`CLAUDE.md` 保护核验均为空。完整质量闸的其余五项均绿，唯一失败是工作树未提交状态（本轮待交付文件 + 动工前已有的 `snapshots/2026-07-29.json`）。
- 交付已提交：`feat(router): add fixed local model workflow`。提交仅含 `router/`、`README.md`、`PROGRESS.md`、`BLOCKED.md`；`snapshots/2026-07-29.json` 仍是动工前原样保留的唯一未提交改动。
- 收尾：提交此状态记录后重跑质量闸。预期唯一失败仍是上述受保护快照脏改动；无需、也不得为此修改快照。

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
