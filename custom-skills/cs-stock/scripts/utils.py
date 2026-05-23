"""通用工具 — 安全调用、DataFrame 截取、格式化。"""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

import pandas as pd


_name_code_cache: dict[str, str] = {}
_etf_category_cache: dict[str, str] = {}


def safe_call(fn, *args, default=None, **kwargs):
    """调用 AkShare 函数，吞掉 stdout/stderr 噪音，失败返回 default。"""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            result = fn(*args, **kwargs)
        return result
    except Exception:
        return default


def ret_n(df: pd.DataFrame, n: int = 5) -> list[dict]:
    """DataFrame -> list[dict], preserve date column, lowercase column names."""
    if df is None or df.empty:
        return []
    df = df.copy()
    if df.index.name in ("Date", "date", None) and "date" not in df.columns:
        df = df.reset_index()
        if "Date" in df.columns:
            df.rename(columns={"Date": "date"}, inplace=True)
        elif "index" in df.columns:
            df.rename(columns={"index": "date"}, inplace=True)
    rename = {}
    for c in df.columns:
        if c.lower() != c and c.lower() not in df.columns:
            rename[c] = c.lower()
    df.rename(columns=rename, inplace=True)
    return df.tail(n).to_dict(orient="records")


def _fmt_pct(val) -> str:
    """格式化百分比，None 返回 '-'。"""
    if val is None:
        return "-"
    try:
        return f"{float(val):.2f}%"
    except (ValueError, TypeError):
        return "-"


def _fmt_num(val, decimals=2) -> str:
    """格式化数字，None 返回 '-'。"""
    if val is None:
        return "-"
    try:
        return f"{float(val):,.{decimals}f}"
    except (ValueError, TypeError):
        return "-"


def _float_or_none(val) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None