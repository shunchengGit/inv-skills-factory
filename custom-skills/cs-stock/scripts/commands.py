"""命令编排 — 所有 cmd_* 子命令和 _fallback_* 降级函数。"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def cmd_snapshot_a(code: str) -> dict:
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


def cmd_snapshot_etf(code: str) -> dict:
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

    if nav_data and nav_data.get("latest_nav") is not None:
        nav = nav_data["latest_nav"]
        latest_close = None
        if result["daily"]:
            last_row = result["daily"][-1]
            latest_close = last_row.get("收盘") or last_row.get("close")
        premium = None
        if latest_close is not None and nav > 0:
            premium = round((latest_close - nav) / nav, 4)

        result["nav"] = {
            "latest": nav,
            "date": nav_data.get("latest_nav_date"),
            "acc_nav": nav_data.get("acc_nav"),
            "premium_pct": premium,
            "premium_label": (
                "溢价" if premium and premium > 0.005
                else "折价" if premium and premium < -0.005
                else "平价"
            ),
        }
        result["nav"]["nav_records"] = nav_data.get("nav_records", [])
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


def cmd_snapshot_yahoo(code: str, market: str) -> dict:
    """港股 / 美股 snapshot（Yahoo Finance 主路径，AkShare 降级）。"""
    from proxy import clear_proxy_env, restore_proxy_env

    yahoo_symbol = to_yahoo_symbol(code, market)
    _has_proxy = bool(os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"))

    # 并行获取 info 和 history，减少串行等待
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_info = executor.submit(fetch_yahoo_info, yahoo_symbol)
        future_hist = executor.submit(fetch_yahoo_history, yahoo_symbol)
        yahoo_info = future_info.result()
        yahoo_hist = future_hist.result()

    if yahoo_info and yahoo_hist is not None:
        # Yahoo 主路径成功
        info = yahoo_info
        name = info.get("shortName") or info.get("longName") or code
        fundamentals = {
            "pe_trailing": info.get("trailingPE"),
            "pe_forward": info.get("forwardPE"),
            "pb": info.get("priceToBook"),
            "market_cap": info.get("marketCap"),
            "dividend_yield": info.get("dividendYield"),
            "roe": info.get("returnOnEquity"),
            "gross_margins": info.get("grossMargins"),
            "profit_margins": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
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

    # Yahoo 失败，尝试降级
    clear_proxy_env()
    try:
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
    finally:
        restore_proxy_env()

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


def cmd_daily(code: str, market: str) -> dict:
    """日K线数据。"""
    if market in ("a", "etf"):
        if market == "etf":
            df = fetch_etf_daily(code)
        else:
            df = fetch_a_daily(code)
        name = ""
        if df is not None and not df.empty:
            last = df.iloc[-1]
            name = str(last.get("股票名称", ""))
            if name:
                _name_code_cache[name] = code
        return {
            "_command": "daily_a",
            "code": code,
            "name": name,
            "daily": ret_n(df, 20) if df is not None else [],
        }
    else:
        yahoo_symbol = to_yahoo_symbol(code, market)
        df = fetch_yahoo_history(yahoo_symbol, period="1y")
        if df is not None:
            return {
                "_command": "daily_yahoo",
                "code": code,
                "market": market,
                "daily": ret_n(df, 20),
            }
        # Yahoo 失败，降级
        if market == "hk":
            df2 = fetch_hk_sina_daily(code) or fetch_hk_daily_akshare(code)
        else:
            df2 = fetch_us_daily_akshare(code)
        return {
            "_command": "daily_yahoo",
            "code": code,
            "market": market,
            "daily": ret_n(df2, 20) if df2 is not None else [],
        }


def cmd_profile(code: str, market: str) -> dict:
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


def cmd_all(code: str, market: str = "a") -> dict:
    """一次调用获取 snapshot + financial + financials，避免跨进程重复建连和限流。"""
    result = {"_command": "all", "code": code, "market": market}

    if market == "etf":
        result["snapshot"] = cmd_snapshot_etf(code)
    elif market in ("hk", "us"):
        result["snapshot"] = cmd_snapshot_yahoo(code, market)
    else:
        result["snapshot"] = cmd_snapshot_a(code)

    result["financial"] = cmd_financial(code, market)
    result["financials"] = cmd_financials(code, market)

    return result


def cmd_financials(code: str, market: str = "a") -> dict:
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


def cmd_financial(code: str, market: str = "a") -> dict:
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
                    "dividend_yield": info.get("dividendYield"),
                    "roe": info.get("returnOnEquity"),
                    "roa": info.get("returnOnAssets"),
                    "gross_margins": info.get("grossMargins"),
                    "profit_margins": info.get("profitMargins"),
                    "operating_margins": info.get("operatingMargins"),
                    "revenue_growth": info.get("revenueGrowth"),
                    "earnings_growth": info.get("earningsGrowth"),
                    "debt_to_equity": info.get("debtToEquity"),
                    "free_cashflow": info.get("freeCashflow"),
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


def cmd_description(code: str) -> dict:
    """公司概况/主营业务。"""
    desc_data = fetch_a_description(code)
    return {
        "_command": "description",
        "code": code,
        "description": desc_data.get("description") if desc_data else None,
        "name": desc_data.get("name") if desc_data else None,
        "industry": desc_data.get("industry") if desc_data else None,
    }


def cmd_announcements(code: str) -> dict:
    """公告列表。"""
    announcements = fetch_announcements(code)
    return {
        "_command": "announcements",
        "code": code,
        "announcements": announcements or [],
    }


def cmd_index_daily(symbol: str) -> dict:
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


def cmd_relations(code: str) -> dict:
    """关联个股。"""
    relations = fetch_relations(code)
    return {
        "_command": "relations",
        "code": code,
        "relations": relations or [],
    }