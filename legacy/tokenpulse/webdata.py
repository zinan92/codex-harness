"""Data bridge for the web goad-widget.

Merges three sources into one payload the UI renders from:
  - core.status()        → today's tokens vs target + pace + mood (THE GOAD signal)
  - limits.plan_limits() → session / weekly % left + reset (CodexBar feed)
  - cost.usage_summary() → today/30d cost, 30d/today tokens (models.dev rates)

Split into a fast core() (goal+limits, renders the emotional state instantly) and
a slow cost() (30-day scan, TTL-cached) so the widget never blocks on cost.

Pure stdlib.
"""
from __future__ import annotations

from datetime import datetime

import core
import cost
import history
import limits

TOOLS = ("claude", "codex")

_SOURCE_LABELS = {
    "claude-jsonl": "Claude 本地日志",
    "codexbar": "CodexBar 本地扫描",
    "codex-jsonl": "Codex 本地日志",
    "codexbar-unavailable": "CodexBar 本地扫描",
}


def _provenance(tool: str, data: dict, now: datetime, boundary: str) -> dict:
    """A small, UI-safe receipt for every displayed usage number."""
    receipt = data.get("breakdown") if isinstance(data.get("breakdown"), dict) else {}
    source = receipt.get("source") or ("claude-jsonl" if tool == "claude" else "codex-jsonl")
    available = receipt.get("available", True)
    stale = bool(receipt.get("stale"))
    status = "unavailable" if not available else ("stale" if stale else "fresh")
    zone = "UTC" if boundary == "utc" else "本地时区"
    return {
        "provider": "Claude" if tool == "claude" else "Codex",
        "source": source,
        "source_label": _SOURCE_LABELS.get(source, "本地用量扫描"),
        "scope": f"今日 · {zone}",
        "refreshed_at": now.isoformat(),
        "status": status,
        "reason": receipt.get("reason") if status == "unavailable" else None,
    }


def _state(mood: str) -> str:
    """Map core's mood to a UI state name."""
    return {"behind": "behind", "ontrack": "ontrack", "ahead": "ahead",
            "done": "hit", "rocket": "rocket"}.get(mood, "ontrack")


def _operator_line(st: dict) -> str:
    tools = list(st["tools"].values())
    remaining = core.humanize(st["combined"]["remaining"])
    if all(t["hit"] for t in tools):
        return "complete - daily target is done; choose the next AI-work session by priority."
    if any(t["mood"] == "behind" for t in tools):
        return f"behind - start the next AI-work session now to catch up; {remaining} tokens remain today."
    return f"on track - keep the next AI-work session aligned to priority; {remaining} tokens remain today."


def _impact_line(st: dict) -> str:
    tools = list(st["tools"].values())
    if all(t["hit"] for t in tools):
        return "priority decides because today's token target is done."
    if any(t["mood"] == "behind" for t in tools):
        return "turn lag into useful AI-work before the day slips."
    return "stay on the priority session while runway is healthy."


def _daily_decision(scope: str, data: dict, unavailable: bool = False) -> dict:
    """Turn a trusted pace state into one concrete, non-automated next move."""
    label = {"combined": "合计", "claude": "Claude", "codex": "Codex"}.get(scope, scope)
    if unavailable:
        return {
            "question": "今天下一步",
            "action": "先等待可信本地扫描完成",
            "reason": f"{label} 数据未完整，不能把未读取当作 0 来安排工作。",
            "pace": "数据状态：未读取",
        }
    state = data.get("state") or "ontrack"
    target = core.humanize(int(data.get("target") or 0))
    if state == "early":
        return {
            "question": "今天下一步",
            "action": "先选定一个可验收的 AI 工作产出",
            "reason": "活跃工作窗口尚未开始；先确定要交付什么，再开始会话。",
            "pace": f"今日目标 {target} · 尚未开始计速",
        }
    if state == "behind":
        deficit = core.humanize(int(data.get("deficit") or 0))
        return {
            "question": "今天下一步",
            "action": "启动下一段专注工作，完成一个可交付物",
            "reason": f"当前比节奏少 {deficit}；先把下一段收敛到一个明确结果。",
            "pace": f"{label} · 落后配速",
        }
    if state in {"done", "hit", "rocket"}:
        return {
            "question": "今天下一步",
            "action": "写下今天已完成的产出，再选明天的第一步",
            "reason": "今日目标已达成；接下来由优先级决定，不再由额度压力决定。",
            "pace": f"{label} · 今日已达标",
        }
    if state == "ahead":
        return {
            "question": "今天下一步",
            "action": "保持当前优先级，收尾一个可交付物",
            "reason": "当前领先配速；不要为了数字切换到低价值工作。",
            "pace": f"{label} · 领先配速",
        }
    return {
        "question": "今天下一步",
        "action": "继续当前优先级，完成下一个可交付物",
        "reason": "配速健康；把注意力留在最重要的工作上。",
        "pace": f"{label} · 配速正常",
    }


def core_payload(now: datetime | None = None, config: dict | None = None) -> dict:
    now = now or datetime.now().astimezone()
    config = config or core.load_config()
    st = core.status(now=now, config=config)
    pl = limits.plan_limits()
    boundary = config.get("day_boundary", "local")

    tools = {}
    for t in TOOLS:
        d = st["tools"][t]
        info = pl.get(t, {})
        sess = limits.window(info, "session") if info.get("available") else None
        week = limits.window(info, "weekly") if info.get("available") else None
        tools[t] = {
            "today": d["today"],
            "target": d["target"],
            "percent": d["percent"],
            "expected": d["expected_by_now"],
            "deficit": d["deficit_vs_pace"],
            "remaining": d["remaining"],
            "active_fraction": d["active_fraction"],
            "hit": d["hit"],
            "state": _state(d["mood"]),
            "pace_ratio": round(d["today"] / d["expected_by_now"], 2) if d["expected_by_now"] else None,
            "session": {"left": sess["left_percent"], "reset": sess["reset_in"]} if sess else None,
            "weekly": {"left": week["left_percent"], "reset": week["reset_in"]} if week else None,
            "plan_available": bool(info.get("available")),
            "plan_stale": bool(info.get("stale")),
            "provenance": _provenance(t, d, now, boundary),
        }

    c = st["combined"]
    expected = sum(t["expected"] for t in tools.values())
    p = core.pace(now, config, c["today"], c["target"])
    frac = round(core._active_fraction(now, config), 3)
    # Outside the active earning window (e.g. before 09:00 / overnight) pace is
    # undefined — expected is 0, so "ahead" would be a lie. Surface "early".
    state = _state(p["mood"])
    if frac <= 0 and not p["hit"]:
        state = "early"
    out = {
        "generated_at": now.isoformat(),
        "clock": now.strftime("%H:%M"),
        "active_fraction": frac,
        "combined": {
            "today": c["today"],
            "target": c["target"],
            "percent": c["percent"],
            "remaining": c["remaining"],
            "expected": expected,
            "deficit": max(0, expected - c["today"]),
            "state": state,
            "hit": p["hit"],
            "pace_ratio": round(c["today"] / expected, 2) if expected else None,
            "operator": _operator_line(st),
            "impact": _impact_line(st),
        },
        "tools": tools,
    }
    out["decisions"] = {
        "combined": _daily_decision(
            "combined", out["combined"],
            unavailable=any(t["provenance"]["status"] == "unavailable" for t in tools.values()),
        ),
        **{
            tool: _daily_decision(tool, data, unavailable=data["provenance"]["status"] == "unavailable")
            for tool, data in tools.items()
        },
    }
    return out


def cost_payload(config: dict | None = None) -> dict:
    """Per-tool cost/token aggregates + the combined 30-day spend (Claude + Codex
    API-equivalent cost) — shown as the headline "this month's burn" badge."""
    out = {}
    total_cost = 0.0
    for t in TOOLS:
        s = cost.usage_summary(t)
        out[t] = {
            "cost_today": round(s["cost_today"], 2),
            "cost_30d": round(s["cost_30d"], 2),
            "tokens_30d": s["tokens_30d"],
            "tokens_today": s["tokens_today"],
        }
        total_cost += s["cost_30d"]
    out["combined"] = {"cost_30d": round(total_cost, 2)}
    return out


def panel_payload(config: dict | None = None) -> dict:
    """30-day usage series + today's active time + streak/best — for the expand
    panel. Heavy (30-day scan); TTL-cached inside history.panel_data()."""
    return history.panel_data(config=config)


if __name__ == "__main__":
    import json
    print(json.dumps({"core": core_payload(), "cost": cost_payload(),
                      "panel": panel_payload()}, indent=2, default=str))
