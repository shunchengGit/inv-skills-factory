"""港美股数据获取 — yfinance 主路径 + akshare/Sina 降级路径。"""

from __future__ import annotations

import threading
import time
from pathlib import Path
import sys

import pandas as pd

from utils import safe_call

# 引入 _shared 代理模块
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from proxy import setup_proxy_env

# yfinance 请求间隔（秒），避免短时间密集请求触发 Yahoo 限流
_YF_CALL_INTERVAL = 3.0
_last_yf_call = 0.0
_throttle_lock = threading.Lock()


def _yf_throttle():
    """yfinance 调用前等待，确保请求间隔 >= _YF_CALL_INTERVAL 秒。线程安全。"""
    global _last_yf_call
    with _throttle_lock:
        elapsed = time.monotonic() - _last_yf_call
        if elapsed < _YF_CALL_INTERVAL:
            time.sleep(_YF_CALL_INTERVAL - elapsed)
        _last_yf_call = time.monotonic()


def fetch_yahoo_info(symbol: str) -> dict | None:
    """获取 Yahoo Finance 基本信息。"""
    import yfinance as yf
    _yf_throttle()
    try:
        tk = yf.Ticker(symbol)
        info = tk.info
        if not info or not info.get("regularMarketPrice"):
            return None
        return info
    except Exception:
        return None


def fetch_yahoo_history(symbol: str, period: str = "6mo") -> pd.DataFrame | None:
    """获取 Yahoo Finance 日K线。"""
    import yfinance as yf
    _yf_throttle()
    try:
        tk = yf.Ticker(symbol)
        hist = tk.history(period=period)
        if hist is None or hist.empty:
            return None
        return hist
    except Exception:
        return None


def fetch_hk_spot_symbol(code: str) -> dict | None:
    """从 AkShare 港股实时行情中查找指定股票。"""
    import akshare as ak
    df = safe_call(ak.stock_hk_spot)
    if df is None or df.empty:
        return None
    row = df[df["代码"] == code]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "name": str(r.get("名称", "")),
        "price": r.get("最新价"),
        "change_pct": r.get("涨跌幅"),
    }


def fetch_hk_daily_akshare(code: str) -> pd.DataFrame | None:
    """通过 AkShare 获取港股日K线。"""
    import akshare as ak
    df = safe_call(ak.stock_hk_hist, symbol=code, period="daily", adjust="qfq")
    return df


def fetch_hk_sina_spot(code: str) -> dict | None:
    """通过新浪获取港股实时行情（名称+价格）。东财屏蔽时的备选。"""
    import requests as req
    pure_code = code.upper().replace(".HK", "")
    sina_code = f"rt_hk{pure_code}"
    try:
        resp = req.get(
            f"https://hq.sinajs.cn/list={sina_code}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://stock.finance.sina.com.cn/"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        text = resp.text
        if f'hq_str_{sina_code}="' not in text:
            return None
        data = text.split('"')[1]
        fields = data.split(",")
        if len(fields) < 8:
            return None
        return {
            "name_en": fields[0],
            "name": fields[1] if len(fields) > 1 else fields[0],
            "price": float(fields[2]) if fields[2] else None,
            "open": float(fields[3]) if len(fields) > 3 and fields[3] else None,
            "high": float(fields[4]) if len(fields) > 4 and fields[4] else None,
            "low": float(fields[5]) if len(fields) > 5 and fields[5] else None,
            "prev_close": float(fields[6]) if len(fields) > 6 and fields[6] else None,
            "change_pct": float(fields[8]) if len(fields) > 8 and fields[8] else None,
            "turnover": float(fields[11]) if len(fields) > 11 and fields[11] else None,
            "volume": float(fields[12]) if len(fields) > 12 and fields[12] else None,
        }
    except Exception:
        return None


def fetch_hk_sina_daily(code: str) -> pd.DataFrame | None:
    """通过新浪获取港股日K线（stock_hk_daily）。东财屏蔽时的备选。"""
    import akshare as ak
    pure_code = code.upper().replace(".HK", "")
    df = safe_call(ak.stock_hk_daily, symbol=pure_code, adjust="qfq")
    if df is None or df.empty:
        return None
    if "date" in df.columns:
        df = df.sort_values("date")
    return df


def fetch_yahoo_financials(symbol: str) -> dict | None:
    """获取 Yahoo Finance 财务三表（利润表/资产负债表/现金流量表）。"""
    import yfinance as yf
    _yf_throttle()
    try:
        tk = yf.Ticker(symbol)
        result = {}
        inc = tk.income_stmt
        if inc is not None and not inc.empty:
            result["income_stmt"] = inc.to_dict(orient="dict")
        bs = tk.balance_sheet
        if bs is not None and not bs.empty:
            result["balance_sheet"] = bs.to_dict(orient="dict")
        cf = tk.cash_flow
        if cf is not None and not cf.empty:
            result["cash_flow"] = cf.to_dict(orient="dict")
        if not result:
            return None
        return result
    except Exception:
        return None


def fetch_us_daily_akshare(symbol: str) -> pd.DataFrame | None:
    """通过 AkShare 获取美股日K线。"""
    import akshare as ak
    df = safe_call(ak.stock_us_hist, symbol=symbol, period="daily", adjust="qfq")
    return df