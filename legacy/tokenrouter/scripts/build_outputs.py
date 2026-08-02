"""Per-project git output stats → outputs.json.

机械性数据（PR 数、提交数、昨日合并），每次刷新重算；
判断性数据（模块进度、下一步）在 status/<项目>.json，由 agent 评估，不在这里。
"""

import datetime
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from ledger.registry import PROJECTS  # noqa: E402


def _git(repo: str, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True, text=True, timeout=30,
        )
        return done.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def stats_for(repo: str) -> dict | None:
    if not repo or not pathlib.Path(repo, ".git").is_dir():
        return None
    merges = _git(repo, "log", "--merges", "--oneline")
    merged_prs = sum(1 for line in merges.splitlines() if "Merge pull request" in line)
    commits_30d = len(_git(repo, "log", "--since=30 days ago", "--oneline").splitlines())
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    merged_yesterday = sum(
        1 for line in _git(
            repo, "log", "--merges",
            "--since", yesterday + " 00:00", "--until", yesterday + " 23:59",
            "--oneline",
        ).splitlines()
        if "Merge pull request" in line
    )
    last_merge = _git(repo, "log", "--merges", "-1", "--format=%s|%cs")
    last_commit_day = _git(repo, "log", "-1", "--format=%cs")
    subject, _, merge_day = last_merge.partition("|")
    pr_no = ""
    if "Merge pull request #" in subject:
        pr_no = subject.split("#", 1)[1].split(" ", 1)[0]
    return {
        "merged_prs": merged_prs,
        "commits_30d": commits_30d,
        "merged_yesterday": merged_yesterday,
        "last_merge_pr": pr_no or None,
        "last_merge_day": merge_day or None,
        "last_commit_day": last_commit_day or None,
    }


def main() -> None:
    projects = {}
    for project in PROJECTS:
        stats = stats_for(project.repo)
        if stats is not None:
            projects[project.name] = stats
    payload = {
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": "仅统计 registry 里带 repo 且本机存在的仓库；其余项目无此数据（≠ 无产出）。",
        "projects": projects,
    }
    out = pathlib.Path(__file__).resolve().parent.parent / "outputs.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"outputs.json: {len(projects)} 个项目")
    for name, stats in projects.items():
        print(f"  {name:<24} PR {stats['merged_prs']:>4}  30d 提交 {stats['commits_30d']:>4}  昨日合并 {stats['merged_yesterday']}")


if __name__ == "__main__":
    main()
