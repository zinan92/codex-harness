#!/bin/bash
# 一次刷新:账本 → 产出 → 快照 → 趋势。launchd 每天调这一个脚本。
# 失败即非零退出,stderr 进 launchd 日志——不假装成功。
set -euo pipefail

ROOT="/Users/wendy/tokenrouter"
PY="/usr/local/bin/python3"
cd "$ROOT"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] refresh 开始"
# 写临时文件、成功后再原子替换——失败时不毁掉上一次的好 ledger.json
"$PY" -m ledger report --json > ledger.json.tmp
mv ledger.json.tmp ledger.json
"$PY" scripts/build_outputs.py
"$PY" scripts/snapshot.py       # 写 snapshots/YYYY-MM-DD.json(入库的历史事实)
"$PY" scripts/trend.py          # 刷 trend.json 供页面画 sparkline
echo "[$(date '+%Y-%m-%d %H:%M:%S')] refresh 完成"
