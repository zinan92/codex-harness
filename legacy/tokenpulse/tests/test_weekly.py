import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import weekly  # noqa: E402


def test_review_empty_week_is_an_honest_empty_state():
    result = weekly.review([{"total": 0}] * 7, [])
    assert result["state"] == "empty"
    assert result["outcomes"] == 0
    assert "会话" in result["next_action"]


def test_review_sparse_week_asks_for_a_defined_output():
    result = weekly.review([{"total": 10}, {"total": 0}], [])
    assert result["state"] == "sparse"
    assert result["active_days"] == 1
    assert "可验收产出" in result["next_action"]


def test_review_never_treats_tokens_as_an_outcome():
    result = weekly.review([{"total": 10}] * 7, [])
    assert result["state"] == "unlinked"
    assert result["outcomes"] == 0
    assert "产出标记" in result["next_action"]


def test_review_counts_only_user_written_outcomes():
    rows = [{"annotation": {"outcome": "merged PR"}}, {"annotation": {}}, {"annotation": {"outcome": ""}}]
    result = weekly.review([{"total": 10}] * 4, rows)
    assert result == {
        "total": 40, "active_days": 4, "outcomes": 1, "state": "steady",
        "conclusion": "本周有 4 个活跃日，并记录了 1 条实际产出。",
        "next_action": "挑出一条最有价值的产出，明确下周要推进的下一步。",
    }
