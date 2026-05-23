"""ETF 数据获取 — 快照、日K线、净值。"""

from __future__ import annotations

import pandas as pd

from utils import safe_call, ret_n, _name_code_cache, _etf_category_cache
from market import prefixed_sina


def _float_or_none(val) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


_fund_name_cache: dict[str, dict] = {}


def fetch_etf_name(code: str) -> dict | None:
    """获取 ETF 名称和分类。优先新浪分类（快），其次天天基金（全但首次需 20s）。"""
    import akshare as ak

    # 1. 新浪 ETF 分类（360只，包含大部分主流 ETF）
    df = safe_call(ak.fund_etf_category_sina)
    if df is not None and not df.empty:
        row = df[df["代码"] == code]
        if not row.empty:
            r = row.iloc[0]
            name = str(r.get("名称", ""))
            category = str(r.get("类型", ""))
            _etf_category_cache[code] = category
            _name_code_cache[name] = code
            return {"name": name, "category": category}

    # 2. 天天基金全量列表（首次调用约20s，结果缓存）
    if not _fund_name_cache:
        fund_df = safe_call(ak.fund_name_em)
        if fund_df is not None and not fund_df.empty:
            for _, r in fund_df.iterrows():
                _fund_name_cache[str(r.get("基金代码", ""))] = {
                    "name": str(r.get("基金简称", "")),
                    "type": str(r.get("基金类型", "")),
                }
    cached = _fund_name_cache.get(code)
    if cached:
        _name_code_cache[cached["name"]] = code
        return {"name": cached["name"], "category": cached["type"]}
    return None


def fetch_etf_snapshot(code: str) -> dict | None:
    """获取 ETF 实时快照（新浪源）。"""
    import akshare as ak
    sina_code = prefixed_sina(code, "etf")
    df = safe_call(ak.stock_zh_a_spot_em)
    if df is None or df.empty:
        return None
    row = df[df["代码"] == code]
    if row.empty:
        return None
    r = row.iloc[0]
    name = str(r.get("名称", ""))
    _name_code_cache[name] = code
    _etf_category_cache[code] = "ETF"
    return {
        "name": name,
        "price": _float_or_none(r.get("最新价")),
        "change_pct": _float_or_none(r.get("涨跌幅")),
        "volume": _float_or_none(r.get("成交量")),
        "amount": _float_or_none(r.get("成交额")),
        "turnover": _float_or_none(r.get("换手率")),
    }


def fetch_etf_daily(code: str, n: int = 60) -> pd.DataFrame | None:
    """获取 ETF 日K线（东财源，前复权）。"""
    import akshare as ak
    sina_code = prefixed_sina(code, "etf")
    df = safe_call(ak.stock_zh_a_daily, symbol=sina_code, adjust="qfq")
    if df is None or df.empty:
        return None
    if "date" in df.columns:
        df = df.sort_values("date")
    return df.tail(n) if len(df) > n else df


def fetch_etf_nav(code: str) -> dict | None:
    """获取 ETF 净值数据（单位净值、累计净值、折溢价率）。"""
    import akshare as ak
    df = safe_call(ak.fund_etf_hist_em, symbol=code, period="daily", adjust="qfq")
    if df is None or df.empty:
        return None
    latest = df.iloc[-1]
    nav = _float_or_none(latest.get("单位净值") or latest.get("净值"))
    acc_nav = _float_or_none(latest.get("累计净值"))
    date_str = str(latest.get("净值日期") or latest.get("日期", ""))
    price = _float_or_none(latest.get("收盘价") or latest.get("收盘"))
    premium_pct = None
    premium_label = "平价"
    if nav and price:
        premium_pct = (price - nav) / nav
        if premium_pct > 0.02:
            premium_label = "溢价"
        elif premium_pct < -0.02:
            premium_label = "折价"
    return {
        "latest": nav,
        "acc_nav": acc_nav,
        "date": date_str,
        "premium_pct": premium_pct,
        "premium_label": premium_label,
    }
