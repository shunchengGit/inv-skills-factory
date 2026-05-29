#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pandas>=2.0.0",
#   "requests>=2.28.0",
# ]
# ///
"""东方财富 push2 API 数据获取层。

提供实时报价、历史K线获取，以及纯碱期货合约自动切换。

代理管理：优先使用环境变量 HTTP_PROXY/HTTPS_PROXY，其次自动检测本地 Clash 端口。
东方财富为国内源，通常不需要代理；若设置了代理环境变量或检测到 Clash，则自动使用。
"""

import datetime
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from proxy import apply_proxy_to_session

BASE_URL_REALTIME = "https://push2.eastmoney.com/api/qt/stock/get"
BASE_URL_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}

KLINE_COLUMNS = [
    "date", "open", "close", "high", "low",
    "volume", "turnover", "amplitude", "pct_change", "change", "turnover_rate",
]


_SESSION = requests.Session()
_SESSION.headers.update(DEFAULT_HEADERS)
_SESSION.mount("https://", HTTPAdapter(pool_maxsize=6))
apply_proxy_to_session(_SESSION)

_MIN_REQUEST_INTERVAL = 0.3  # 请求间隔(秒)，避免触发限流
_last_request_time = 0.0

# 合约探测缓存：{(cache_key, date_str): secid}，按天有效
_secid_cache: dict[tuple[str, str], str] = {}

# API 响应缓存：{cache_key: (timestamp, data)}，TTL 5分钟
_api_cache: dict[str, tuple[float, dict]] = {}
_API_CACHE_TTL = 300  # 秒


def _throttle():
    """确保请求间隔不低于阈值。"""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def _cache_key(url: str, params: dict) -> str:
    """生成请求缓存键。"""
    # 按参数排序确保一致性
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return f"{url}?{sorted_params}"


def _request(url: str, params: dict, timeout: int = 10, retries: int = 2, use_cache: bool = True) -> dict:
    # 检查缓存
    if use_cache:
        key = _cache_key(url, params)
        now = time.monotonic()
        if key in _api_cache:
            cached_time, cached_data = _api_cache[key]
            if now - cached_time < _API_CACHE_TTL:
                return cached_data

    for attempt in range(retries + 1):
        _throttle()
        try:
            resp = _SESSION.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("rc") == 0 and data.get("data"):
                result = data["data"]
                if use_cache:
                    _api_cache[key] = (time.monotonic(), result)
                return result
            return {}
        except (requests.RequestException, json.JSONDecodeError):
            if attempt < retries:
                time.sleep(2)
            else:
                return {}
    return {}


def fetch_realtime(secid: str, fields: str, timeout: int = 10, use_cache: bool = True) -> dict:
    """获取实时报价。

    返回 {current, open, high, low, volume, turnover, code, name, timestamp}
    """
    data = _request(BASE_URL_REALTIME, {"secid": secid, "fields": fields}, timeout=timeout, use_cache=use_cache)
    if not data:
        return {}
    return {
        "current": data.get("f43"),
        "high": data.get("f44"),
        "low": data.get("f45"),
        "open": data.get("f46"),
        "volume": data.get("f47"),
        "turnover": data.get("f48"),
        "code": data.get("f57"),
        "name": data.get("f58"),
        "timestamp": data.get("f60"),
    }


def fetch_kline(
    secid: str,
    beg: str,
    end: str,
    klt: int = 101,
    fqt: int = 0,
    timeout: int = 15,
) -> pd.DataFrame:
    """获取日K线。

    返回 DataFrame[date,open,close,high,low,volume,turnover,amplitude,pct_change,change,turnover_rate]
    """
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": klt,
        "fqt": fqt,
        "beg": beg,
        "end": end,
    }
    data = _request(BASE_URL_KLINE, params, timeout=timeout)
    if not data or not data.get("klines"):
        return pd.DataFrame(columns=KLINE_COLUMNS)

    rows = []
    for line in data["klines"]:
        parts = line.split(",")
        if len(parts) >= 11:
            rows.append(parts[:11])

    if not rows:
        return pd.DataFrame(columns=KLINE_COLUMNS)

    df = pd.DataFrame(rows, columns=KLINE_COLUMNS)
    for col in ["open", "close", "high", "low", "volume", "turnover",
                "amplitude", "pct_change", "change", "turnover_rate"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def resolve_soda_ash_secid() -> str:
    """返回当前应使用的纯碱期货 secid。

    东方财富期货代码格式：SA + 1位年 + 2位月，如 SA607 = 2026年7月合约。
    连续合约 SA0 不被支持（返回 data=null）。

    策略：尝试最近3个交割月合约，取成交量最大的（主力合约）。
    结果按天缓存，避免重复探测。
    """
    today = datetime.date.today()
    cache_key = ("soda_ash", today.isoformat())
    if cache_key in _secid_cache:
        return _secid_cache[cache_key]

    contract_months = [1, 3, 5, 7, 9, 11]
    candidates = _build_candidates(today, contract_months)

    best_secid = None
    best_volume = -1

    for yr, cm in candidates[:3]:
        contract_code = f"{yr % 10}{cm:02d}"
        secid = f"115.SA{contract_code}"
        # 同时取价格和成交量，用成交量判断主力合约
        rt = fetch_realtime(secid, "f43,f47", use_cache=False)
        price = rt.get("current")
        volume = rt.get("volume") or 0
        if price and price > 0:
            if volume > best_volume:
                best_volume = volume
                best_secid = secid

    if best_secid:
        _secid_cache[cache_key] = best_secid
        return best_secid

    # fallback: 第一个有价格的
    yr, cm = candidates[0]
    secid = f"115.SA{contract_code}"
    _secid_cache[cache_key] = secid
    return secid


def resolve_ec_secid() -> str:
    """返回当前应使用的集运指数(欧线)期货 secid。

    东方财富期货代码格式：EC + 2位年 + 2位月，如 EC2606 = 2026年6月合约。
    注意：EC用的是2位年（与纯碱的1位年不同）。

    策略：尝试最近3个交割月合约，取成交量最大的（主力合约）。
    结果按天缓存，避免重复探测。
    """
    today = datetime.date.today()
    cache_key = ("ec", today.isoformat())
    if cache_key in _secid_cache:
        return _secid_cache[cache_key]

    contract_months = [2, 4, 6, 8, 10, 12]
    candidates = _build_candidates(today, contract_months)

    best_secid = None
    best_volume = -1

    for yr, cm in candidates[:3]:
        contract_code = f"{str(yr)[2:]}{cm:02d}"
        secid = f"142.EC{contract_code}"
        rt = fetch_realtime(secid, "f43,f47", use_cache=False)
        price = rt.get("current")
        volume = rt.get("volume") or 0
        if price and price > 0:
            if volume > best_volume:
                best_volume = volume
                best_secid = secid

    if best_secid:
        _secid_cache[cache_key] = best_secid
        return best_secid

    yr, cm = candidates[0]
    contract_code = f"{str(yr)[2:]}{cm:02d}"
    secid = f"142.EC{contract_code}"
    _secid_cache[cache_key] = secid
    return secid


def _build_candidates(today: datetime.date, contract_months: list[int]) -> list[tuple[int, int]]:
    """生成候选合约列表：当前月及之后的交割月。"""
    month = today.month
    candidates = []
    for cm in contract_months:
        if cm >= month:
            candidates.append((today.year, cm))
    while len(candidates) < 3:
        next_year = today.year + 1
        for cm in contract_months:
            candidates.append((next_year, cm))
            if len(candidates) >= 3:
                break
    return candidates


def calc_beg_date(lookback_days: int = 120) -> str:
    """计算历史K线的起始日期。"""
    d = datetime.date.today() - datetime.timedelta(days=lookback_days + 30)
    return d.strftime("%Y%m%d")


def today_str() -> str:
    """返回今天的日期字符串 YYYYMMDD。"""
    return datetime.date.today().strftime("%Y%m%d")
