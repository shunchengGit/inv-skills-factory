"""A 股 / 北交所数据获取 + 公告 / 关联。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from utils import safe_call, ret_n, _name_code_cache
from market import prefixed_sina


def fetch_exchange_list(code: str) -> dict | None:
    """从交易所列表获取股票名称和行业。"""
    import akshare as ak
    df = safe_call(ak.stock_info_a_code_name)
    if df is None or df.empty:
        return None
    row = df[df["code"] == code]
    if row.empty:
        return None
    r = row.iloc[0]
    name = str(r.get("name", ""))
    _name_code_cache[name] = code
    return {"name": name}


def fetch_a_daily(code: str, n: int | None = None) -> pd.DataFrame | None:
    """获取 A 股/北交所日K线。新浪源（stock_zh_a_daily），避免东财 API 反爬。"""
    import akshare as ak
    sina_code = prefixed_sina(code, "a")
    df = safe_call(ak.stock_zh_a_daily, symbol=sina_code, adjust="qfq")
    if df is None or df.empty:
        return None
    if "date" in df.columns:
        df = df.sort_values("date")
    return df.tail(n) if n is not None and len(df) > n else df


def fetch_ths_financial(code: str) -> dict | None:
    """获取同花顺主要财务指标。"""
    import akshare as ak
    df = safe_call(ak.stock_financial_abstract_ths, symbol=code, indicator="按报告期")
    if df is None or df.empty:
        return None
    latest = df.iloc[0].to_dict()
    return latest


def fetch_baidu_valuation(code: str) -> dict | None:
    """获取百度估值指标（PE/PB/PCR/市值）。新版 akshare API，每个指标独立查询。"""
    import akshare as ak
    result = {}
    indicators = {
        "pe_static": ("市盈率(静)", "近一年"),
        "pe_ttm": ("市盈率", "近一年"),
        "pb": ("市净率", "近一年"),
    }

    def _fetch_one(key: str, indicator: str, period: str):
        df = safe_call(ak.stock_zh_valuation_baidu, symbol=code, indicator=indicator, period=period)
        if df is not None and not df.empty and "value" in df.columns:
            try:
                val = float(df.iloc[-1]["value"])
                if key == "total_mv":
                    val = val * 100000000  # 亿→元
                return key, val
            except (ValueError, TypeError, IndexError):
                pass
        return key, None

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_fetch_one, key, indicator, period): key
            for key, (indicator, period) in indicators.items()
        }
        for future in as_completed(futures):
            key, val = future.result()
            if val is not None:
                result[key] = val

    return result if result else None


def fetch_sina_financial_indicator(code: str) -> dict | None:
    """获取新浪财务指标（ROE/毛利率/净利率等）。"""
    import akshare as ak
    sina_code = prefixed_sina(code, "a")
    df = safe_call(ak.stock_financial_report_sina, stock=sina_code, symbol="利润表")
    if df is None or df.empty:
        return None
    return df.iloc[0].to_dict() if len(df) > 0 else None


def _fallback_description_em(code: str) -> dict | None:
    """东财公司概况（巨潮被限流时的降级源）。"""
    import akshare as ak
    df = safe_call(ak.stock_individual_info_em, symbol=code)
    if df is None or df.empty:
        return None
    # 东财返回两列：item / value，转为 dict
    info = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
    desc = info.get("公司概况") or info.get("经营范围")
    return {
        "name": info.get("股票简称", ""),
        "description": str(desc) if desc else None,
        "industry": info.get("行业"),
        "full_name": info.get("公司名称", ""),
        "listing_date": info.get("上市时间", ""),
    }


def fetch_a_description(code: str) -> dict | None:
    """获取 A 股公司概况。源1: cninfo（巨潮），源2: 东财降级。"""
    import akshare as ak
    df = safe_call(ak.stock_profile_cninfo, symbol=code)
    if df is not None and not df.empty:
        row = df.iloc[0]
        desc = row.get("主营业务") or row.get("经营范围") or row.get("机构简介")
        industry = row.get("所属行业")
        return {
            "name": row.get("A股简称") or row.get("公司名称", ""),
            "description": str(desc) if desc else None,
            "industry": str(industry) if industry else None,
            "full_name": str(row.get("公司名称", "")),
            "listing_date": str(row.get("上市日期", "")),
            "website": str(row.get("官方网站", "")),
        }
    # 巨潮被限流，走东财降级
    return _fallback_description_em(code)


def fetch_announcements(code: str) -> list[dict] | None:
    """获取最新公告列表。"""
    import akshare as ak
    df = safe_call(ak.stock_notice_report, symbol=code)
    if df is None or df.empty:
        return None
    return ret_n(df, 10)


def fetch_relations(code: str) -> list[dict] | None:
    """获取关联个股（同行业/同概念）。"""
    import akshare as ak
    df = safe_call(ak.stock_board_industry_name_em)
    if df is None or df.empty:
        return None
    for _, row in df.iterrows():
        board_name = str(row.get("板块名称", ""))
        members = safe_call(ak.stock_board_industry_cons_em, symbol=board_name)
        if members is not None and not members.empty:
            if code in members["代码"].values:
                return ret_n(members, 10)
    return None
