# tokenrouter · Agent 操作上下文

个人项目组合工作台：`workbench.html`（三栏静态页）+ `ledger/`（双通道成本账本）+ `status/`（agent 评估）+ `scripts/`（产出统计）。愿景文档 `ARCHITECTURE.md` 描述的是**未来的路由产品**，与当前代码不是一回事——别按它改现状。

## 不变量（违反即失败）

1. **归类合计 == 全量合计**（整数分）。`ledger/registry.py:aggregate` 里的断言是真闸门，不许注释、不许放宽。
2. **Codex 每文件只取最后一条 `total_token_usage`**（会话累计值，求和会静默放大数倍）。改 `collect.py` 前先跑 `python3 -m unittest discover ledger/tests`。
3. `~/.claude/` 与 `~/.codex/` 是数据源，**只读**。

## 边界

- `ledger.json` / `outputs.json` 是派生数据，已 gitignore——改数字改上游，不许手编这两个文件。
- `status/<项目>.json` 是**判断性评估**，入库；生成/刷新规矩见 `status/PROMPT.md`（百分比可以判断，note 里的事实必须可溯源）。
- 归类宁缺勿错：归不上进「未归类」，不许为好看硬塞。
- 页面所有动态 innerHTML 必须过 `esc()`；往 HTML **属性位**（如 `title="…"`）拼接时注意 `esc()` 当前不逃逸双引号。

## 常用命令

```bash
python3 -m ledger report --json > ledger.json   # 刷账本（约 16s，全量扫描）
python3 scripts/build_outputs.py                 # 刷 git 产出
python3 -m unittest discover ledger/tests        # 3 个用例须全绿
python3 -m http.server 8790 --bind 127.0.0.1     # 本地看页面（fetch 需 HTTP）
```
