# tokenrouter · Agent 操作上下文

个人项目组合工作台：`workbench.html`（三栏静态页）+ `ledger/`（双通道成本账本）+ `status/`（agent 评估）+ `scripts/`（产出统计）。愿景文档 `ARCHITECTURE.md` 描述的是**未来的路由产品**，与当前代码不是一回事——别按它改现状。

## 不变量（违反即失败）

1. **归类合计 == 全量合计**（整数分）。`ledger/registry.py:aggregate` 里的断言是真闸门，不许注释、不许放宽。
2. **Codex 每文件只取最后一条 `total_token_usage`**（会话累计值，求和会静默放大数倍）。改 `collect.py` 前先跑 `python3 -m unittest discover ledger/tests`。
3. `~/.claude/` 与 `~/.codex/` 是数据源，**只读**。
4. **改代码前后各跑一次 `bash scripts/check.sh`**（测试 + 账本不变量 + 快照不变量 + 工作树 + 泄漏）。它红了就别提交；`bash scripts/check.sh --fix-hint` 说明每种失败怎么修。
5. **定价与 TokenPulse 同源**：`ledger/prices.py` 优先读 `~/Library/Caches/codexbar/model-pricing/models-dev-v1.json`（TokenPulse/CodexBar 每日维护的共享价表），缺失才回退离线标价。三个产品对同一 model 得同一价——别在 ledger 里另立价表。

## 边界

- `ledger.json` / `outputs.json` 是派生数据，已 gitignore——改数字改上游，不许手编这两个文件。
- `status/<项目>.json` 是**判断性评估**，入库；生成/刷新规矩见 `status/PROMPT.md`（百分比可以判断，note 里的事实必须可溯源）。
- 归类宁缺勿错：归不上进「未归类」，不许为好看硬塞。
- 页面纯函数（`money` / `esc` / `validateStatus` / `sparkPoints`）统一在 `assets/pure.js`，有 node 测试钉住——**别在页面里再写一份**。`esc()` 已逃逸引号，可安全用于属性位。
- 页面所有动态 innerHTML 必须过 `esc()`。
- 数据不足时说实话：趋势少于 2 天显示提示，不许画假线补位；无日志的项目显示「无日志」而非 `$0`。

## 常用命令

```bash
bash scripts/check.sh                            # 质量闸：改动前后各跑一次
bash scripts/refresh.sh                          # 刷全部数据（账本→产出→快照→趋势，约 40s）
python3 -m http.server 8790 --bind 127.0.0.1     # 本地看页面（fetch 需 HTTP）
node assets/tests/pure.test.js                   # 只跑页面纯函数测试
```

不设每日定时刷新。由 Park 显式发起 Good Night 时运行 `bash scripts/refresh.sh`，并把结果作为当天 Token 截止值的来源。
