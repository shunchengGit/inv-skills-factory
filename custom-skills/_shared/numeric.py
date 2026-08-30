"""Numeric parsing helpers shared across inv-* skills."""

from __future__ import annotations


def parse_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().replace(",", "")
    if not s:
        return None

    multiplier = 1.0
    if "万亿" in s:
        multiplier = 1e12
        s = s.replace("万亿", "")
    elif "亿" in s:
        multiplier = 1e8
        s = s.replace("亿", "")
    elif "万" in s:
        multiplier = 1e4
        s = s.replace("万", "")

    if s.endswith("%"):
        s = s[:-1]
    s = s.strip()
    if not s:
        return None

    try:
        return float(s) * multiplier
    except ValueError:
        return None


def parse_percent(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if v > 1 else round(v * 100, 2)

    s = str(value).strip().rstrip("%").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None
