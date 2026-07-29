"""Conservative, longest-match project attribution for ledger source keys."""

from dataclasses import dataclass

UNCLASSIFIED = "未归类"


@dataclass(frozen=True)
class Project:
    name: str
    claude_prefixes: tuple[str, ...] = ()
    codex_prefixes: tuple[str, ...] = ()
    group: str = "其他"
    repo: str = ""          # 本地 git 仓库路径；空 = 无仓库或不在本机
    archived: bool = False  # 长期无碰且花费可忽略；页面折叠显示，账本仍计入总额


# Prefixes are deliberately specific.  A source that is not confidently
# identified stays visible in UNCLASSIFIED rather than being assigned broadly.
PROJECTS = (
    Project("tokenrouter", ("-Users-wendy-tokenrouter",), ("/Users/wendy/tokenrouter", "/Users/wendy/Documents/tokenrouter"), group="Agent OS", repo="/Users/wendy/tokenrouter"),
    # Claude 侧把 worktree 路径也算进本体：superpowers / codex 的 worktree 是同一个仓库的分身
    Project(
        "trading-orchestrator",
        ("-Users-wendy-trading-orchestrator",
         "-Users-wendy--config-superpowers-worktrees-trading-orchestrator"),
        ("/Users/wendy/trading-orchestrator",),
        group="交易",
        repo="/Users/wendy/trading-orchestrator",
    ),
    Project(
        "trading-system",
        ("-Users-wendy-work-trading-system",
         "-Users-wendy--codex-worktrees-trading-system"),
        ("/Users/wendy/work/trading-system",),
        group="交易",
        repo="/Users/wendy/work/trading-system",
    ),
    Project("trading-co", ("-Users-wendy-work-trading-co",), ("/Users/wendy/work/trading-co",), group="交易", repo="/Users/wendy/work/trading-co"),
    Project("input-to-park", ("-Users-wendy-work-input-to-park",), ("/Users/wendy/work/input-to-park",), group="Agent OS", repo="/Users/wendy/work/input-to-park"),
    Project("park-io", ("-Users-wendy-park-io",), ("/Users/wendy/park-io",), group="Agent OS"),
    Project("agent 自管理", ("-Users-wendy-Documents-agent---",), ("/Users/wendy/Documents/agent自管理",), group="Agent OS"),
    Project("人生 K 线", ("-Users-wendy-Documents---k-",), ("/Users/wendy/Documents/人生k线",), group="交易"),
    Project("New project", ("-Users-wendy-Documents-New-project",), ("/Users/wendy/Documents/New project",), group="内容"),
    # Claude 把中文目录名转义成等长横杠：投研面板=5 字→5 杠，电商工作台=6 字→6 杠。
    # 二者互为前缀，靠 project_for 的最长匹配区分；键名来自各自 jsonl 里的 cwd 字段，非推测。
    Project(
        "投研面板",
        ("-Users-wendy-Documents-----", "-private-tmp-equity-research"),
        ("/Users/wendy/Documents/投研面板",),
        group="交易",
    ),
    Project("电商工作台", ("-Users-wendy-Documents------",), ("/Users/wendy/Documents/电商工作台",), group="内容"),
    # 以下为 Codex 侧独占项目（Claude 侧无会话，故不设 claude 前缀——
    # 中文目录的短横杠前缀会误吞同长度的其他项目，宁可不归也不错归）
    Project("内容制作", (), ("/Users/wendy/Documents/内容制作", "/Users/wendy/Documents/内容生产"), group="内容"),
    Project("知识库", (), ("/Users/wendy/Documents/知识库",), group="内容"),
    Project("tokenpulse", (), ("/Users/wendy/work/tokenpulse", "/Users/wendy/Documents/tokenpulse"), group="交易", repo="/Users/wendy/work/tokenpulse"),
    # 以下 archived=True：2026-07-29 复核——花费个位数（<$20）且账本/git 双信号均已停摆一个月以上。
    # trading-system、tokenpulse 花费同样低但 git 近期高频提交（多为 bot/其他机器），不算停摆，未归档。
    Project("a股情报", (), ("/Users/wendy/Documents/a股情报newsletter",), group="交易", archived=True),
    Project("个人助理", (), ("/Users/wendy/Documents/个人助理",), group="Agent OS", archived=True),
    Project("产品工厂", (), ("/Users/wendy/Documents/产品工厂",), group="内容"),
    Project("关系管理", (), ("/Users/wendy/Documents/关系管理",), group="Agent OS", archived=True),
    Project("repo-evals", ("-Users-wendy-work-repo-evals",), ("/Users/wendy/repo-evals",), group="Agent OS", archived=True),
    Project("content-ops", ("-Users-wendy-work-content-ops",), ("/Users/wendy/work/content-ops",), group="内容", repo="/Users/wendy/work/content-ops", archived=True),
    Project("content-toolkit", ("-Users-wendy-content-toolkit",), ("/Users/wendy/content-toolkit",), group="内容", archived=True),
    Project("videocut", ("-Users-wendy-videocut",), ("/Users/wendy/videocut",), group="内容", archived=True),
)


def project_for(source_key, channel, projects=PROJECTS):
    """Choose one project for a source key; longest matching prefix wins."""
    candidates = []
    for project in projects:
        prefixes = project.claude_prefixes if channel == "claude" else project.codex_prefixes
        for prefix in prefixes:
            if source_key.startswith(prefix):
                candidates.append((len(prefix), project.name))
    if not candidates:
        return UNCLASSIFIED
    longest = max(length for length, _ in candidates)
    names = {name for length, name in candidates if length == longest}
    if len(names) != 1:
        raise ValueError("ambiguous project prefixes for {!r}: {}".format(source_key, sorted(names)))
    return names.pop()


def aggregate(records, projects=PROJECTS):
    """Aggregate every record exactly once, preserving the total in whole cents."""
    totals = {
        project.name: {"name": project.name, "group": project.group,
                       "archived": project.archived,
                       "claude_cents": 0, "codex_cents": 0,
                       "cost_cents": 0, "records": 0}
        for project in projects
    }
    totals[UNCLASSIFIED] = {"name": UNCLASSIFIED, "group": "未归类",
                            "archived": False,
                            "claude_cents": 0, "codex_cents": 0,
                            "cost_cents": 0, "records": 0}
    for record in records:
        channel = record["channel"]
        project = project_for(record["source_key"], channel, projects)
        cents = record["cost_cents"]
        bucket = totals[project]
        bucket["cost_cents"] += cents
        bucket["{}_cents".format(channel)] += cents
        bucket["records"] += 1
    rows = [totals[project.name] for project in projects] + [totals[UNCLASSIFIED]]
    grand_total_cents = sum(record["cost_cents"] for record in records)
    categorized_total_cents = sum(row["cost_cents"] for row in rows)
    if categorized_total_cents != grand_total_cents:
        raise AssertionError((categorized_total_cents, grand_total_cents))
    return rows, grand_total_cents
