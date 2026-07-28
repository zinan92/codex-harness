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
