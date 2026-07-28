"""scripts/ 三个脚本的纯逻辑。

用假的 git 输出与临时快照目录,不跑真 git、不读真实 snapshots。
重点钉住 build_trend 的序列对齐——sparkline 画得对不对全看它。
"""

import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_outputs  # noqa: E402
import trend  # noqa: E402


def _write_snapshot(directory, date, projects, grand=None):
    """projects: {name: cost_cents}"""
    payload = {
        "date": date,
        "generated_at": date + "T03:15:00+08:00",
        "grand_total_cents": grand if grand is not None else sum(projects.values()),
        "projects": {
            name: {"cost_cents": cents, "claude_cents": cents,
                   "codex_cents": 0, "active_days": 1}
            for name, cents in projects.items()
        },
    }
    (pathlib.Path(directory) / f"{date}.json").write_text(
        json.dumps(payload, ensure_ascii=False)
    )


class TrendTests(unittest.TestCase):
    def setUp(self):
        self._original = trend.SNAP_DIR
        self._tmp = tempfile.TemporaryDirectory()
        trend.SNAP_DIR = pathlib.Path(self._tmp.name)

    def tearDown(self):
        trend.SNAP_DIR = self._original
        self._tmp.cleanup()

    def test_no_snapshots_yields_empty_series(self):
        result = trend.build_trend()
        self.assertEqual(result["dates"], [])
        self.assertEqual(result["grand_total_cents"], [])
        self.assertEqual(result["projects"], {})

    def test_series_sorted_by_date_regardless_of_write_order(self):
        _write_snapshot(trend.SNAP_DIR, "2026-07-30", {"a": 300})
        _write_snapshot(trend.SNAP_DIR, "2026-07-28", {"a": 100})
        _write_snapshot(trend.SNAP_DIR, "2026-07-29", {"a": 200})
        result = trend.build_trend()
        self.assertEqual(result["dates"], ["2026-07-28", "2026-07-29", "2026-07-30"])
        self.assertEqual(result["grand_total_cents"], [100, 200, 300])
        self.assertEqual(result["projects"]["a"], [100, 200, 300])

    def test_project_appearing_midway_is_zero_filled_and_aligned(self):
        # 这是 sparkline 正确的前提:每条序列长度必须等于 dates 长度
        _write_snapshot(trend.SNAP_DIR, "2026-07-28", {"old": 100})
        _write_snapshot(trend.SNAP_DIR, "2026-07-29", {"old": 150, "new": 50})
        result = trend.build_trend()
        self.assertEqual(result["projects"]["old"], [100, 150])
        self.assertEqual(result["projects"]["new"], [0, 50])   # 出现前补 0
        for name, series in result["projects"].items():
            self.assertEqual(len(series), len(result["dates"]), name)

    def test_malformed_snapshot_is_skipped_not_fatal(self):
        _write_snapshot(trend.SNAP_DIR, "2026-07-28", {"a": 100})
        (trend.SNAP_DIR / "2026-07-29.json").write_text("{ not json")
        result = trend.build_trend()
        self.assertEqual(result["dates"], ["2026-07-28"])


class SnapshotInvariantTests(unittest.TestCase):
    def test_snapshot_project_sum_equals_its_own_grand_total(self):
        with tempfile.TemporaryDirectory() as directory:
            _write_snapshot(directory, "2026-07-28", {"a": 100, "b": 250})
            payload = json.loads(
                (pathlib.Path(directory) / "2026-07-28.json").read_text()
            )
        total = sum(p["cost_cents"] for p in payload["projects"].values())
        self.assertEqual(total, payload["grand_total_cents"])


class GitOutputParsingTests(unittest.TestCase):
    """stats_for 只解析 _git 返回的字符串——打桩即可,不跑真 git。"""

    def setUp(self):
        self._original = build_outputs._git
        self._tmp = tempfile.TemporaryDirectory()
        pathlib.Path(self._tmp.name, ".git").mkdir()

    def tearDown(self):
        build_outputs._git = self._original
        self._tmp.cleanup()

    def _stub(self, mapping, default=""):
        def fake(repo, *args):
            for key, value in mapping.items():
                if key in " ".join(args):
                    return value
            return default
        build_outputs._git = fake

    def test_counts_only_pull_request_merges(self):
        self._stub({
            "--merges --oneline": (
                "aaa Merge pull request #10 from x\n"
                "bbb Merge branch 'main' into feature\n"      # 不是 PR,不算
                "ccc Merge pull request #11 from y"
            ),
        })
        stats = build_outputs.stats_for(self._tmp.name)
        self.assertEqual(stats["merged_prs"], 2)

    def test_extracts_pr_number_from_last_merge_subject(self):
        self._stub({
            "-1 --format=%s|%cs": "Merge pull request #383 from zinan92/codex/x|2026-07-25",
        })
        stats = build_outputs.stats_for(self._tmp.name)
        self.assertEqual(stats["last_merge_pr"], "383")
        self.assertEqual(stats["last_merge_day"], "2026-07-25")

    def test_non_pr_last_merge_yields_none_not_garbage(self):
        self._stub({"-1 --format=%s|%cs": "Merge branch 'main'|2026-07-25"})
        stats = build_outputs.stats_for(self._tmp.name)
        self.assertIsNone(stats["last_merge_pr"])

    def test_missing_repo_returns_none(self):
        self.assertIsNone(build_outputs.stats_for("/nonexistent/repo"))
        self.assertIsNone(build_outputs.stats_for(""))

    def test_empty_repo_yields_zeros_not_crash(self):
        self._stub({}, default="")     # 全空:仓库存在但无 commit
        stats = build_outputs.stats_for(self._tmp.name)
        self.assertEqual(stats["merged_prs"], 0)
        self.assertEqual(stats["commits_30d"], 0)
        self.assertIsNone(stats["last_commit_day"])


if __name__ == "__main__":
    unittest.main()
