"""定价对齐:优先读 models.dev 共享缓存,缺失时回退离线标价。

与 TokenPulse 同源(同一份缓存文件),所以对同一 model 得同一价。
这些用例用自造的最小缓存,不依赖真实文件,也不联网。
"""

import json
import tempfile
import unittest
from decimal import Decimal

from ledger import prices


class PriceAlignmentTests(unittest.TestCase):
    def _reset(self):
        prices._MODELS_DEV_TABLE = None

    def test_shared_cache_overrides_offline_list_price(self):
        # 缓存里 sonnet 是引导优惠价 2/10,离线标价是 3/15——必须以缓存为准
        cache = {"catalog": {"providers": {"anthropic": {"models": {
            "claude-sonnet-5": {"cost": {"input": 2, "output": 10,
                                         "cache_read": 0.2, "cache_write": 2.5}}
        }}}}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(cache, handle)
            path = handle.name
        original = prices.MODELS_DEV_CACHE
        prices.MODELS_DEV_CACHE = path
        self._reset()
        try:
            rates = prices.claude_prices("claude-sonnet-5")
            self.assertEqual(rates[0], Decimal("2"))
            self.assertEqual(rates[1], Decimal("10"))
        finally:
            prices.MODELS_DEV_CACHE = original
            self._reset()

    def test_falls_back_to_offline_when_cache_missing(self):
        original = prices.MODELS_DEV_CACHE
        prices.MODELS_DEV_CACHE = "/nonexistent/models-dev.json"
        self._reset()
        try:
            rates = prices.claude_prices("claude-opus-4-8")
            self.assertEqual(rates[0], Decimal("5"))   # 离线标价
            self.assertEqual(rates[1], Decimal("25"))
        finally:
            prices.MODELS_DEV_CACHE = original
            self._reset()

    def test_malformed_cache_falls_back_not_raises(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write("{ not valid json")
            path = handle.name
        original = prices.MODELS_DEV_CACHE
        prices.MODELS_DEV_CACHE = path
        self._reset()
        try:
            rates = prices.claude_prices("claude-opus-4-8")   # 不许抛异常
            self.assertEqual(rates[0], Decimal("5"))
        finally:
            prices.MODELS_DEV_CACHE = original
            self._reset()


if __name__ == "__main__":
    unittest.main()
