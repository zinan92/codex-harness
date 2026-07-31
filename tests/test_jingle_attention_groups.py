from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class AttentionGroupContractTests(unittest.TestCase):
    def test_replay_fixture_projects_to_one_actionable_card_per_project(self) -> None:
        data = json.loads((ROOT / "tests/fixtures/jingle-attention-work-units.json").read_text(encoding="utf-8"))
        latest: dict[tuple[str, str], dict[str, object]] = {}
        for unit in data["units"].values():
            key = (unit["provider"], unit["session_id"])
            if unit["started_at"] > latest.get(key, {}).get("started_at", -1):
                latest[key] = unit
        self.assertEqual({unit["id"] for unit in latest.values()}, {"cl-current", "cx-current", "cl-blocked", "unmapped-one", "unmapped-two"})
        self.assertNotIn("cl-old", {unit["id"] for unit in latest.values()})
        projects = json.loads((ROOT / "tests/fixtures/jingle-attention-projects.json").read_text(encoding="utf-8"))["projects"]

        def project_id(unit: dict[str, object]) -> str:
            for project in projects:
                for alias in project["aliases"]:
                    if alias.get("provider") in {None, unit["provider"]} and str(unit["cwd"]).startswith(alias["prefix"]):
                        return project["project_id"]
            return f"unmapped:{unit['cwd']}"

        def visible(unit: dict[str, object]) -> bool:
            identity = project_id(unit)
            return unit.get("provider") == "codex" and unit.get("needs_attention") is True and identity == "token-router"

        groups: dict[str, list[dict[str, object]]] = {}
        for unit in latest.values():
            if visible(unit):
                groups.setdefault(project_id(unit), []).append(unit)
        cards = {
            identity: max(items, key=lambda item: (item["state"] == "blocked", item["started_at"], item["id"]))
            for identity, items in groups.items()
        }
        self.assertEqual(set(cards), {"token-router"})
        self.assertEqual(cards["token-router"]["id"], "cx-current")
        self.assertEqual(len(cards), 1)

        unmapped_blocked = {"id": "unmapped-blocked", "state": "blocked", "needs_attention": True, "cwd": "/workspace/a/shared", "provider": "codex"}
        self.assertFalse(visible(unmapped_blocked))

    def test_native_model_uses_explicit_group_identity_and_supersession(self) -> None:
        source = (ROOT / "src/CodexNotificationSettings.swift").read_text(encoding="utf-8")
        self.assertIn('case projectID = "project_id"', source)
        self.assertIn('"unmapped:\\(normalized)"', source)
        self.assertIn("currentBySession", source)
        self.assertIn("attentionGroups", source)
        self.assertIn("var needsAttention: Bool", source)
        self.assertIn("guard let needsAttentionFlag else { return false }", source)
        self.assertIn('var attentionPrefix: String', source)
        self.assertIn('Text("\\(unit.attentionPrefix)', source)
        self.assertNotIn('Text("还在跑")', source)
        self.assertIn("struct ProjectPersona", source)
        self.assertIn("LinearGradient", source)
        self.assertIn("startPoint: UnitPoint(x: 0.15, y: 0)", source)
        self.assertIn("endPoint: UnitPoint(x: 0.85, y: 1)", source)
        self.assertIn("static let panelRadius: CGFloat = 18", source)
        self.assertIn("static let itemRadius: CGFloat = 11", source)
        self.assertNotIn(".ultraThinMaterial", source)
        self.assertIn("deliberately not translucent", source)
        self.assertIn("panel.isOpaque = false", source)
        self.assertIn("panel.backgroundColor = .clear", source)
        self.assertIn("var settlementLabel", source)
        self.assertIn("var waitingLabel", source)
        self.assertIn('Text(unit.settlementLabel)', source)
        self.assertNotIn('identity(for: $0).isMapped || $0.state == "blocked"', source)
        self.assertIn('private func preferredUnit(in items: [WorkUnit])', source)
        self.assertIn('units: [preferred]', source)
        self.assertNotIn('@State private var expanded = false', source)
        self.assertNotIn('Array(group.units.prefix(3))', source)
        self.assertNotIn('Button(expanded ? "收起" : "点开展开")', source)
        self.assertIn("var runningUnits", source)
        self.assertIn("by: { identity(for: $0).id }", source)
        self.assertIn("private var trackedCodexUnits", source)
        self.assertIn("private var liveProjectIDs", source)
        self.assertIn("!liveProjectIDs.contains(identity(for: $0).id)", source)
        self.assertIn("var todayTokenTotal: Int?", source)
        self.assertIn("var featuredAttentionGroup: AttentionGroup?", source)
        self.assertIn("Token accounting is intentionally terminal-only", source)
        self.assertIn('private var codexUnits: [WorkUnit]', source)
        self.assertIn('codexUnits.filter {', source)
        self.assertIn('private func hasLiveCodexThread(_ unit: WorkUnit)', source)
        self.assertIn('private func sessionHasLiveCodexThread(_ sessionID: String)', source)
        self.assertIn('private func terminalWasSupersededBySessionCompletion(_ unit: WorkUnit)', source)
        self.assertIn('(activity.lastTerminalAt ?? 0) < unit.startedAt', source)
        self.assertIn('private func activityIsResolved(for unit: WorkUnit)', source)
        self.assertIn('activityIsResolved(for: $0) && !sessionHasLiveCodexThread($0.sessionID)', source)
        self.assertIn('!terminalWasSupersededBySessionCompletion($0)', source)
        self.assertIn('private func isIgnored(_ unit: WorkUnit)', source)
        self.assertIn('activityResolvedSessionIDs = Set(sessionIDs)', source)
        self.assertIn('$0.state == "running" && hasLiveCodexThread($0)', source)
        self.assertIn('Dictionary(grouping: trackedCodexUnits.filter', source)
        self.assertIn('"thread:\\(unit.sessionID)"', source)
        self.assertIn("private struct RunningItem", source)
        self.assertIn('sectionLabel("当前任务", trailing: "耗时")', source)
        self.assertIn('if let group = model.featuredAttentionGroup { attention(group) }', source)
        self.assertIn('sectionLabel("等你检查", trailing: "最高优先级")', source)
        self.assertIn("private struct MetricBlock", source)
        self.assertIn("JingleVisual.attentionFill", source)
        self.assertIn("model.pendingCount == 0 && model.runningUnits.isEmpty", source)
        self.assertIn("var hasSettlementContent: Bool", source)
        self.assertIn("guard model.hasSettlementContent", source)
        self.assertIn("struct DecisionDetails", source)
        self.assertIn('Text("工作中  ·  \\(unit.startedLabel)")', source)
        self.assertIn('Text("\\(unit.startedLabel) · 本轮 \\(unit.elapsed)")', source)
        self.assertNotIn("providerName", source)
        self.assertNotIn(".badge", source)
        self.assertIn('private var callUnitID: String?', source)
        self.assertIn('!model.callableBlocked.contains(where: { $0.id == callUnitID })', source)
        self.assertNotIn("struct WorkRow", source)
        self.assertIn('Button("已处理")', source)
        self.assertIn("var callableBlocked", source)
        self.assertIn("var oldestWaitingAt", source)
        self.assertIn("if left.hasBlocked != right.hasBlocked { return left.hasBlocked }", source)
        self.assertIn("left.oldestWaitingAt < right.oldestWaitingAt", source)
        self.assertNotIn('.sorted { $0.id < $1.id }', source)
        lifecycle = (ROOT / "src/jingle_lifecycle.py").read_text(encoding="utf-8")
        self.assertIn('existing["superseded_at"]', lifecycle)

    def test_live_session_wins_over_its_historic_terminal_work_units(self) -> None:
        units = [
            {"id": "trade-old-blocked", "session_id": "trade", "state": "blocked", "needs_attention": True, "started_at": 1},
            {"id": "trade-running", "session_id": "trade", "state": "running", "needs_attention": None, "started_at": 2},
            {"id": "research-old-done", "session_id": "research", "state": "done", "needs_attention": True, "started_at": 3},
            {"id": "research-running", "session_id": "research", "state": "running", "needs_attention": None, "started_at": 4},
            {"id": "inactive-blocked", "session_id": "inactive", "state": "blocked", "needs_attention": True, "started_at": 5},
        ]
        live_sessions = {"trade", "research"}
        attention = [
            unit for unit in units
            if unit["needs_attention"] is True and unit["session_id"] not in live_sessions
        ]
        running = {}
        for unit in units:
            if unit["state"] == "running" and unit["session_id"] in live_sessions:
                running[unit["session_id"]] = unit

        self.assertEqual([unit["id"] for unit in attention], ["inactive-blocked"])
        self.assertEqual(set(running), {"trade", "research"})
        self.assertEqual(running["trade"]["id"], "trade-running")

    def test_monitor_strip_keeps_only_the_latest_live_session_per_project(self) -> None:
        live = [
            {"id": "trade-old", "project": "trading", "updated_at": 100},
            {"id": "trade-current", "project": "trading", "updated_at": 140},
            {"id": "research-current", "project": "research", "updated_at": 130},
        ]
        latest: dict[str, dict[str, object]] = {}
        for unit in live:
            project = str(unit["project"])
            if unit["updated_at"] > latest.get(project, {}).get("updated_at", -1):
                latest[project] = unit

        self.assertEqual({unit["id"] for unit in latest.values()}, {"trade-current", "research-current"})
        self.assertEqual(len(latest), 2)

    def test_live_session_suppresses_attention_from_another_session_in_the_same_project(self) -> None:
        units = [
            {"id": "research-running", "project": "research", "session": "research-live", "state": "running"},
            {"id": "research-old-attention", "project": "research", "session": "research-finished", "state": "done", "needs_attention": True},
            {"id": "trade-attention", "project": "trading", "session": "trade-finished", "state": "blocked", "needs_attention": True},
        ]
        live_projects = {unit["project"] for unit in units if unit["state"] == "running"}
        attention = [
            unit for unit in units
            if unit.get("needs_attention") is True and unit["project"] not in live_projects
        ]

        self.assertEqual(live_projects, {"research"})
        self.assertEqual([unit["id"] for unit in attention], ["trade-attention"])

    def test_replay_orders_blocked_groups_before_oldest_done_groups(self) -> None:
        data = json.loads((ROOT / "tests/fixtures/jingle-attention-work-units.json").read_text(encoding="utf-8"))
        projects = json.loads((ROOT / "tests/fixtures/jingle-attention-projects.json").read_text(encoding="utf-8"))["projects"]

        def project_id(unit: dict[str, object]) -> str:
            for project in projects:
                for alias in project["aliases"]:
                    if alias.get("provider") in {None, unit["provider"]} and str(unit["cwd"]).startswith(alias["prefix"]):
                        return project["project_id"]
            return f"unmapped:{unit['cwd']}"

        latest: dict[tuple[str, str], dict[str, object]] = {}
        for unit in data["units"].values():
            key = (unit["provider"], unit["session_id"])
            if unit["started_at"] > latest.get(key, {}).get("started_at", -1):
                latest[key] = unit
        groups: dict[str, list[dict[str, object]]] = {}
        for unit in latest.values():
            if unit.get("provider") == "codex" and unit.get("needs_attention") is True and (
                project_id(unit) == "token-router" or unit.get("state") == "blocked"
            ):
                groups.setdefault(project_id(unit), []).append(unit)

        ordered = sorted(
            groups.items(),
            key=lambda entry: (
                not any(unit["state"] == "blocked" for unit in entry[1]),
                min(unit["ended_at"] for unit in entry[1]),
                entry[0],
            ),
        )
        self.assertEqual([project for project, _ in ordered], ["token-router"])
        self.assertEqual([unit["id"] for unit in ordered[0][1]], ["cx-current"])


if __name__ == "__main__":
    unittest.main()
