#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pandas>=2.0.0",
# ]
# ///
"""
获取个股估值快照数据，供价值投资估值流程使用。

数据层统一通过 inv-stock-data CLI 获取，不再直接调用 AkShare / yfinance。

示例:
  uv run {baseDir}/scripts/valuation_snapshot.py AAPL
  uv run {baseDir}/scripts/valuation_snapshot.py 600519 --output json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import time

import pandas as pd




# 跨进程调用间隔（秒），避免连续 uv run 触发 Yahoo 限流
_CS_STOCK_CALL_INTERVAL = 5.0
_last_cs_stock_call = 0.0


def _call_cs_stock(*args: str) -> dict[str, Any]:
    """Call inv-stock-data CLI and return parsed JSON dict.

    跨进程调用自动等待，确保间隔 >= _CS_STOCK_CALL_INTERVAL 秒。
    """
    global _last_cs_stock_call
    from pathlib import Path
    cs_dir = Path(__file__).resolve().parent.parent.parent / "inv-stock-data"
    cmd = ["uv", "run", str(cs_dir / "scripts" / "cs_stock_info.py"), *args, "--output", "json"]

    elapsed = time.monotonic() - _last_cs_stock_call
    if elapsed < _CS_STOCK_CALL_INTERVAL:
        time.sleep(_CS_STOCK_CALL_INTERVAL - elapsed)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cs_dir,
            timeout=120,
        )
        _last_cs_stock_call = time.monotonic()
        if result.returncode != 0:
            return {"error": result.stderr.strip()[:300]}
        return json.loads(result.stdout)
    except Exception as exc:
        _last_cs_stock_call = time.monotonic()
        return {"error": str(exc)[:200]}


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


def pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value * 100, 2)


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


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class Snapshot:
    symbol: str
    normalized_symbol: str
    company_name: str | None
    currency: str | None
    market: str | None
    data_time: str
    data_sources: list[str]
    metrics: dict[str, Any]
    data_gaps: list[str]
    notes: list[str]


def first_not_none(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def build_snapshot(symbol: str) -> Snapshot:
    normalized = normalize_symbol(symbol)
    notes: list[str] = []
    data_sources: list[str] = []
    is_a_share = is_a_share_code(normalized)

    if is_a_share:
        return _build_a_share_snapshot(symbol, normalized, notes, data_sources)
    else:
        return _build_yahoo_snapshot(symbol, normalized, notes, data_sources)


def _build_a_share_snapshot(
    symbol: str,
    normalized: str,
    notes: list[str],
    data_sources: list[str],
) -> Snapshot:
    """Build snapshot for A-share symbols via inv-stock-data."""
    plain = to_a_share_plain_code(normalized)

    # --- snapshot ---
    snap = _call_cs_stock("snapshot", plain)
    if snap and not snap.get("error"):
        data_sources.append("inv-stock-data(snapshot)")
    else:
        notes.append("inv-stock-data snapshot 调用失败，A 股数据可能不完整")

    company_name = snap.get("name")
    description = snap.get("description")

    # 财务指标：优先 sina（更新更及时），fallback 到 financial（同花顺）
    financial = snap.get("financial") or {}
    sina = snap.get("sina") or {}

    # 从 sina 提取（中文 key，值可能是 None/False/数字）
    def _sina_num(key: str) -> float | None:
        v = sina.get(key)
        if v is None or v is False:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    def _fin_num(key: str) -> float | None:
        v = financial.get(key)
        if v is None or v is False:
            return None
        try:
            return float(str(v).replace("亿", "").replace("%", "").replace("万", ""))
        except (ValueError, TypeError):
            return None

    # 基本面：sina 优先
    gross_margin = _sina_num("销售毛利率") or _fin_num("销售毛利率")
    net_margin = _sina_num("销售净利率") or _fin_num("销售净利率")
    roe = _sina_num("净资产收益率") or _fin_num("净资产收益率")
    debt_to_asset = _sina_num("资产负债率") or _fin_num("资产负债率")
    eps = _sina_num("基本每股收益") or _fin_num("基本每股收益")
    bvps = _sina_num("每股净资产") or _fin_num("每股净资产")
    report_date = sina.get("报告日") or financial.get("报告期")

    # 估值：从 valuation 字段获取
    valuation = snap.get("valuation") or {}
    pe_ttm = valuation.get("pe_ttm")
    pb = valuation.get("pb")

    # 行业：从 description 提取（inv-stock-data A 股快照不直接返回 industry）
    ak_xq_industry = None

    # --- daily bars for 5y percentile ---
    daily_data = _call_cs_stock("daily", plain)
    hist_5y = _bars_to_df(daily_data)
    if not hist_5y.empty:
        data_sources.append("inv-stock-data(daily)")

    # 从 daily bars 计算收盘价和收益率
    latest_close = None
    return_20d = None
    return_60d = None
    if not hist_5y.empty and "Close" in hist_5y.columns:
        closes = hist_5y["Close"].dropna()
        if len(closes) > 0:
            latest_close = float(closes.iloc[-1])
            return_20d = compute_period_return(hist_5y, 20)
            return_60d = compute_period_return(hist_5y, 60)

    price_percentile_5y = estimate_price_percentile(hist_5y)
    return_250d = compute_period_return(hist_5y, 250)
    # 从 daily bars 计算 52w 位置
    high_52w, low_52w, pos_52w, downside_to_52w = compute_52w_position(hist_5y)

    # --- announcements for event scoring ---
    ann_data = _call_cs_stock("announcements", plain)
    announcements = []
    if ann_data:
        if isinstance(ann_data, list):
            announcements = ann_data
        elif isinstance(ann_data, dict):
            announcements = ann_data.get("announcements", ann_data.get("items", []))
        if announcements:
            data_sources.append("inv-stock-data(announcements)")
    else:
        notes.append("inv-stock-data announcements 调用失败，事件评分可能不完整")

    # --- relations ---
    rel_data = _call_cs_stock("relations", plain)
    relations = []
    if rel_data:
        if isinstance(rel_data, list):
            relations = rel_data
        elif isinstance(rel_data, dict):
            relations = rel_data.get("relations", rel_data.get("items", []))
        if relations:
            data_sources.append("inv-stock-data(relations)")
    relation_count = len(relations)
    latest_relation_title = None
    if relation_count > 0 and isinstance(relations[0], dict):
        latest_relation_title = relations[0].get("title") or relations[0].get("公告标题")

    # --- raw announcements & relations (for LLM to interpret) ---
    raw_titles = []
    for item in announcements[:30]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("公告标题", ""))
        event_time_str = item.get("time") or item.get("date") or item.get("公告时间", "")
        if title:
            raw_titles.append({"title": title, "date": event_time_str})

    event_metrics = {
        "recent_announcements": raw_titles[:10],
        "relation_count_30d": relation_count,
        "latest_relation_title": latest_relation_title,
    }

    # --- assemble metrics ---
    metrics: dict[str, Any] = {
        "market_label": "A-share",
        "currency": "CNY",
        "sector": ak_xq_industry,
        "industry": ak_xq_industry,
        "current_price": safe_round(latest_close, 4),
        "latest_close": safe_round(latest_close, 4),
        "company_name": company_name,
        "ak_xq_industry": ak_xq_industry,
        "ak_ths_report_date": str(report_date) if report_date is not None else None,
        "ak_ths_roe_weighted_pct": safe_round(roe, 2),
        "ak_ths_gross_margin_pct": safe_round(gross_margin, 2),
        "ak_ths_net_margin_pct": safe_round(net_margin, 2),
        "ak_ths_debt_asset_ratio_pct": safe_round(debt_to_asset, 2),
        "valuation_pe_ttm": safe_round(pe_ttm, 2),
        "trailing_pe": safe_round(pe_ttm, 2),
        "valuation_pb": safe_round(pb, 2),
        "pb": safe_round(pb, 2),
        "sina_eps": safe_round(eps, 2) if eps is not None else None,
        "sina_bvps": safe_round(bvps, 2) if bvps is not None else None,
        "price_percentile_5y_proxy": price_percentile_5y,
        "return_20d_pct": safe_round(return_20d, 2),
        "return_60d_pct": safe_round(return_60d, 2),
        "return_250d_pct": return_250d,
        "high_52w": safe_round(high_52w, 4),
        "low_52w": safe_round(low_52w, 4),
        "position_in_52w_range_pct": pos_52w,
        "distance_to_52w_high_pct": downside_to_52w,
    }
    if description:
        metrics["profile_highlights"] = description

    metrics.update(event_metrics)

    # company_type_hint 由 LLM 根据 sector/industry 判断

    gaps = [k for k, v in metrics.items() if v is None]
    notes.extend(
        [
            "price_percentile_5y_proxy 为价格分位代理值，并非严格 PE/PB 历史分位。",
            "部分市场数据可能有 15-20 分钟延迟，建议在结论中标注时点。",
            "若 trailing_pe/pb 缺失，通常因亏损或数据源未提供。",
            "A股 / 港股 / 美股统一优先输出技能真正要用的估值、增长、质量、分位与财报时点字段。",
        ]
    )
    if not data_sources:
        data_sources.append("none")

    return Snapshot(
        symbol=symbol,
        normalized_symbol=normalized,
        company_name=company_name,
        currency="CNY",
        market="A-share",
        data_time=datetime.now().isoformat(timespec="seconds"),
        data_sources=data_sources,
        metrics=metrics,
        data_gaps=gaps,
        notes=notes,
    )


def _build_yahoo_snapshot(
    symbol: str,
    normalized: str,
    notes: list[str],
    data_sources: list[str],
) -> Snapshot:
    """Build snapshot for non-A-share (Yahoo) symbols via inv-stock-data.

    使用 `all` 子命令一次获取 snapshot + financial + financials，
    避免多次跨进程调用触发 Yahoo 限流。
    """

    # --- 一次调用获取全部数据 ---
    all_data = _call_cs_stock("all", normalized)

    snap = all_data.get("snapshot") or {}
    financial_data = all_data.get("financial") or {}
    financials_data = all_data.get("financials") or {}

    if snap and not snap.get("error"):
        data_sources.append("inv-stock-data(all→snapshot)")
    else:
        notes.append("inv-stock-data snapshot 调用失败，Yahoo 数据可能不完整")
    if financial_data and not financial_data.get("error"):
        data_sources.append("inv-stock-data(all→financial)")
    if financials_data and not financials_data.get("error"):
        data_sources.append("inv-stock-data(all→financials)")

    company_name = snap.get("name")
    sector = snap.get("sector")
    industry = snap.get("industry")
    current_price = snap.get("price")
    currency = snap.get("currency")

    # fundamentals（inv-stock-data Yahoo 快照的 key 名）
    fund = snap.get("fundamentals") or {}
    trailing_pe = fund.get("pe_trailing")
    forward_pe = fund.get("pe_forward")
    pb = fund.get("pb")
    market_cap = fund.get("market_cap")
    div_yield = fund.get("dividend_yield")
    roe = fund.get("roe")
    gross_margin = fund.get("gross_margins")
    net_margin = fund.get("profit_margins")
    revenue_growth = fund.get("revenue_growth")
    earnings_growth = fund.get("earnings_growth")

    # 从 financial 子命令补充更多字段
    fin_fund = financial_data.get("fundamentals") or {}
    if not trailing_pe:
        trailing_pe = fin_fund.get("pe_trailing")
    if not forward_pe:
        forward_pe = fin_fund.get("pe_forward")
    if not pb:
        pb = fin_fund.get("pb")
    if not market_cap:
        market_cap = fin_fund.get("market_cap")
    enterprise_value = fin_fund.get("enterprise_value")
    debt_to_equity = fin_fund.get("debt_to_equity")
    fcf = fin_fund.get("free_cashflow")
    total_debt = fin_fund.get("total_debt")
    total_cash = fin_fund.get("total_cash")
    shares_outstanding = fin_fund.get("shares_outstanding") or fin_fund.get("market_cap")
    operating_margin = fin_fund.get("operating_margins")
    ps = None
    ev_to_ebitda = None
    analyst_target_price = None
    analyst_count = None
    beta = None

    # --- daily bars for 5y percentile ---
    daily_data = _call_cs_stock("daily", normalized)
    hist_5y = _bars_to_df(daily_data)
    if not hist_5y.empty:
        data_sources.append("inv-stock-data(daily)")

    price_percentile_5y = estimate_price_percentile(hist_5y)
    latest_close = None if hist_5y.empty else float(hist_5y["Close"].dropna().iloc[-1]) if "Close" in hist_5y.columns else None
    return_20d = compute_period_return(hist_5y, 20)
    return_60d = compute_period_return(hist_5y, 60)
    return_250d = compute_period_return(hist_5y, 250)
    # 从 daily bars 计算 52w 位置
    high_52w, low_52w, pos_52w, downside_to_52w = compute_52w_position(hist_5y)

    # --- financial command for earnings data（已从 all 调用获取） ---
    next_earnings_date = None
    last_earnings_date = None
    last_surprise = None

    # --- raw earnings data (for LLM to interpret) ---
    event_metrics = {
        "last_surprise_pct": safe_round(last_surprise, 2),
        "next_earnings_date": next_earnings_date,
        "last_earnings_date": last_earnings_date,
    }

    # Determine market label from normalized symbol
    if normalized.endswith(".HK"):
        market = "HK"
    elif normalized.startswith("^"):
        market = "US-Index"
    else:
        market = "US"

    # --- assemble metrics ---
    current_price_value = safe_round(current_price, 4)
    analyst_upside_pct = None
    earnings_yield_pct = None
    if trailing_pe not in {None, 0}:
        earnings_yield_pct = safe_round(100 / float(trailing_pe), 2)
    price_to_fcf = None

    metrics = {
        "market_label": market,
        "currency": currency,
        "sector": sector,
        "industry": industry,
        "current_price": current_price_value,
        "latest_close": safe_round(latest_close, 4),
        "trailing_pe": safe_round(trailing_pe, 2),
        "forward_pe": safe_round(forward_pe, 2),
        "pb": safe_round(pb, 2),
        "ps_ttm": safe_round(ps, 2),
        "ev_ebitda": safe_round(ev_to_ebitda, 2),
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "total_debt": total_debt,
        "total_cash": total_cash,
        "shares_outstanding": shares_outstanding,
        "analyst_target_price": safe_round(analyst_target_price, 4),
        "analyst_upside_pct": analyst_upside_pct,
        "analyst_count": analyst_count,
        "next_earnings_date": next_earnings_date,
        "last_earnings_date": last_earnings_date,
        "dividend_yield_pct": normalize_dividend_yield(div_yield),
        "roe_pct": pct(roe),
        "gross_margin_pct": pct(gross_margin),
        "operating_margin_pct": pct(operating_margin),
        "net_margin_pct": pct(net_margin),
        "debt_to_equity": safe_round(debt_to_equity, 2),
        "revenue_growth_pct": pct(revenue_growth),
        "earnings_growth_pct": pct(earnings_growth),
        "free_cash_flow": fcf,
        "price_to_fcf": price_to_fcf,
        "earnings_yield_pct": earnings_yield_pct,
        "price_percentile_5y_proxy": price_percentile_5y,
        "return_20d_pct": return_20d,
        "return_60d_pct": return_60d,
        "return_250d_pct": return_250d,
        "high_52w": safe_round(high_52w, 4),
        "low_52w": safe_round(low_52w, 4),
        "position_in_52w_range_pct": pos_52w,
        "distance_to_52w_high_pct": downside_to_52w,
        "beta": safe_round(beta, 2),
    }
    metrics.update(event_metrics)

    # company_type_hint 由 LLM 根据 sector/industry 判断

    gaps = [k for k, v in metrics.items() if v is None]
    notes.extend(
        [
            "price_percentile_5y_proxy 为价格分位代理值，并非严格 PE/PB 历史分位。",
            "部分市场数据可能有 15-20 分钟延迟，建议在结论中标注时点。",
            "若 trailing_pe/pb 缺失，通常因亏损或数据源未提供。",
            "A股 / 港股 / 美股统一优先输出技能真正要用的估值、增长、质量、分位与财报时点字段。",
        ]
    )
    if not data_sources:
        data_sources.append("none")

    return Snapshot(
        symbol=symbol,
        normalized_symbol=normalized,
        company_name=company_name,
        currency=currency,
        market=market,
        data_time=datetime.now().isoformat(timespec="seconds"),
        data_sources=data_sources,
        metrics=metrics,
        data_gaps=gaps,
        notes=notes,
    )


def render_text(snapshot: Snapshot) -> str:
    lines = [
        "=" * 72,
        f"VALUE SNAPSHOT: {snapshot.normalized_symbol} ({snapshot.company_name or 'N/A'})",
        f"Data Time: {snapshot.data_time}",
        f"Data Sources: {', '.join(snapshot.data_sources)}",
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
            lines.append(f"- {g}")
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
        f"- 数据时点：{snapshot.data_time}",
        f"- 数据源：{', '.join(snapshot.data_sources)}",
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
                *[f"- {item}" for item in snapshot.data_gaps],
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
