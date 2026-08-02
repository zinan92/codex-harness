"""Pricing for the ledger (USD per million tokens).

口径与 TokenPulse 对齐:两个产品都读同一份 models.dev 缓存
(~/Library/Caches/codexbar/model-pricing/models-dev-v1.json,由 TokenPulse/CodexBar
每日维护),所以对同一 model 得到同一价。缓存缺失或读不动时回退到下面的
离线标价——保证无网也能算,只是可能滞后于优惠/降价(如 sonnet-5 引导期 $2/$10)。
"""

import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP

# 与 TokenPulse cost.py 同一路径,是三个产品共享的价表数据源
MODELS_DEV_CACHE = os.path.expanduser(
    "~/Library/Caches/codexbar/model-pricing/models-dev-v1.json"
)

# 离线回退标价:(input, output, cache_write, cache_read) $/Mtok
CLAUDE_PRICES = {
    "opus-5": ("5", "25", "6.25", "0.5"),
    "opus-4-8": ("5", "25", "6.25", "0.5"),
    "opus-4-7": ("5", "25", "6.25", "0.5"),
    "opus-4-6": ("5", "25", "6.25", "0.5"),
    "opus": ("15", "75", "18.75", "1.5"),
    "fable": ("10", "50", "12.5", "1"),
    "sonnet": ("3", "15", "3.75", "0.3"),
    "haiku": ("1", "5", "1.25", "0.1"),
}

# Codex usage records do not reliably contain the model name, so this is the
# task's single offline pricing assumption for that channel.
CODEX_PRICES = ("1.25", "0.125", "10")

_MODELS_DEV_TABLE = None  # 惰性加载并进程内缓存;None=未尝试,{}=尝试过但没有


def _load_models_dev(path=MODELS_DEV_CACHE):
    """展平 models.dev 缓存为 model-id -> {input, output, cache_read, cache_write}。

    结构与 TokenPulse._flatten 一致:catalog.providers.<prov>.models.<id>.cost。
    读不到或格式不符一律返回 {},让调用方回退离线标价。
    """
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    catalog = raw.get("catalog") if isinstance(raw, dict) else None
    providers = catalog.get("providers") if isinstance(catalog, dict) else None
    if not isinstance(providers, dict):
        return {}
    table = {}
    for provider in providers.values():
        models = provider.get("models") if isinstance(provider, dict) else None
        if not isinstance(models, dict):
            continue
        for model_id, meta in models.items():
            cost = meta.get("cost") if isinstance(meta, dict) else None
            if not isinstance(cost, dict) or not cost:
                continue
            table[model_id] = (
                cost.get("input", 0), cost.get("output", 0),
                cost.get("cache_write", 0), cost.get("cache_read", 0),
            )
    return table


def _models_dev_table():
    global _MODELS_DEV_TABLE
    if _MODELS_DEV_TABLE is None:
        _MODELS_DEV_TABLE = _load_models_dev()
    return _MODELS_DEV_TABLE


def _match_models_dev(model, table):
    """精确 → 去日期后缀 → 最长前缀。对齐 TokenPulse.price_for 的匹配顺序。"""
    if not model or not table:
        return None
    if model in table:
        return table[model]
    base = model.rsplit("-", 1)[0] if re.search(r"\d{8}$", model) else model
    if base in table:
        return table[base]
    best = ""
    for model_id in table:
        if model.startswith(model_id) and len(model_id) > len(best):
            best = model_id
    return table[best] if best else None


def claude_prices(model):
    """Return input, output, cache-write, cache-read rates for *model*.

    先查共享的 models.dev 价表(与 TokenPulse 同源),命中即用;否则回退离线标价。
    """
    hit = _match_models_dev(model or "", _models_dev_table())
    if hit is not None:
        return tuple(Decimal(str(rate)) for rate in hit)
    lowered = (model or "").lower()
    for key, rates in CLAUDE_PRICES.items():
        if key in lowered:
            return tuple(Decimal(rate) for rate in rates)
    return tuple(Decimal(rate) for rate in CLAUDE_PRICES["sonnet"])


def codex_prices():
    """Return input, output, cache-write, cache-read rates for Codex.

    优先用共享价表里的 gpt-5-codex(与 TokenPulse 同源);缺失回退离线标价。
    """
    hit = _match_models_dev("gpt-5-codex", _models_dev_table())
    if hit is not None:
        return tuple(Decimal(str(rate)) for rate in hit)
    fresh_input, cached_input, output = (Decimal(rate) for rate in CODEX_PRICES)
    return fresh_input, output, Decimal("0"), cached_input


def cost_cents(input_tokens, output_tokens, cache_write_tokens=0,
               cache_read_tokens=0, rates=None):
    """Calculate one record's price in whole cents, using a documented rounding."""
    input_rate, output_rate, write_rate, read_rate = rates
    dollars = (
        Decimal(input_tokens) * input_rate
        + Decimal(output_tokens) * output_rate
        + Decimal(cache_write_tokens) * write_rate
        + Decimal(cache_read_tokens) * read_rate
    ) / Decimal(1_000_000)
    return int((dollars * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
