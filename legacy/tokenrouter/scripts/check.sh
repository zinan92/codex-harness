#!/bin/bash
# 质量闸:回答「这仓库现在健康吗」。任一项失败即非零退出并指明是哪项。
# 改代码前后都该跑一次。--fix-hint 看每种失败怎么办。
set -uo pipefail          # 故意不用 -e:要跑完所有检查再汇总,而不是第一项失败就退

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/usr/local/bin/python3"
cd "$ROOT"

if [[ "${1:-}" == "--fix-hint" ]]; then
  cat <<'HINT'
质量闸各项失败时怎么办:

1 python 测试        跑 python3 -m unittest discover ledger/tests -v 看是哪个用例;
                     改了 collect.py/registry.py/prices.py 后失败通常是真回归。
2 node 测试          跑 node assets/tests/pure.test.js 看失败用例;
                     esc 相关失败=安全回归,优先修。
3 账本不变量         归类合计 != 全量,说明 registry 归类重复或丢失记录。
                     查 registry.py 是否有重叠前缀(project_for 会对歧义抛错)。
4 快照不变量         某份快照内部项目合计对不上自己的总额,该快照已损坏。
                     它是历史事实不可重算——先看 git log 确认是否被误改。
5 判卷文件           工作树有未提交改动。先 git status 看是不是你自己改的。
6 gitleaks           有凭证泄漏风险,立刻查 gitleaks detect --verbose。
HINT
  exit 0
fi

FAILED=()
pass(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
fail(){ printf '  \033[31m✗\033[0m %s\n' "$1"; FAILED+=("$1"); }

echo "质量闸 · $(date '+%Y-%m-%d %H:%M:%S')"

# 1 python 测试(ledger + scripts)
if "$PY" -m unittest discover ledger/tests >/tmp/_chk_led 2>&1 \
   && "$PY" -m unittest discover scripts/tests >/tmp/_chk_scr 2>&1; then
  n=$(( $(grep -oE 'Ran [0-9]+' /tmp/_chk_led | grep -oE '[0-9]+') \
      + $(grep -oE 'Ran [0-9]+' /tmp/_chk_scr | grep -oE '[0-9]+') ))
  pass "python 测试 ($n 个用例)"
else
  fail "python 测试 —— 见 /tmp/_chk_led 与 /tmp/_chk_scr"
fi

# 2 node 页面纯函数测试
if command -v node >/dev/null 2>&1; then
  if out=$(node assets/tests/pure.test.js 2>&1); then
    pass "node 测试 (${out#OK  })"
  else
    fail "node 测试 —— $out"
  fi
else
  echo "  - node 未安装,跳过页面测试"
fi

# 3 账本不变量:归类合计 == 全量合计
if [[ -f ledger.json ]]; then
  if "$PY" - <<'EOF' >/dev/null 2>&1
import json, sys
d = json.load(open("ledger.json"))
a = sum(p["cost_cents"] for p in d["projects"])
sys.exit(0 if a == d["grand_total_cents"] else 1)
EOF
  then pass "账本不变量(归类合计 == 全量合计)"
  else fail "账本不变量 —— 归类合计 != 全量合计"; fi
else
  echo "  - ledger.json 不存在,跳过(跑 bash scripts/refresh.sh 生成)"
fi

# 4 快照不变量:每份快照内部自洽
if compgen -G "snapshots/*.json" >/dev/null; then
  if "$PY" - <<'EOF' >/tmp/_chk_snap 2>&1
import glob, json, sys
bad = []
for path in sorted(glob.glob("snapshots/*.json")):
    snap = json.load(open(path))
    total = sum(p["cost_cents"] for p in snap["projects"].values())
    if total != snap["grand_total_cents"]:
        bad.append(f"{path}: {total} != {snap['grand_total_cents']}")
if bad:
    print("\n".join(bad)); sys.exit(1)
print(len(glob.glob("snapshots/*.json")))
EOF
  then pass "快照不变量 ($(cat /tmp/_chk_snap) 份自洽)"
  else fail "快照不变量 —— $(cat /tmp/_chk_snap)"; fi
else
  echo "  - 暂无快照,跳过"
fi

# 5 判卷文件未被篡改(工作树干净)
if [[ -z "$(git status --porcelain)" ]]; then
  pass "工作树干净"
else
  fail "工作树有 $(git status --porcelain | wc -l | tr -d ' ') 处未提交改动"
fi

# 6 秘密泄漏
if command -v gitleaks >/dev/null 2>&1; then
  if gitleaks detect --no-banner >/tmp/_chk_leak 2>&1; then
    pass "gitleaks 无泄漏"
  else
    fail "gitleaks 发现泄漏 —— 见 /tmp/_chk_leak"
  fi
else
  echo "  - gitleaks 未安装,跳过泄漏扫描"
fi

echo
if (( ${#FAILED[@]} )); then
  printf '\033[31m不健康:%d 项失败\033[0m\n' "${#FAILED[@]}"
  printf '  · %s\n' "${FAILED[@]}"
  echo "怎么修:bash scripts/check.sh --fix-hint"
  exit 1
fi
printf '\033[32m全部通过\033[0m\n'
