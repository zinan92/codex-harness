"""Local-only weekly review derived from usage and user-written outcomes."""
from __future__ import annotations

import history
import sessions


def review(series: list[dict], annotated: list[dict]) -> dict:
    """Build an honest weekly conclusion; tokens are activity, never output."""
    totals = [int(day.get("total") or 0) for day in series]
    total = sum(totals)
    active_days = sum(1 for value in totals if value > 0)
    outcomes = sum(1 for row in annotated if (row.get("annotation") or {}).get("outcome"))
    if total == 0:
        return {"total": 0, "active_days": 0, "outcomes": outcomes, "conclusion": "本周还没有可读取的本地用量。",
                "next_action": "完成一次 Claude 或 Codex 会话后，再回来复盘。", "state": "empty"}
    if active_days <= 2:
        return {"total": total, "active_days": active_days, "outcomes": outcomes,
                "conclusion": f"本周有 {active_days} 个活跃日，节奏仍不稳定。",
                "next_action": "为下一次专注会话先定义一个可验收产出，并在结束后记录它。", "state": "sparse"}
    if outcomes == 0:
        return {"total": total, "active_days": active_days, "outcomes": 0,
                "conclusion": f"本周有 {active_days} 个活跃日，但还没有记录实际产出。",
                "next_action": "先给本周最重要的一次会话补一条实际产出标记。", "state": "unlinked"}
    return {"total": total, "active_days": active_days, "outcomes": outcomes,
            "conclusion": f"本周有 {active_days} 个活跃日，并记录了 {outcomes} 条实际产出。",
            "next_action": "挑出一条最有价值的产出，明确下周要推进的下一步。", "state": "steady"}


def local_review() -> dict:
    data = history.daily_tokens(days=7)
    return review(data.get("series") or [], sessions.annotated_sessions(days=7, limit=50))
