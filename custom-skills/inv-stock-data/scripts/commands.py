"""命令编排 — 所有 cmd_* 子命令和 _fallback_* 降级函数。"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from data_contract import (
    VALID_PERIODS,
    aggregate_status,
    extract_date,
    historical_gaps,
    make_component,
    make_envelope,
    make_gap,
    make_source,
    make_symbol,
    make_window,
)
from utils import safe_call, ret_n, _name_code_cache, _etf_category_cache
from market import parse_symbol, prefixed_sina, to_yahoo_symbol
from fetch_ashare import (
    fetch_exchange_list, fetch_a_daily, fetch_ths_financial,
    fetch_baidu_valuation, fetch_sina_financial_indicator,
    fetch_a_description, fetch_announcements, fetch_relations,
)
from fetch_etf import fetch_etf_snapshot, fetch_etf_daily, fetch_etf_nav, fetch_etf_name
from fetch_yahoo import (
    fetch_yahoo_info, fetch_yahoo_history,
    fetch_yahoo_financials,
    fetch_hk_spot_symbol, fetch_hk_daily_akshare,
    fetch_hk_sina_spot, fetch_hk_sina_daily,
    fetch_us_daily_akshare,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from numeric import parse_number


def _ratio_to_pct(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number * 100, 4)


def _raw_snapshot_a(code: str) -> dict:
    """A 股 / 北交所 snapshot。"""
    # 并行获取所有数据源
    results = {}
    errors = {}

    def _task(name, fn, *args):
        try:
            results[name] = fn(*args)
        except Exception as e:
            errors[name] = str(e)[:200]

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(fetch_exchange_list, code): "exchange_list",
            executor.submit(fetch_a_daily, code): "daily",
            executor.submit(fetch_ths_financial, code): "financial",
            executor.submit(fetch_baidu_valuation, code): "valuation",
            executor.submit(fetch_sina_financial_indicator, code): "sina",
            executor.submit(fetch_a_description, code): "description",
        }
        for future in as_completed(futures):
            fname = futures[future]
            try:
                results[fname] = future.result()
            except Exception as e:
                errors[fname] = str(e)[:200]

    # 组装 payload
    exchange_info = results.get("exchange_list")
    name = exchange_info.get("name", code) if exchange_info else code

    desc_data = results.get("description")
    description = desc_data.get("description") if desc_data else None
    # cninfo 提供的名称和行业可补充 exchange_list 的缺失
    if desc_data:
        if not name or name == code:
            name = desc_data.get("name", name)
        if desc_data.get("industry"):
            industry_cninfo = desc_data["industry"]

    daily_df = results.get("daily")
    financial = results.get("financial")
    valuation = results.get("valuation")
    sina = results.get("sina")

    payload = {
        "_command": "snapshot_a",
        "code": code,
        "name": name,
        "industry": desc_data.get("industry") if desc_data else None,
        "daily": ret_n(daily_df, 5) if daily_df is not None else [],
        "financial": financial,
        "valuation": valuation,
        "sina": sina,
        "description": description,
    }

    notes = []
    if "daily" in errors:
        notes.append(f"日K线: {errors['daily']}")
    if "financial" in errors:
        notes.append(f"财务指标: {errors['financial']}")
    if "valuation" in errors:
        notes.append(f"估值: {errors['valuation']}")
    if "sina" in errors:
        notes.append(f"新浪财务: {errors['sina']}")
    if description is None:
        notes.append("公司概况: 未获取到")
    if notes:
        payload["_notes"] = notes

    return payload


def _raw_snapshot_etf(code: str) -> dict:
    """ETF snapshot。含日线行情 + 净值（折溢价判断）。"""
    etf_info = fetch_etf_name(code)
    daily_df = fetch_etf_daily(code)
    nav_data = fetch_etf_nav(code)

    name = etf_info.get("name", code) if etf_info else code
    category = etf_info.get("category", "") if etf_info else ""

    result = {
        "_command": "snapshot_etf",
        "code": code,
        "name": name,
        "category": category,
        "daily": ret_n(daily_df, 5) if daily_df is not None else [],
    }

    if nav_data and nav_data.get("latest") is not None:
        result["nav"] = {
            "latest": nav_data["latest"],
            "date": nav_data.get("date"),
            "acc_nav": nav_data.get("acc_nav"),
            "premium_pct": nav_data.get("premium_pct"),
            "premium_label": nav_data.get("premium_label", "平价"),
        }
    else:
        result["nav"] = None

    return result


def _fallback_hk_akshare(code: str) -> dict | None:
    """港股 AkShare 降级（东财源，可能被屏蔽）。"""
    hk_info = fetch_hk_spot_symbol(code)
    hk_daily_df = fetch_hk_daily_akshare(code)
    if hk_info is None and hk_daily_df is None:
        return None
    name = hk_info.get("name", code) if hk_info else code
    return {
        "name": name,
        "price": hk_info.get("price") if hk_info else None,
        "change_pct": hk_info.get("change_pct") if hk_info else None,
        "daily": ret_n(hk_daily_df, 5) if hk_daily_df is not None else [],
        "fundamentals": None,
        "_notes": ["已降级到 AkShare (东财源)"],
    }


def _fallback_hk_sina(code: str) -> dict | None:
    """港股新浪降级：新浪实时行情 + 新浪日K线。"""
    sina_spot = fetch_hk_sina_spot(code)
    sina_daily = fetch_hk_sina_daily(code)
    if sina_spot is None and sina_daily is None:
        return None
    name = sina_spot.get("name", code) if sina_spot else code
    notes = ["已降级到新浪港股源"]
    if sina_spot is None:
        notes.append("新浪实时行情不可用")
    return {
        "name": name,
        "price": sina_spot.get("price") if sina_spot else None,
        "change_pct": sina_spot.get("change_pct") if sina_spot else None,
        "daily": ret_n(sina_daily, 5) if sina_daily is not None else [],
        "fundamentals": None,
        "_notes": notes,
    }


def _fallback_us_akshare(symbol: str) -> dict | None:
    """美股 AkShare 降级：日线。"""
    us_daily_df = fetch_us_daily_akshare(symbol)
    if us_daily_df is None:
        return None
    return {
        "name": symbol,
        "daily": ret_n(us_daily_df, 5),
        "fundamentals": None,
    }


def _raw_snapshot_yahoo(code: str, market: str) -> dict:
    """港股 / 美股 snapshot（Yahoo Finance 主路径，AkShare 降级）。"""
    yahoo_symbol = to_yahoo_symbol(code, market)
    _has_proxy = bool(os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"))

    # 并行获取 info 和 history；单个源异常不中断整体（后续走降级路径）
    yahoo_info = None
    yahoo_hist = None
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(fetch_yahoo_info, yahoo_symbol): "info",
            executor.submit(fetch_yahoo_history, yahoo_symbol): "history",
        }
        for future in as_completed(futures):
            fname = futures[future]
            try:
                result = future.result()
            except Exception:
                continue
            if fname == "info":
                yahoo_info = result
            else:
                yahoo_hist = result

    if yahoo_info and yahoo_hist is not None:
        # Yahoo 主路径成功
        info = yahoo_info
        name = info.get("shortName") or info.get("longName") or code
        fundamentals = {
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "pb": info.get("priceToBook"),
            "market_cap": info.get("marketCap"),
            "dividend_yield_pct": _ratio_to_pct(info.get("dividendYield")),
            "roe_pct": _ratio_to_pct(info.get("returnOnEquity")),
            "gross_margin_pct": _ratio_to_pct(info.get("grossMargins")),
            "net_margin_pct": _ratio_to_pct(info.get("profitMargins")),
            "revenue_growth_pct": _ratio_to_pct(info.get("revenueGrowth")),
            "earnings_growth_pct": _ratio_to_pct(info.get("earningsGrowth")),
        }
        return {
            "_command": "snapshot_yahoo",
            "code": code,
            "market": market,
            "name": name,
            "price": info.get("regularMarketPrice"),
            "change_pct": info.get("regularMarketChangePercent"),
            "currency": info.get("currency"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "daily": ret_n(yahoo_hist, 5),
            "fundamentals": fundamentals,
        }

    # Yahoo 失败，尝试降级（AkShare 走代理也可用，无需清除代理）
    if market == "hk":
        fallback = _fallback_hk_sina(code) or _fallback_hk_akshare(code)
        if fallback:
            return {
                "_command": "snapshot_yahoo",
                "code": code,
                "market": market,
                "name": fallback["name"],
                "price": fallback.get("price"),
                "change_pct": fallback.get("change_pct"),
                "currency": "HKD",
                "sector": None,
                "industry": None,
                "daily": fallback.get("daily", []),
                "fundamentals": None,
                "_notes": fallback.get("_notes", ["Yahoo Finance 不可用，已降级"]),
            }
    else:
        fallback = _fallback_us_akshare(code)
        if fallback:
            return {
                "_command": "snapshot_yahoo",
                "code": code,
                "market": market,
                "name": fallback["name"],
                "price": None,
                "change_pct": None,
                "currency": "USD",
                "sector": None,
                "industry": None,
                "daily": fallback.get("daily", []),
                "fundamentals": None,
                "_notes": ["Yahoo Finance 不可用，已降级到 AkShare"],
            }

    err_notes = ["所有数据源均不可用"]
    if not _has_proxy:
        err_notes.append("代理缺失：未设置 HTTPS_PROXY，国内直连 Yahoo 被限流。请 export HTTPS_PROXY=http://127.0.0.1:7890 后重试")
    else:
        err_notes.append("代理已设置但 Yahoo + AkShare 均失败。可能 Clash 节点被限流或系统代理未开。尝试切换节点/检查代理设置后重试")
    return {
        "_command": "snapshot_yahoo",
        "code": code,
        "market": market,
        "name": code,
        "_notes": err_notes,
    }


def _period_start(last_date: object, period: str) -> object | None:
    if period == "max":
        return None
    try:
        last = pd.Timestamp(last_date)
    except Exception:
        return None
    offsets = {"1mo": pd.DateOffset(months=1), "1y": pd.DateOffset(years=1), "5y": pd.DateOffset(years=5)}
    return last - offsets[period]


def _filter_period(df, period: str):
    if df is None or df.empty or period == "max":
        return df
    date_column = next((name for name in ("date", "Date", "日期") if name in df.columns), None)
    if date_column is not None:
        dates = pd.to_datetime(df[date_column], errors="coerce", utc=True)
    else:
        dates = pd.to_datetime(df.index, errors="coerce", utc=True)
    valid_dates = dates.dropna()
    if valid_dates.empty:
        return df
    start = _period_start(valid_dates.max(), period)
    return df.loc[dates >= start] if start is not None else df


def _raw_daily(
    code: str,
    market: str,
    *,
    period: str = "1y",
    limit: int | None = None,
) -> tuple[dict, object | None, list[dict], list[dict]]:
    """获取日K线及来源状态，保留调用方请求的实际窗口。"""
    if period not in VALID_PERIODS:
        raise ValueError(f"不支持的 period: {period}")
    if limit is not None and limit <= 0:
        raise ValueError("limit 必须为正整数")

    sources: list[dict] = []
    gaps: list[dict] = []
    name = ""
    df = None

    if market in ("a", "etf"):
        df = fetch_etf_daily(code, n=None) if market == "etf" else fetch_a_daily(code, n=None)
        provider = "sina-etf" if market == "etf" else "sina"
        if df is not None and not df.empty:
            sources.append(make_source(provider, "ok"))
            last = df.iloc[-1]
            name = str(last.get("股票名称", ""))
            if name:
                _name_code_cache[name] = code
        else:
            sources.append(make_source(provider, "failed", reason="empty response"))
    else:
        yahoo_symbol = to_yahoo_symbol(code, market)
        df = fetch_yahoo_history(yahoo_symbol, period=period)
        if df is not None and not df.empty:
            sources.append(make_source("yahoo", "ok"))
        else:
            sources.append(make_source("yahoo", "failed", reason="history unavailable"))
            if market == "hk":
                df = fetch_hk_sina_daily(code)
                if df is not None and not df.empty:
                    sources.append(make_source("sina", "ok", fallback=True))
                else:
                    sources.append(make_source("sina", "failed", fallback=True, reason="history unavailable"))
                    df = fetch_hk_daily_akshare(code)
                    sources.append(make_source(
                        "akshare",
                        "ok" if df is not None and not df.empty else "failed",
                        fallback=True,
                        reason=None if df is not None and not df.empty else "history unavailable",
                    ))
            else:
                df = fetch_us_daily_akshare(code)
                sources.append(make_source(
                    "akshare",
                    "ok" if df is not None and not df.empty else "failed",
                    fallback=True,
                    reason=None if df is not None and not df.empty else "history unavailable",
                ))

    if df is None or df.empty:
        gaps.append(make_gap("all_sources_failed", "data.daily", "日线数据不可用", retryable=True))
        raw = {"name": name, "daily": []}
        return raw, None, sources, gaps

    df = _filter_period(df, period)
    if limit is not None:
        df = df.tail(limit)
    bars = ret_n(df, len(df))
    raw = {"name": name, "daily": bars}
    return raw, df, sources, gaps


def _raw_profile(code: str, market: str) -> dict:
    """公司基本信息。"""
    if market in ("a", "etf"):
        if market == "etf":
            info = fetch_etf_name(code)
            return {
                "_command": "profile_etf",
                "code": code,
                "name": info.get("name", "") if info else "",
                "category": info.get("category", "") if info else "",
            }
        exchange_info = fetch_exchange_list(code)
        desc_data = fetch_a_description(code)
        description_text = desc_data.get("description") if desc_data else None
        industry_from_cninfo = desc_data.get("industry") if desc_data else None
        return {
            "_command": "profile_a",
            "code": code,
            "name": desc_data.get("name") if desc_data else (exchange_info.get("name", "") if exchange_info else ""),
            "description": description_text,
            "industry": industry_from_cninfo,
        }
    else:
        yahoo_symbol = to_yahoo_symbol(code, market)
        info = fetch_yahoo_info(yahoo_symbol)
        if info:
            return {
                "_command": "profile_yahoo",
                "code": code,
                "market": market,
                "name": info.get("shortName") or info.get("longName") or "",
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "description": info.get("longBusinessSummary"),
                "website": info.get("website"),
                "employees": info.get("fullTimeEmployees"),
            }
        return {
            "_command": "profile_yahoo",
            "code": code,
            "market": market,
            "name": code,
            "_notes": ["Yahoo Finance 不可用"],
        }


def _raw_all(code: str, market: str = "a") -> dict:
    """一次调用获取 snapshot + financial + financials，避免跨进程重复建连和限流。"""
    result = {"_command": "all", "code": code, "market": market}

    if market == "etf":
        result["snapshot"] = _raw_snapshot_etf(code)
    elif market in ("hk", "us"):
        result["snapshot"] = _raw_snapshot_yahoo(code, market)
    else:
        result["snapshot"] = _raw_snapshot_a(code)

    result["financial"] = _raw_financial(code, market)
    result["financials"] = _raw_financials(code, market)

    return result


def _raw_financials(code: str, market: str = "a") -> dict:
    """财务三表（利润表/资产负债表/现金流量表）。美港股走 yfinance，A 股走 akshare。"""
    if market in ("hk", "us"):
        yahoo_symbol = to_yahoo_symbol(code, market)
        data = fetch_yahoo_financials(yahoo_symbol)
        if data:
            # yfinance DataFrame 列名是 Timestamp，转成字符串以便 JSON 序列化
            for table_name, table_data in data.items():
                if isinstance(table_data, dict):
                    data[table_name] = {str(k): v for k, v in table_data.items()}
            return {"_command": "financials", "code": code, "market": market, **data}
        return {"_command": "financials", "code": code, "market": market, "error": "Yahoo Finance 不可用"}

    # A 股：用 akshare 利润表 + 资产负债表
    import akshare as ak
    result = {}
    sina_code = prefixed_sina(code, "a")
    inc = safe_call(ak.stock_financial_report_sina, stock=sina_code, symbol="利润表")
    if inc is not None and not inc.empty:
        result["income_stmt"] = inc.to_dict(orient="records")[:4]
    bs = safe_call(ak.stock_financial_report_sina, stock=sina_code, symbol="资产负债表")
    if bs is not None and not bs.empty:
        result["balance_sheet"] = bs.to_dict(orient="records")[:4]
    cf = safe_call(ak.stock_financial_report_sina, stock=sina_code, symbol="现金流量表")
    if cf is not None and not cf.empty:
        result["cash_flow"] = cf.to_dict(orient="records")[:4]
    if not result:
        return {"_command": "financials", "code": code, "market": market, "error": "A 股财务三表不可用"}
    return {"_command": "financials", "code": code, "market": market, **result}


def _raw_financial(code: str, market: str = "a") -> dict:
    """财务指标。A 股走同花顺+新浪，美港股走 Yahoo Finance。"""
    if market in ("hk", "us"):
        yahoo_symbol = to_yahoo_symbol(code, market)
        yahoo_info = fetch_yahoo_info(yahoo_symbol)
        if yahoo_info:
            info = yahoo_info
            next_earnings_date = None
            earnings_dates_raw = info.get("earningsDates")
            if earnings_dates_raw and isinstance(earnings_dates_raw, list) and len(earnings_dates_raw) > 0:
                try:
                    from datetime import datetime as dt
                    next_earnings_date = dt.fromtimestamp(earnings_dates_raw[0]).strftime("%Y-%m-%d")
                except (ValueError, TypeError, OSError):
                    pass
            return {
                "_command": "financial",
                "code": code,
                "market": market,
                "fundamentals": {
                    "pe_trailing": info.get("trailingPE"),
                    "pe_forward": info.get("forwardPE"),
                    "pb": info.get("priceToBook"),
                    "market_cap": info.get("marketCap"),
                    "enterprise_value": info.get("enterpriseValue"),
                    "dividend_yield_pct": _ratio_to_pct(info.get("dividendYield")),
                    "roe_pct": _ratio_to_pct(info.get("returnOnEquity")),
                    "roa_pct": _ratio_to_pct(info.get("returnOnAssets")),
                    "gross_margin_pct": _ratio_to_pct(info.get("grossMargins")),
                    "net_margin_pct": _ratio_to_pct(info.get("profitMargins")),
                    "operating_margin_pct": _ratio_to_pct(info.get("operatingMargins")),
                    "revenue_growth_pct": _ratio_to_pct(info.get("revenueGrowth")),
                    "earnings_growth_pct": _ratio_to_pct(info.get("earningsGrowth")),
                    "debt_to_equity": info.get("debtToEquity"),
                    "free_cash_flow": info.get("freeCashflow"),
                    "total_revenue": info.get("totalRevenue"),
                    "total_cash": info.get("totalCash"),
                    "total_debt": info.get("totalDebt"),
                },
                "next_earnings_date": next_earnings_date,
                "last_surprise_pct": None,
                "_notes": ["美港股财务数据来自 Yahoo Finance，字段覆盖率不如 A 股；last_surprise_pct 需通过 snapshot 获取"],
            }
        return {
            "_command": "financial",
            "code": code,
            "market": market,
            "error": "Yahoo Finance 不可用",
        }

    financial = fetch_ths_financial(code)
    sina = fetch_sina_financial_indicator(code)
    return {
        "_command": "financial",
        "code": code,
        "market": market,
        "ths_financial": financial,
        "sina_financial": sina,
    }


def _raw_description(code: str) -> dict:
    """公司概况/主营业务。"""
    desc_data = fetch_a_description(code)
    return {
        "_command": "description",
        "code": code,
        "description": desc_data.get("description") if desc_data else None,
        "name": desc_data.get("name") if desc_data else None,
        "industry": desc_data.get("industry") if desc_data else None,
    }


def _raw_announcements(code: str) -> dict:
    """公告列表。"""
    announcements = fetch_announcements(code)
    return {
        "_command": "announcements",
        "code": code,
        "announcements": announcements or [],
    }


def _raw_index_daily(symbol: str) -> dict:
    """A 股指数日K线。symbol 可以是代码（如 000300）或带前缀（如 sh000300）。"""
    import akshare as ak
    code = symbol.lstrip("shsz").strip()
    df = None
    # 尝试带市场前缀
    for prefix in (["sh", "sz"] if code.startswith(("0", "9")) else ["sz", "sh"]):
        df = safe_call(ak.stock_zh_index_daily_em, symbol=f"{prefix}{code}")
        if df is not None and not df.empty:
            break
    if df is None or df.empty:
        return {"_command": "index_daily", "code": code, "bars": [], "error": "指数日线数据不可用"}
    keep = [c for c in ["date", "open", "close", "high", "low", "volume"] if c in df.columns]
    df = df[keep].tail(300)
    bars = df.to_dict(orient="records")
    return {"_command": "index_daily", "code": code, "bars": bars}


def _raw_relations(code: str) -> dict:
    """关联个股。"""
    relations = fetch_relations(code)
    return {
        "_command": "relations",
        "code": code,
        "relations": relations or [],
    }


def _symbol(code: str, market: str, raw_symbol: str | None = None) -> dict:
    return make_symbol(raw_symbol or code, code, market)


def _last_date(rows: list[dict], *keys: str) -> str | None:
    if not rows:
        return None
    row = rows[-1]
    for key in keys:
        if row.get(key) is not None:
            return extract_date(row[key])
    return None


def _provider_status(has_data: bool, field: str, reason: str) -> tuple[str, list[dict]]:
    if has_data:
        return "ok", []
    return "failed", [make_gap("provider_unavailable", field, reason, retryable=True)]


def cmd_snapshot_a(code: str, *, raw_symbol: str | None = None) -> dict:
    raw = _raw_snapshot_a(code)
    daily = raw.get("daily") or []
    meaningful = any((raw.get("name") not in (None, "", code), daily, raw.get("financial"), raw.get("valuation"), raw.get("sina"), raw.get("description")))
    gaps = []
    if not raw.get("description"):
        gaps.append(make_gap("field_unavailable", "data.description", "公司概况不可用", retryable=True))
    if not raw.get("valuation"):
        gaps.append(make_gap("field_unavailable", "data.valuation", "估值数据不可用", retryable=True))
    if not meaningful:
        gaps = [make_gap("all_sources_failed", "data", "A 股快照数据不可用", retryable=True)]
    status = "failed" if not meaningful else "partial" if gaps else "ok"
    financial = raw.get("financial") or {}
    sina = raw.get("sina") or {}
    valuation = raw.get("valuation") or {}

    def local_number(value: object) -> float | None:
        return parse_number(value)

    revenue = local_number(sina.get("营业总收入") or sina.get("营业收入"))
    cost = local_number(sina.get("营业成本"))
    net_profit = local_number(sina.get("归属于母公司所有者的净利润") or sina.get("净利润"))
    gross_margin = local_number(financial.get("销售毛利率"))
    if gross_margin is None and revenue and cost is not None:
        gross_margin = round((revenue - cost) / revenue * 100, 4)
    net_margin = local_number(financial.get("销售净利率"))
    if net_margin is None and revenue and net_profit is not None:
        net_margin = round(net_profit / revenue * 100, 4)
    fundamentals = {
        "pe_trailing": local_number(valuation.get("pe_ttm")),
        "pe_static": local_number(valuation.get("pe_static")),
        "pb": local_number(valuation.get("pb")),
        "roe_pct": local_number(financial.get("净资产收益率")),
        "gross_margin_pct": gross_margin,
        "net_margin_pct": net_margin,
        "debt_to_asset_pct": local_number(financial.get("资产负债率")),
        "revenue_growth_pct": local_number(financial.get("营业总收入同比增长率")),
        "earnings_growth_pct": local_number(financial.get("净利润同比增长率")),
    }
    data = {} if status == "failed" else {
        "name": raw.get("name"),
        "industry": raw.get("industry"),
        "price": (daily[-1].get("close") if daily else None),
        "currency": "CNY",
        "daily": daily,
        "financial": financial,
        "valuation": valuation,
        "sina": sina,
        "fundamentals": fundamentals,
        "description": raw.get("description"),
    }
    return make_envelope(
        "snapshot", status, _symbol(code, "a", raw_symbol), data,
        data_as_of=_last_date(daily, "date", "日期"),
        sources=[make_source("akshare", "ok" if meaningful else "failed", reason=None if meaningful else "snapshot unavailable")],
        gaps=gaps,
        notes=raw.get("_notes") or [],
    )


def cmd_snapshot_etf(code: str, *, raw_symbol: str | None = None) -> dict:
    raw = _raw_snapshot_etf(code)
    daily = raw.get("daily") or []
    nav = raw.get("nav")
    meaningful = any((raw.get("name") not in (None, "", code), daily, nav))
    gaps = []
    if not daily:
        gaps.append(make_gap("field_unavailable", "data.daily", "ETF 日线不可用", retryable=True))
    if nav is None:
        gaps.append(make_gap("field_unavailable", "data.nav", "ETF 净值不可用", retryable=True))
    if not meaningful:
        gaps = [make_gap("all_sources_failed", "data", "ETF 快照数据不可用", retryable=True)]
    status = "failed" if not meaningful else "partial" if gaps else "ok"
    data = {} if status == "failed" else {
        "name": raw.get("name"),
        "category": raw.get("category"),
        "price": (daily[-1].get("close") if daily else None),
        "currency": "CNY",
        "daily": daily,
        "nav": nav,
    }
    sources = [make_source("sina", "ok" if daily else "failed", reason=None if daily else "daily unavailable")]
    sources.append(make_source("eastmoney-nav", "ok" if nav else "failed", reason=None if nav else "nav unavailable"))
    return make_envelope(
        "snapshot", status, _symbol(code, "etf", raw_symbol), data,
        data_as_of=(nav or {}).get("date") or _last_date(daily, "date", "日期"),
        sources=sources,
        gaps=gaps,
    )


def cmd_snapshot_yahoo(code: str, market: str, *, raw_symbol: str | None = None) -> dict:
    raw = _raw_snapshot_yahoo(code, market)
    daily = raw.get("daily") or []
    failed = raw.get("name") == code and not any((raw.get("price"), daily, raw.get("fundamentals")))
    fallback = bool(raw.get("_notes")) and not failed
    gaps = []
    if failed:
        gaps.append(make_gap("all_sources_failed", "data", "所有港美股数据源均不可用", retryable=True))
    elif fallback:
        gaps.append(make_gap("provider_unavailable", "data.fundamentals", "Yahoo 不可用，降级源无完整基本面", retryable=True))
    status = "failed" if failed else "partial" if fallback else "ok"
    sources = [make_source("yahoo", "failed" if fallback or failed else "ok", reason="snapshot unavailable" if fallback or failed else None)]
    if fallback:
        provider = "sina" if market == "hk" and any("新浪" in note for note in raw.get("_notes", [])) else "akshare"
        sources.append(make_source(provider, "ok", fallback=True))
    elif failed:
        sources.append(make_source("akshare", "failed", fallback=True, reason="fallback unavailable"))
    data = {} if failed else {
        "name": raw.get("name"),
        "price": raw.get("price"),
        "change_pct": raw.get("change_pct"),
        "currency": raw.get("currency"),
        "sector": raw.get("sector"),
        "industry": raw.get("industry"),
        "description": raw.get("description"),
        "daily": daily,
        "fundamentals": raw.get("fundamentals"),
    }
    return make_envelope(
        "snapshot", status, _symbol(code, market, raw_symbol), data,
        data_as_of=_last_date(daily, "date", "Date"),
        sources=sources,
        gaps=gaps,
        notes=raw.get("_notes") or [],
    )


def cmd_daily(
    code: str,
    market: str,
    *,
    period: str = "1y",
    limit: int | None = None,
    raw_symbol: str | None = None,
) -> dict:
    raw, _df, sources, gaps = _raw_daily(code, market, period=period, limit=limit)
    daily = raw["daily"]
    first = _last_date(daily[:1], "date", "Date", "日期")
    last = _last_date(daily, "date", "Date", "日期")
    window = make_window(period, len(daily), first, last)
    if period == "5y" and daily and historical_gaps(window):
        gaps.append(make_gap("insufficient_period_coverage", "window", "实际历史覆盖不足请求的五年窗口", retryable=True))
    if daily and any(s["fallback"] for s in sources if s["status"] == "ok"):
        gaps.append(make_gap("fallback_used", "sources", "主日线来源不可用，已使用降级来源", retryable=True))
    status = "failed" if not daily else "partial" if gaps else "ok"
    data = {} if status == "failed" else {"name": raw.get("name"), "daily": daily}
    return make_envelope(
        "daily", status, _symbol(code, market, raw_symbol), data,
        data_as_of=last, sources=sources, gaps=gaps, window=window,
    )


def _wrap_raw(
    command: str,
    code: str,
    market: str,
    raw: dict,
    data: dict,
    *,
    provider: str,
    raw_symbol: str | None = None,
    has_data: bool | None = None,
) -> dict:
    if has_data is None:
        has_data = bool(data) and not raw.get("error")
    status, gaps = _provider_status(has_data, "data", raw.get("error") or f"{command} 数据不可用")
    return make_envelope(
        command, status, _symbol(code, market, raw_symbol), data if has_data else {},
        sources=[make_source(provider, status, reason=raw.get("error"))],
        gaps=gaps,
        notes=raw.get("_notes") or [],
    )


def cmd_profile(code: str, market: str, *, raw_symbol: str | None = None) -> dict:
    raw = _raw_profile(code, market)
    data = {key: raw.get(key) for key in ("name", "category", "sector", "industry", "description", "website", "employees")}
    has_data = any(value not in (None, "", code) for value in data.values())
    return _wrap_raw("profile", code, market, raw, data, provider="yahoo" if market in ("hk", "us") else "akshare", raw_symbol=raw_symbol, has_data=has_data)


def cmd_financial(code: str, market: str = "a", *, raw_symbol: str | None = None) -> dict:
    raw = _raw_financial(code, market)
    data = {key: raw.get(key) for key in ("fundamentals", "next_earnings_date", "last_surprise_pct", "ths_financial", "sina_financial") if key in raw}
    has_data = any(value for value in data.values())
    return _wrap_raw("financial", code, market, raw, data, provider="yahoo" if market in ("hk", "us") else "akshare", raw_symbol=raw_symbol, has_data=has_data)


def cmd_financials(code: str, market: str = "a", *, raw_symbol: str | None = None) -> dict:
    raw = _raw_financials(code, market)
    data = {key: raw.get(key) for key in ("income_stmt", "balance_sheet", "cash_flow") if raw.get(key)}
    return _wrap_raw("financials", code, market, raw, data, provider="yahoo" if market in ("hk", "us") else "akshare", raw_symbol=raw_symbol, has_data=bool(data))


def cmd_description(code: str, *, raw_symbol: str | None = None) -> dict:
    raw = _raw_description(code)
    data = {key: raw.get(key) for key in ("name", "industry", "description")}
    return _wrap_raw("description", code, "a", raw, data, provider="akshare", raw_symbol=raw_symbol, has_data=bool(raw.get("description")))


def cmd_announcements(code: str, *, raw_symbol: str | None = None) -> dict:
    raw = _raw_announcements(code)
    return _wrap_raw("announcements", code, "a", raw, {"announcements": raw["announcements"]}, provider="akshare", raw_symbol=raw_symbol, has_data=bool(raw["announcements"]))


def cmd_relations(code: str, *, raw_symbol: str | None = None) -> dict:
    raw = _raw_relations(code)
    return _wrap_raw("relations", code, "a", raw, {"relations": raw["relations"]}, provider="akshare", raw_symbol=raw_symbol, has_data=bool(raw["relations"]))


def cmd_index_daily(symbol: str, *, period: str = "1y", limit: int | None = None) -> dict:
    raw = _raw_index_daily(symbol)
    bars = raw.get("bars") or []
    if bars:
        df = pd.DataFrame(bars)
        df = _filter_period(df, period)
        bars = df.to_dict(orient="records")
    if limit is not None:
        bars = bars[-limit:]
    code = raw.get("code") or symbol
    first = _last_date(bars[:1], "date")
    last = _last_date(bars, "date")
    status, gaps = _provider_status(bool(bars), "data.bars", raw.get("error") or "指数日线不可用")
    return make_envelope(
        "index-daily", status, make_symbol(symbol, code, "index"), {"bars": bars} if bars else {},
        data_as_of=last,
        sources=[make_source("akshare", status, reason=raw.get("error"))],
        gaps=gaps,
        window=make_window(period, len(bars), first, last),
    )


def cmd_all(code: str, market: str = "a", *, raw_symbol: str | None = None) -> dict:
    snapshot = (
        cmd_snapshot_etf(code, raw_symbol=raw_symbol)
        if market == "etf"
        else cmd_snapshot_yahoo(code, market, raw_symbol=raw_symbol)
        if market in ("hk", "us")
        else cmd_snapshot_a(code, raw_symbol=raw_symbol)
    )
    financial = cmd_financial(code, market, raw_symbol=raw_symbol)
    financials = cmd_financials(code, market, raw_symbol=raw_symbol)
    children = {"snapshot": snapshot, "financial": financial, "financials": financials}
    statuses = [payload["status"] for payload in children.values()]
    status = aggregate_status(statuses)
    gaps = [gap for payload in children.values() for gap in payload["gaps"]]
    sources = [source for payload in children.values() for source in payload["sources"]]
    dates = [payload.get("data_as_of") for payload in children.values() if payload.get("data_as_of")]
    return make_envelope(
        "all", status, _symbol(code, market, raw_symbol),
        {"components": {name: make_component(payload) for name, payload in children.items()}},
        data_as_of=max(dates) if dates else None,
        sources=sources,
        gaps=gaps,
    )