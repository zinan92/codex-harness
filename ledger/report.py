"""Project and channel cost report."""

import argparse
import json

from .collect import collect_all
from .registry import PROJECTS, UNCLASSIFIED, aggregate


def _attach_time_stats(projects, records):
    """Per project: first/last day, distinct active days and hours.

    「时间成本」按会话日志估算：active_hours = 有用量记录的自然小时数（去重），
    不是精确工时；Codex 只有会话起始时刻，粒度更粗。

    返回时间无法解析的记录数——日志格式一变（如 Codex 改文件命名），时间统计会
    静默归零，这个计数是唯一的信号，必须冒泡到 coverage 而不是烂在这里。
    """
    from .registry import project_for

    days = {project["name"]: set() for project in projects}
    hours = {project["name"]: set() for project in projects}
    undated = 0
    for record in records:
        hour = record.get("hour") or ""
        if not hour:
            undated += 1
            continue
        name = project_for(record["source_key"], record["channel"])
        days[name].add(hour[:10])
        hours[name].add(hour)
    for project in projects:
        project_days = sorted(days[project["name"]])
        project["first_day"] = project_days[0] if project_days else None
        project["last_day"] = project_days[-1] if project_days else None
        project["active_days"] = len(project_days)
        project["active_hours"] = len(hours[project["name"]])
    return undated


def build_report():
    import datetime

    collected = collect_all()
    records = collected["claude"]["records"] + collected["codex"]["records"]
    projects, grand_total_cents = aggregate(records)
    undated_records = _attach_time_stats(projects, records)
    unclassified = next(project for project in projects if project["name"] == UNCLASSIFIED)
    generated_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    no_log_projects = sum(
        1 for project in projects
        if project["name"] != UNCLASSIFIED and project["records"] == 0
    )
    return {
        "generated_at": generated_at,
        "projects": projects,
        "grand_total_cents": grand_total_cents,
        "coverage": {
            "registered_projects": len(PROJECTS),
            "no_log_projects": no_log_projects,
            "unclassified_cost_share": (
                unclassified["cost_cents"] / grand_total_cents if grand_total_cents else 0
            ),
            # 时间戳解析不了的记录数。>0 说明日志格式可能变了，时间统计已在悄悄失真。
            "records_without_time": undated_records,
            "records_total": len(records),
        },
        "sources": {
            "claude_dirs": collected["claude"]["dirs"],
            "codex_files": collected["codex"]["files"],
        },
    }


def _money(cents):
    return "无日志" if cents == 0 else "${:,.2f}".format(cents / 100)


def print_human_report(report):
    headers = ("项目", "Claude", "Codex", "合计")
    rows = [
        (project["name"], _money(project["claude_cents"]), _money(project["codex_cents"]),
         _money(project["cost_cents"]))
        for project in report["projects"]
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    def line(row):
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))
    print(line(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(line(row))
    print("\n全量合计: {}".format(_money(report["grand_total_cents"])))
    print("覆盖缺口:")
    print("- 无日志项目数: {}".format(report["coverage"]["no_log_projects"]))
    print("- 未归类金额占比: {:.2%}".format(report["coverage"]["unclassified_cost_share"]))
    undated = report["coverage"]["records_without_time"]
    total = report["coverage"]["records_total"]
    if undated:
        print("- ⚠ 时间无法解析: {} / {} 条（{:.1%}）——日志格式可能已变，"
              "活跃天数/小时被低估".format(undated, total, undated / total if total else 0))
    else:
        print("- 时间解析: {} 条全部可解析".format(total))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report local model spend by project.")
    parser.add_argument("--json", action="store_true", help="print machine-readable report")
    args = parser.parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return
    print_human_report(report)


if __name__ == "__main__":
    main()
