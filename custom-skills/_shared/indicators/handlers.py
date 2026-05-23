"""前置指标框架 — handler 处理逻辑。

每种 handler 类型负责将 fetcher 返回的原始数据加工为快照格式。

已实现的 handler 类型：
- kline:    K-line 行情数据（自动计算趋势、百分位、波动率）
- macro:    宏观数据（直接透传 fetcher 字段）
- ranking:  排名数据（直接透传 fetcher 字段）
- agent_search: Agent 搜索型指标（标记 agent_required）
"""

from __future__ import annotations

from typing import Any

from .config import register_handler


def _handle_kline(cfg, raw: dict) -> dict:
    """处理 K-line 类型指标。

    自动计算：
    - 当前价格（应用 divisor 换算）
    - 20/60 日趋势判断
    - 120 日百分位
    - 波动率警告（近 20 日振幅 > 15%）

    fetcher 返回格式（示例）：
    {
        "data_quality": "complete",
        "history": [...],  # [{date, close, high, low}, ...]
        "divisor": 100,   # 可选，默认 1
    }
    """
    if raw.get("data_quality") != "complete":
        return raw

    history = raw.get("history", [])
    if not history:
        raw["data_quality"] = "partial"
        return raw

    divisor = raw.get("divisor", 1)
    closes = [h["close"] for h in history if h.get("close") is not None]
    if not closes:
        raw["data_quality"] = "partial"
        return raw

    latest_raw = closes[-1]
    latest = round(latest_raw / divisor, 2)

    result = {k: v for k, v in raw.items() if k != "history"}
    result["latest_price"] = latest

    # 趋势判断
    def _trend(prices, window):
        if len(prices) < window:
            return "N/A"
        seg = prices[-window:]
        return "↑上升" if seg[-1] > seg[0] else "↓下降" if seg[-1] < seg[0] else "→持平"

    result["trend_20d"] = _trend(closes, 20)
    result["trend_60d"] = _trend(closes, 60)

    # 120 日百分位
    if len(closes) >= 20:
        window120 = closes[-120:] if len(closes) >= 120 else closes
        sorted_prices = sorted(window120)
        rank = sum(1 for p in sorted_prices if p <= latest_raw)
        result["percentile_120d"] = round(rank / len(sorted_prices) * 100, 1)
    else:
        result["percentile_120d"] = "N/A"

    # 波动率警告
    if len(closes) >= 20:
        recent20 = closes[-20:]
        high = max(recent20)
        low = min(recent20)
        amplitude = (high - low) / low * 100 if low else 0
        result["volatility_warning"] = amplitude > 15
    else:
        result["volatility_warning"] = False

    return result


def _handle_macro(cfg, raw: dict) -> dict:
    """处理宏观数据指标——直接透传 fetcher 返回的字段。"""
    return raw


def _handle_ranking(cfg, raw: dict) -> dict:
    """处理排名数据指标——直接透传 fetcher 返回的字段。"""
    return raw


def _handle_agent_search(cfg, raw: dict) -> dict:
    """处理 Agent 搜索型指标。

    这类指标无法通过脚本自动获取，需要 LLM 通过搜索获取数据。
    快照中标记 data_quality 为 agent_required，附 search_hint。
    """
    return {
        "data_quality": "agent_required",
        "search_hint": cfg.search_hint or "",
    }


# 注册所有内置 handler
register_handler("kline", _handle_kline)
register_handler("macro", _handle_macro)
register_handler("ranking", _handle_ranking)
register_handler("agent_search", _handle_agent_search)