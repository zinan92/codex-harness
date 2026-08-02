"""把当前 ledger 存成一份每日快照 → snapshots/YYYY-MM-DD.json。

快照是历史事实,不是派生数据:会话日志会滚动清理,过去某天的数字之后可能
重算不出来。所以 snapshots/ 入库(版本化留存),与 gitignore 的 ledger.json 不同。

同一天多次运行 = 覆盖(取当天最终值)。只存项目级聚合,不存原始记录。
"""

import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ledger.report import build_report  # noqa: E402


def main() -> None:
    report = build_report()
    snap = {
        "date": datetime.date.today().isoformat(),
        "generated_at": report["generated_at"],
        "grand_total_cents": report["grand_total_cents"],
        # 只留每个项目的钱,趋势看的就是这个;模块/记录明细不进快照
        "projects": {
            p["name"]: {
                "cost_cents": p["cost_cents"],
                "claude_cents": p["claude_cents"],
                "codex_cents": p["codex_cents"],
                "active_days": p.get("active_days", 0),
            }
            for p in report["projects"]
        },
    }
    out_dir = ROOT / "snapshots"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{snap['date']}.json"
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=1))
    total = snap["grand_total_cents"] / 100
    print(f"snapshot {snap['date']}: ${total:,.0f} · {len(snap['projects'])} 个项目 → {out.name}")


if __name__ == "__main__":
    main()
