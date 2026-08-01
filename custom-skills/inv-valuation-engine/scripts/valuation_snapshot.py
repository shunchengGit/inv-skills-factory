#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "akshare>=1.14.0",
#   "yfinance>=0.2.31",
#   "pandas>=2.0.0",
#   "requests>=2.28.0",
# ]
# ///
"""
获取个股估值快照数据，供价值投资估值流程使用。

数据层通过 inv-stock-data 模块直接调用（进程内），限流锁在同一进程内生效。

示例:
  uv run {baseDir}/scripts/valuation_snapshot.py AAPL
  uv run {baseDir}/scripts/valuation_snapshot.py 600519 --output json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

# ── 直接 import inv-stock-data 模块 ──────────────────────────────────────
_inv_stock_dir = Path(__file__).resolve().parent.parent.parent / "inv-stock-data" / "scripts"
sys.path.insert(0, str(_inv_stock_dir))
from cs_stock_info import execute_command
from data_contract import historical_eligibility, historical_gaps, make_gap

from investment_data_adapter import (
    Envelope,
    component_data,
    has_fallback,
    merge_gaps,
    number,
    parse_all_components,
    parse_v1_envelope,
)


def _call_cs_stock(
    command: str,
    symbol: str,
    *,
    period: str = "1y",
    limit: int | None = None,
) -> dict[str, Any]:
    """调用 inv-stock-data v1 公共契约。"""
    return execute_command(command, symbol, period=period, limit=limit)


def _bars_to_df(data: dict[str, Any] | list[dict[str, Any]]) -> pd.DataFrame:
    """Convert inv-stock-data daily bars JSON to a DataFrame with Close column."""
    if not data:
        return pd.DataFrame()
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("daily") or data.get("bars") or data.get("data", [])
        if not rows and data:
            # If the dict itself looks like a single record, wrap it
            if "close" in data or "Close" in data:
                rows = [data]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Normalise column names to title-case expected by analysis helpers
    col_map = {}
    for col in df.columns:
        low = col.lower()
        if low == "close":
            col_map[col] = "Close"
        elif low == "date" or low == "time" or low == "datetime":
            col_map[col] = "Date"
    df = df.rename(columns=col_map)
    if "Close" in df.columns:
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    return df


def normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        return s
    if s.isdigit() and len(s) == 6:
        if s.startswith(("6", "9")):
            return f"{s}.SS"
        return f"{s}.SZ"
    return s


def is_a_share_code(symbol: str) -> bool:
    s = symbol.strip().upper()
    if "." in s:
        base, suffix = s.split(".", 1)
        return base.isdigit() and len(base) == 6 and suffix in {"SS", "SZ", "SH"}
    return s.isdigit() and len(s) == 6


def to_a_share_plain_code(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        return s.split(".", 1)[0]
    return s


def normalize_dividend_yield(value: float | None) -> float | None:
    if value is None:
        return None
    # 兼容两种来源口径：
    # 1) 小数口径: 0.0042 -> 0.42%
    # 2) 百分口径: 0.42   -> 0.42%
    if 0 <= value <= 0.2:
        return round(value * 100, 2)
    return round(value, 2)


def safe_round(value: float | None, ndigits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, ndigits)


def estimate_price_percentile(hist: pd.DataFrame) -> float | None:
    if hist.empty or "Close" not in hist.columns:
        return None
    closes = [float(v) for v in hist["Close"].dropna().tolist()]
    if len(closes) < 30:
        return None
    current = closes[-1]
    rank = sum(1 for x in closes if x <= current)
    return round(rank / len(closes) * 100, 2)


def compute_period_return(hist: pd.DataFrame, lookback: int) -> float | None:
    if hist.empty or "Close" not in hist.columns:
        return None
    closes = hist["Close"].dropna()
    if len(closes) < 2:
        return None
    current = float(closes.iloc[-1])
    past = float(closes.iloc[-min(lookback, len(closes))])
    if past == 0:
        return None
    return round((current - past) / past * 100, 2)


def compute_52w_position(hist: pd.DataFrame) -> tuple[float | None, float | None, float | None, float | None]:
    if hist.empty or "Close" not in hist.columns:
        return None, None, None, None
    tail = hist.tail(252) if len(hist) > 252 else hist
    closes = tail["Close"].dropna()
    if closes.empty:
        return None, None, None, None
    current = float(closes.iloc[-1])
    high_52w = float(closes.max())
    low_52w = float(closes.min())
    if high_52w == low_52w:
        return high_52w, low_52w, None, None
    from_low = round((current - low_52w) / (high_52w - low_52w) * 100, 2)
    to_high = round((high_52w - current) / high_52w * 100, 2) if high_52w else None
    return high_52w, low_52w, from_low, to_high



@dataclass
class Snapshot:
    symbol: str
    normalized_symbol: str
    company_name: str | None
    currency: str | None
    market: str | None
    data_time: str | None
    data_sources: list[dict[str, Any]]
    metrics: dict[str, Any]
    data_gaps: list[dict[str, Any]]
    notes: list[str]
    upstream_status: str
    history_window: dict[str, Any] | None
    used_fallback: bool


def first_not_none(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def build_snapshot(symbol: str) -> Snapshot:
    normalized = normalize_symbol(symbol)
    if is_a_share_code(normalized):
        return _build_a_share_snapshot_v1(symbol, normalized)
    return _build_yahoo_snapshot_v1(symbol, normalized)


def _history_metrics(daily: Envelope) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bars = daily.data.get("daily") or []
    hist = _bars_to_df(bars)
    window = daily.window or {"observations": len(bars)}
    eligibility = historical_eligibility(window)
    gaps = historical_gaps(window)

    latest_close = None
    return_20d = None
    return_60d = None
    if not hist.empty and "Close" in hist.columns:
        closes = hist["Close"].dropna()
        if not closes.empty:
            latest_close = float(closes.iloc[-1])
            if len(closes) >= 21:
                return_20d = compute_period_return(hist, 20)
            if len(closes) >= 61:
                return_60d = compute_period_return(hist, 60)

    percentile = estimate_price_percentile(hist) if eligibility["5y_percentile"] else None
    return_250d = compute_period_return(hist, 250) if eligibility["250d_return"] else None
    high_52w = low_52w = pos_52w = distance_52w = None
    if eligibility["52w"]:
        high_52w, low_52w, pos_52w, distance_52w = compute_52w_position(hist)
    return {
        "latest_close": safe_round(latest_close, 4),
        "price_percentile_5y_proxy": percentile,
        "return_20d_pct": return_20d,
        "return_60d_pct": return_60d,
        "return_250d_pct": return_250d,
        "high_52w": safe_round(high_52w, 4),
        "low_52w": safe_round(low_52w, 4),
        "position_in_52w_range_pct": pos_52w,
        "distance_to_52w_high_pct": distance_52w,
    }, gaps


def _component_gaps(component: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in component.get("gaps") or []]


def _build_a_share_snapshot_v1(symbol: str, normalized: str) -> Snapshot:
    plain = to_a_share_plain_code(normalized)
    all_envelope, components = parse_all_components(_call_cs_stock("all", plain))
    daily = parse_v1_envelope(_call_cs_stock("daily", plain, period="5y"), expected_command="daily")
    announcements = parse_v1_envelope(_call_cs_stock("announcements", plain), expected_command="announcements")
    relations = parse_v1_envelope(_call_cs_stock("relations", plain), expected_command="relations")

    snap = component_data(components["snapshot"])
    financial_component = component_data(components["financial"])
    financial = snap.get("financial") or financial_component.get("ths_financial") or {}
    sina = snap.get("sina") or financial_component.get("sina_financial") or {}
    valuation = snap.get("valuation") or {}

    def sina_num(key: str) -> float | None:
        return number(sina.get(key))

    def fin_num(key: str) -> float | None:
        return number(financial.get(key))

    history, history_gaps = _history_metrics(daily)
    roe = first_not_none(sina_num("净资产收益率"), fin_num("净资产收益率"))
    gross_margin = first_not_none(sina_num("销售毛利率"), fin_num("销售毛利率"))
    net_margin = first_not_none(sina_num("销售净利率"), fin_num("销售净利率"))
    debt_to_asset = first_not_none(sina_num("资产负债率"), fin_num("资产负债率"))
    pe_ttm = number(valuation.get("pe_ttm"))
    # 如果百度 PE TTM 缺失，降级使用静态 PE
    if pe_ttm is None:
        pe_ttm = number(valuation.get("pe_static"))
    pb = number(valuation.get("pb"))
    current_price = first_not_none(number(snap.get("price")), history["latest_close"])

    ann_items = announcements.data.get("announcements") or []
    rel_items = relations.data.get("relations") or []
    raw_titles = []
    for item in ann_items[:10]:
        if isinstance(item, dict):
            title = item.get("title") or item.get("标题") or item.get("公告标题")
            if title:
                raw_titles.append({"title": str(title), "date": item.get("date") or item.get("公告日期")})

    metrics: dict[str, Any] = {
        "market_label": "A-share",
        "currency": "CNY",
        "sector": snap.get("industry"),
        "industry": snap.get("industry"),
        "current_price": safe_round(current_price, 4),
        "company_name": snap.get("name"),
        "trailing_pe": safe_round(pe_ttm, 2),
        "forward_pe": None,
        "pb": safe_round(pb, 2),
        "roe_pct": safe_round(roe, 2),
        "gross_margin_pct": safe_round(gross_margin, 2),
        "net_margin_pct": safe_round(net_margin, 2),
        "debt_to_equity": safe_round(debt_to_asset, 2),
        "sina_eps": safe_round(sina_num("基本每股收益"), 2),
        "sina_bvps": safe_round(sina_num("每股净资产"), 2),
        "recent_announcements": raw_titles,
        "relation_count_30d": len(rel_items),
        "profile_highlights": snap.get("description"),
        **history,
    }
    computed_gaps = [
        make_gap("field_unavailable", f"metrics.{key}", "估值指标不可用", retryable=False)
        for key in ("trailing_pe", "pb", "roe_pct", "gross_margin_pct")
        if metrics.get(key) is None
    ]
    gaps = merge_gaps(
        all_envelope.gaps,
        _component_gaps(components["snapshot"]),
        _component_gaps(components["financial"]),
        _component_gaps(components["financials"]),
        daily.gaps,
        announcements.gaps,
        relations.gaps,
        history_gaps,
        computed_gaps,
    )
    sources = all_envelope.sources + daily.sources + announcements.sources + relations.sources
    status = "failed" if components["snapshot"]["status"] == "failed" else "partial" if gaps or all_envelope.status == "partial" else "ok"
    return Snapshot(
        symbol=symbol,
        normalized_symbol=normalized,
        company_name=snap.get("name"),
        currency="CNY",
        market="A-share",
        data_time=daily.data_as_of or all_envelope.data_as_of,
        data_sources=sources,
        metrics=metrics,
        data_gaps=gaps,
        notes=all_envelope.notes + daily.notes,
        upstream_status=status,
        history_window=daily.window,
        used_fallback=has_fallback(sources),
    )


def _build_yahoo_snapshot_v1(symbol: str, normalized: str) -> Snapshot:
    all_envelope, components = parse_all_components(_call_cs_stock("all", normalized))
    daily = parse_v1_envelope(_call_cs_stock("daily", normalized, period="5y"), expected_command="daily")
    snap = component_data(components["snapshot"])
    financial = component_data(components["financial"])
    fund = snap.get("fundamentals") or {}
    fin_fund = financial.get("fundamentals") or {}

    def first_metric(*keys: str) -> Any:
        for key in keys:
            value = first_not_none(fund.get(key), fin_fund.get(key))
            if value is not None:
                return value
        return None

    history, history_gaps = _history_metrics(daily)
    trailing_pe = number(first_metric("pe_trailing"))
    forward_pe = number(first_metric("pe_forward"))
    pb = number(first_metric("pb"))
    current_price = number(snap.get("price"))
    market = "HK" if all_envelope.symbol.get("market") == "hk" else "US"
    metrics: dict[str, Any] = {
        "market_label": market,
        "currency": snap.get("currency"),
        "sector": snap.get("sector"),
        "industry": snap.get("industry"),
        "current_price": safe_round(current_price, 4),
        "trailing_pe": safe_round(trailing_pe, 2),
        "forward_pe": safe_round(forward_pe, 2),
        "pb": safe_round(pb, 2),
        "ps_ttm": safe_round(number(first_metric("price_to_sales", "ps_ttm")), 2),
        "ev_ebitda": safe_round(number(first_metric("ev_to_ebitda", "enterprise_to_ebitda")), 2),
        "market_cap": number(first_metric("market_cap")),
        "enterprise_value": number(first_metric("enterprise_value")),
        "total_debt": number(first_metric("total_debt")),
        "total_cash": number(first_metric("total_cash")),
        "analyst_target_price": safe_round(number(first_metric("target_mean_price", "analyst_target_price")), 4),
        "analyst_count": number(first_metric("number_of_analysts", "analyst_count")),
        "next_earnings_date": financial.get("next_earnings_date"),
        "dividend_yield_pct": safe_round(number(first_metric("dividend_yield_pct")), 2),
        "roe_pct": safe_round(number(first_metric("roe_pct")), 2),
        "gross_margin_pct": safe_round(number(first_metric("gross_margin_pct")), 2),
        "operating_margin_pct": safe_round(number(first_metric("operating_margin_pct")), 2),
        "net_margin_pct": safe_round(number(first_metric("net_margin_pct")), 2),
        "debt_to_equity": safe_round(number(first_metric("debt_to_equity")), 2),
        "revenue_growth_pct": safe_round(number(first_metric("revenue_growth_pct")), 2),
        "earnings_growth_pct": safe_round(number(first_metric("earnings_growth_pct")), 2),
        "free_cash_flow": number(first_metric("free_cash_flow")),
        "earnings_yield_pct": safe_round(100 / trailing_pe, 2) if trailing_pe not in (None, 0) else None,
        **history,
    }
    target = metrics["analyst_target_price"]
    metrics["analyst_upside_pct"] = safe_round((target / current_price - 1) * 100, 2) if target and current_price else None
    computed_gaps = [
        make_gap("field_unavailable", f"metrics.{key}", "估值指标不可用", retryable=False)
        for key in ("trailing_pe", "forward_pe", "pb", "revenue_growth_pct", "earnings_growth_pct")
        if metrics.get(key) is None
    ]
    gaps = merge_gaps(
        all_envelope.gaps,
        _component_gaps(components["snapshot"]),
        _component_gaps(components["financial"]),
        _component_gaps(components["financials"]),
        daily.gaps,
        history_gaps,
        computed_gaps,
    )
    sources = all_envelope.sources + daily.sources
    status = "failed" if components["snapshot"]["status"] == "failed" else "partial" if gaps or all_envelope.status == "partial" else "ok"
    return Snapshot(
        symbol=symbol,
        normalized_symbol=normalized,
        company_name=snap.get("name"),
        currency=snap.get("currency"),
        market=market,
        data_time=daily.data_as_of or all_envelope.data_as_of,
        data_sources=sources,
        metrics=metrics,
        data_gaps=gaps,
        notes=all_envelope.notes + daily.notes,
        upstream_status=status,
        history_window=daily.window,
        used_fallback=has_fallback(sources),
    )


def render_text(snapshot: Snapshot) -> str:
    lines = [
        "=" * 72,
        f"VALUE SNAPSHOT: {snapshot.normalized_symbol} ({snapshot.company_name or 'N/A'})",
        f"Data Time: {snapshot.data_time}",
        f"Upstream Status: {snapshot.upstream_status}",
        f"Data Sources: {json.dumps(snapshot.data_sources, ensure_ascii=False)}",
        "=" * 72,
        "",
        "估值与经营指标:",
    ]
    for key, value in snapshot.metrics.items():
        lines.append(f"- {key}: {value}")
    if snapshot.data_gaps:
        lines.append("")
        lines.append("缺失字段:")
        for g in snapshot.data_gaps:
            lines.append(f"- {g.get('field')}: {g.get('reason')} ({g.get('code')})")
    if snapshot.notes:
        lines.append("")
        lines.append("说明:")
        for n in snapshot.notes:
            lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def render_markdown(snapshot: Snapshot) -> str:
    lines = [
        f"## 估值快照：{snapshot.normalized_symbol} {snapshot.company_name or ''}".rstrip(),
        "",
        f"- 数据时点：{snapshot.data_time or '未知'}",
        f"- 上游状态：{snapshot.upstream_status}",
        f"- 数据源：{json.dumps(snapshot.data_sources, ensure_ascii=False)}",
        "",
        "## 核心字段",
        "",
        "| 字段 | 值 |",
        "|---|---|",
    ]
    for key, value in snapshot.metrics.items():
        if isinstance(value, list):
            display = "<br>".join(str(x) for x in value) if value else ""
        else:
            display = "" if value is None else str(value)
        lines.append(f"| {key} | {display} |")

    if snapshot.data_gaps:
        lines.extend(
            [
                "",
                "## 缺失字段",
                *[f"- {item.get('field')}: {item.get('reason')} ({item.get('code')})" for item in snapshot.data_gaps],
            ]
        )
    if snapshot.notes:
        lines.extend(
            [
                "",
                "## 说明",
                *[f"- {item}" for item in snapshot.notes],
            ]
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="价值投资估值数据快照")
    parser.add_argument("symbol", help="股票代码，如 AAPL / 600519 / 0700.HK")
    parser.add_argument("--output", default="text", choices=["text", "json", "markdown"], help="输出格式")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        snapshot = build_snapshot(args.symbol)
    except Exception as exc:
        print(f"抓取失败: {exc}", file=sys.stderr)
        return 1

    if args.output == "json":
        print(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2))
    elif args.output == "markdown":
        print(render_markdown(snapshot))
    else:
        print(render_text(snapshot))
    return 1 if snapshot.upstream_status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
