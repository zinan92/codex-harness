"""读 snapshots/*.json,输出每个项目与总额的时间序列 → trend.json + 人话表。

页面用 trend.json 画 sparkline;命令行直接看最近几天的总额走势。
只读快照,不碰日志——秒级返回。
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "snapshots"


def load_snapshots():
    if not SNAP_DIR.exists():
        return []
    snaps = []
    for path in sorted(SNAP_DIR.glob("*.json")):
        try:
            snaps.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    snaps.sort(key=lambda s: s.get("date", ""))
    return snaps


def build_trend():
    snaps = load_snapshots()
    dates = [s["date"] for s in snaps]
    grand = [s["grand_total_cents"] for s in snaps]
    names = set()
    for s in snaps:
        names.update(s.get("projects", {}).keys())
    per_project = {}
    for name in sorted(names):
        per_project[name] = [
            s.get("projects", {}).get(name, {}).get("cost_cents", 0) for s in snaps
        ]
    return {"dates": dates, "grand_total_cents": grand, "projects": per_project}


def main():
    trend = build_trend()
    write = "--json" in sys.argv
    (ROOT / "trend.json").write_text(json.dumps(trend, ensure_ascii=False, indent=1))
    n = len(trend["dates"])
    if write:
        print(json.dumps(trend, ensure_ascii=False))
        return
    print(f"trend.json 已更新 · {n} 个快照")
    if n == 0:
        print("(暂无快照;跑 python3 scripts/snapshot.py 留第一份)")
        return
    if n == 1:
        print(f"只有 1 天({trend['dates'][0]}),趋势需要至少 2 个快照才看得出走势。")
    print("\n总额走势(最近):")
    for d, c in list(zip(trend["dates"], trend["grand_total_cents"]))[-7:]:
        print(f"  {d}  ${c/100:>10,.0f}")


if __name__ == "__main__":
    main()
