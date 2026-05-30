"""市场识别 — 股票代码解析与格式转换。"""

from __future__ import annotations

import re

_A_SHARE_PREFIXES = {"0", "1", "2", "3", "4", "5", "6", "8", "9"}
_BSE_PREFIXES = {"4", "8"}  # 北交所


def parse_symbol(raw: str) -> tuple[str, str]:
    """解析用户输入的股票代码，返回 (code, market)。

    market: 'a' | 'etf' | 'hk' | 'us'
    """
    s = raw.strip().upper()
    # 港股：显式 .HK 后缀
    if s.endswith(".HK"):
        return s, "hk"
    # 港股：5位纯数字
    if re.fullmatch(r"\d{5}", s):
        return s, "hk"
    # 美股：纯字母（含 .B 等后缀如 BRK.B）
    if re.fullmatch(r"[A-Z]+(?:\.[A-Z])?", s):
        return s, "us"
    # A 股 / ETF：6位数字
    if re.fullmatch(r"\d{6}", s):
        first = s[0]
        if first in _BSE_PREFIXES and s[1] == "8":
            return s, "a"  # 北交所 4xxxxx / 8xxxxx
        if first in {"5", "2"}:
            return s, "etf"
        return s, "a"
    # 兜底：尝试当 A 股
    return s, "a"


def prefixed_sina(code: str, market: str) -> str:
    """返回新浪行情用的前缀代码，如 sh600519 / sz000001 / sh000001。"""
    if market == "a" or market == "etf":
        if code.startswith(("6", "5", "9")):
            return f"sh{code}"
        return f"sz{code}"
    return code


def to_yahoo_symbol(code: str, market: str) -> str:
    """将内部代码转为 Yahoo Finance 格式。

    A 股/ETF 不使用 Yahoo；港股 5 位数字需去前导零转为 4 位（Yahoo 不认 5 位）。
    例: 00700 → 0700.HK, 09988 → 9988.HK, 07709.HK → 7709.HK
    """
    if code.endswith(".HK"):
        # 去掉前导零：Yahoo 只认 4 位港股代码，07709.HK → 7709.HK
        base = code[:-3]  # "07709"
        if base.isdigit() and len(base) == 5 and base.startswith("0"):
            return f"{base[1:]}.HK"
        return code
    if market == "hk" and code.isdigit() and len(code) == 5 and code.startswith("0"):
        return f"{code[1:]}.HK"
    if market == "hk":
        return f"{code}.HK"
    return code  # 美股直接返回