"""时间统计:小时桶去重、日期边界、畸形输入不污染。

时间是「花了多少工夫」的唯一度量,算错了没人看得出来——所以每条规则都钉住。
用真实 registry 前缀构造记录(归类逻辑本身另有测试),不读真实日志。
"""

import unittest

from ledger.report import _attach_time_stats

KNOWN = "-Users-wendy-tokenrouter"      # → tokenrouter
UNKNOWN = "/no/such/place"              # → 未归类


def _record(hour, source_key=KNOWN, channel="claude"):
    return {"hour": hour, "source_key": source_key, "channel": channel}


def _projects(*names):
    return [{"name": name} for name in names]


class TimeStatsTests(unittest.TestCase):
    def test_same_day_many_hours_counts_one_day(self):
        projects = _projects("tokenrouter")
        _attach_time_stats(projects, [
            _record("2026-07-28T09"),
            _record("2026-07-28T10"),
            _record("2026-07-28T10"),   # 同小时重复,应去重
        ])
        stats = projects[0]
        self.assertEqual(stats["active_days"], 1)
        self.assertEqual(stats["active_hours"], 2)
        self.assertEqual(stats["first_day"], "2026-07-28")
        self.assertEqual(stats["last_day"], "2026-07-28")

    def test_spans_days_reports_range_and_count(self):
        projects = _projects("tokenrouter")
        _attach_time_stats(projects, [
            _record("2026-07-28T09"),
            _record("2026-05-29T23"),   # 乱序输入,first/last 仍须正确
            _record("2026-06-15T00"),
        ])
        stats = projects[0]
        self.assertEqual(stats["active_days"], 3)
        self.assertEqual(stats["first_day"], "2026-05-29")
        self.assertEqual(stats["last_day"], "2026-07-28")

    def test_no_records_yields_none_not_crash(self):
        projects = _projects("tokenrouter")
        _attach_time_stats(projects, [])
        stats = projects[0]
        self.assertIsNone(stats["first_day"])
        self.assertIsNone(stats["last_day"])
        self.assertEqual(stats["active_days"], 0)
        self.assertEqual(stats["active_hours"], 0)

    def test_blank_hour_is_skipped_without_polluting_counts(self):
        projects = _projects("tokenrouter")
        _attach_time_stats(projects, [
            _record("2026-07-28T09"),
            _record(""),        # Codex 文件名不合规时会是空串
            _record(None),      # 字段缺失
        ])
        stats = projects[0]
        self.assertEqual(stats["active_days"], 1)
        self.assertEqual(stats["active_hours"], 1)

    def test_returns_count_of_unparseable_records_as_signal(self):
        # 日志格式一变(如 Codex 改文件命名),时间会静默归零。
        # 这个计数是唯一的信号——必须准,且必须冒泡到 coverage。
        projects = _projects("tokenrouter")
        undated = _attach_time_stats(projects, [
            _record("2026-07-28T09"),
            _record(""),
            _record(None),
            _record(""),
        ])
        self.assertEqual(undated, 3)

    def test_all_parseable_reports_zero_undated(self):
        projects = _projects("tokenrouter")
        self.assertEqual(_attach_time_stats(projects, [_record("2026-07-28T09")]), 0)
        self.assertEqual(_attach_time_stats(projects, []), 0)

    def test_records_route_to_their_own_project(self):
        projects = _projects("tokenrouter", "未归类")
        _attach_time_stats(projects, [
            _record("2026-07-28T09", KNOWN),
            _record("2026-07-27T09", UNKNOWN),
            _record("2026-07-26T09", UNKNOWN),
        ])
        by_name = {p["name"]: p for p in projects}
        self.assertEqual(by_name["tokenrouter"]["active_days"], 1)
        self.assertEqual(by_name["未归类"]["active_days"], 2)


if __name__ == "__main__":
    unittest.main()
