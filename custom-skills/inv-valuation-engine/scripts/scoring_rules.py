"""Scoring rules for valuation, loaded from a single machine-readable source.

`scoring_rules.json` is the canonical source. This module only loads and
normalizes it for runtime use.
"""

from __future__ import annotations

import json
from pathlib import Path

Ranges = list[tuple[float | None, float | None, str]]

_CONFIG_PATH = Path(__file__).resolve().parent / "scoring_rules.json"
_CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def _to_ranges(rows: list[list]) -> Ranges:
    return [(row[0], row[1], row[2]) for row in rows]


PEG_RANGES: Ranges = _to_ranges(_CONFIG["ranges"]["peg"])
PERCENTILE_RANGES: Ranges = _to_ranges(_CONFIG["ranges"]["percentile"])
PS_RANGES: Ranges = _to_ranges(_CONFIG["ranges"]["ps"])
EARNINGS_YIELD_RANGES: Ranges = _to_ranges(_CONFIG["ranges"]["earnings_yield"])
ANALYST_UPSIDE_RANGES: Ranges = _to_ranges(_CONFIG["ranges"]["analyst_upside"])
PE_RANGES_BY_TYPE: dict[str, Ranges] = {
    name: _to_ranges(rows) for name, rows in _CONFIG["pe_ranges_by_type"].items()
}

DIVIDEND_YIELD_HIGH = float(_CONFIG["thresholds"]["dividend_yield_high"])
DIVIDEND_YIELD_MEDIUM = float(_CONFIG["thresholds"]["dividend_yield_medium"])
PB_ROE_THRESHOLD = float(_CONFIG["thresholds"]["pb_roe_threshold"])
FORWARD_PE_IMPLIED_GROWTH_LIMIT = float(_CONFIG["thresholds"]["forward_pe_implied_growth_limit"])
EARNINGS_GROWTH_HIGH = float(_CONFIG["thresholds"]["earnings_growth_high"])
EARNINGS_GROWTH_LOW = float(_CONFIG["thresholds"]["earnings_growth_low"])
