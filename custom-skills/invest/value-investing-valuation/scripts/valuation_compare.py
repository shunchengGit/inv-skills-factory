#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "yfinance>=0.2.40",
#   "pandas>=2.0.0",
#   "akshare>=1.13.0",
# ]
# ///
"""
对多只股票做相对估值比较。

示例:
  python3 valuation_compare.py 002475 601138 002241 --company-type tech --proxy http://127.0.0.1:7890
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from typing import Any

from valuation_report import RATING_SCORE, generate_report_from_snapshot
from valuation_snapshot import build_snapshot


@dataclass
class CompareRow:
    symbol: str
    company_name: str | None
    conclusion: str
    confidence: str
    pe: float | None
    pb: float | None
    ps: float | None
    peg: float | None
    earnings_growth_pct: float | None
    percentile_proxy: float | None
    action: str


@dataclass
class CompareResult:
    symbols: list[str]
    company_type: str
    ranking_summary: list[str]
    rows: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="多股票相对估值比较")
    parser.add_argument("symbols", nargs="+", help="股票代码列表，如 002475 601138 002241")
    parser.add_argument(
        "--company-type",
        default="auto",
        choices=["auto", "consumer", "internet", "tech", "cyclical", "financial", "distressed"],
        help="可选公司类型覆盖",
    )
    parser.add_argument("--output", default="text", choices=["text", "json", "markdown"], help="输出格式")
    return parser.parse_args()


def _get_metric(report: Any, name: str) -> float | None:
    for item in report.metrics_used:
        if item["name"] == name:
            return item["value"]
    return None


def build_row(report: Any, snapshot_metrics: dict[str, Any]) -> CompareRow:
    return CompareRow(
        symbol=report.symbol,
        company_name=report.company_name,
        conclusion=report.conclusion,
        confidence=report.confidence,
        pe=_get_metric(report, "PE锚"),
        pb=snapshot_metrics.get("pb"),
        ps=_get_metric(report, "PS(TTM)"),
        peg=_get_metric(report, "PEG"),
        earnings_growth_pct=snapshot_metrics.get("earnings_growth_pct"),
        percentile_proxy=_get_metric(report, "历史分位代理"),
        action=report.action_reference,
    )


def sort_rows(rows: list[CompareRow]) -> list[CompareRow]:
    def key_fn(row: CompareRow) -> tuple[float, float, float]:
        rating_score = RATING_SCORE.get(row.conclusion, 2)
        percentile = row.percentile_proxy if row.percentile_proxy is not None else 50.0
        peg = row.peg if row.peg is not None else 1.2
        return (rating_score, percentile, peg)

    return sorted(rows, key=key_fn)


def build_summary(rows: list[CompareRow]) -> list[str]:
    if not rows:
        return ["无可比数据。"]

    cheapest = rows[0]
    richest = rows[-1]
    summary = [
        f"按综合排序相对更便宜：{cheapest.symbol} {cheapest.company_name or ''}，当前结论为“{cheapest.conclusion}”。".strip(),
        f"按综合排序相对更不便宜：{richest.symbol} {richest.company_name or ''}，当前结论为“{richest.conclusion}”。".strip(),
    ]

    pe_rows = [r for r in rows if r.pe is not None]
    if pe_rows:
        best_pe = min(pe_rows, key=lambda x: x.pe or 9999)
        summary.append(f"PE 锚最低的是 {best_pe.symbol}，PE={best_pe.pe}。")

    peg_rows = [r for r in rows if r.peg is not None]
    if peg_rows:
        best_peg = min(peg_rows, key=lambda x: x.peg or 9999)
        summary.append(f"PEG 最优的是 {best_peg.symbol}，PEG={best_peg.peg}。")
    return summary[:4]


def generate_compare(symbols: list[str], company_type_override: str) -> CompareResult:
    rows: list[CompareRow] = []
    final_company_type = ""
    for symbol in symbols:
        snapshot = build_snapshot(symbol)
        report = generate_report_from_snapshot(snapshot, company_type_override)
        row = build_row(report, snapshot.metrics)
        if not final_company_type:
            final_company_type = report.company_type
        rows.append(row)

    rows = sort_rows(rows)
    return CompareResult(
        symbols=symbols,
        company_type=final_company_type or "未知",
        ranking_summary=build_summary(rows),
        rows=[asdict(r) for r in rows],
    )


def render_text(result: CompareResult) -> str:
    lines = [
        "## 对比结论",
        f"- 公司类型：{result.company_type}",
        *[f"- {line}" for line in result.ranking_summary],
        "",
        "## 对比明细",
    ]
    for row in result.rows:
        lines.extend(
            [
                f"- {row['symbol']} {row['company_name'] or ''}".rstrip(),
                f"  结论={row['conclusion']} | 置信度={row['confidence']} | PE={row['pe']} | PB={row['pb']} | PS={row['ps']} | PEG={row['peg']} | 增速={row['earnings_growth_pct']}% | 分位代理={row['percentile_proxy']} | 操作={row['action']}",
            ]
        )
    return "\n".join(lines)


def render_markdown(result: CompareResult) -> str:
    lines = [
        "## 对比结论",
        f"- 公司类型：{result.company_type}",
        *[f"- {line}" for line in result.ranking_summary],
        "",
        "## 对比明细",
        "",
        "| 代码 | 名称 | 结论 | 置信度 | PE | PB | PS | PEG | 增速% | 分位代理 | 操作 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in result.rows:
        lines.append(
            f"| {row['symbol']} | {row['company_name'] or ''} | {row['conclusion']} | {row['confidence']} | "
            f"{'' if row['pe'] is None else row['pe']} | {'' if row['pb'] is None else row['pb']} | "
            f"{'' if row['ps'] is None else row['ps']} | {'' if row['peg'] is None else row['peg']} | "
            f"{'' if row['earnings_growth_pct'] is None else row['earnings_growth_pct']} | "
            f"{'' if row['percentile_proxy'] is None else row['percentile_proxy']} | {row['action']} |"
        )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    result = generate_compare(args.symbols, args.company_type)
    if args.output == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    elif args.output == "markdown":
        print(render_markdown(result))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
