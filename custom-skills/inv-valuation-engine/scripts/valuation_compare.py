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
  uv run valuation_compare.py 002475 601138 002241 --company-type tech
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from valuation_report import generate_report_from_snapshot
from valuation_snapshot import Snapshot, build_snapshot


@dataclass
class CompareRow:
    symbol: str
    company_name: str | None
    valuation_status: str
    conclusion: str | None
    confidence: str
    pe: float | None
    pb: float | None
    ps: float | None
    peg: float | None
    earnings_growth_pct: float | None
    percentile_proxy: float | None
    action: str | None
    primary_valuation: dict[str, Any] | None = None


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
        choices=["auto", "consumer", "internet", "tech", "cyclical", "financial"],
        help="可选公司类型覆盖",
    )
    parser.add_argument("--output", default="text", choices=["text", "json", "markdown"], help="输出格式")
    parser.add_argument("--input", help="JSON对象：snapshots及primary_inputs均以原始股票代码为键")
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
        valuation_status=report.valuation_status,
        conclusion=report.conclusion,
        confidence=report.confidence,
        pe=_get_metric(report, "PE锚"),
        pb=snapshot_metrics.get("pb"),
        ps=_get_metric(report, "PS(TTM)"),
        peg=_get_metric(report, "PEG"),
        earnings_growth_pct=snapshot_metrics.get("earnings_growth_pct"),
        percentile_proxy=_get_metric(report, "历史分位代理"),
        action=report.action_reference,
        primary_valuation=report.primary_valuation,
    )


def sort_rows(rows: list[CompareRow]) -> list[CompareRow]:
    return list(rows)  # Labels and diagnostic multiples are not comparable rankings.


def build_summary(rows: list[CompareRow]) -> list[str]:
    if not rows:
        return ["无可比数据。"]

    reviewed = [row for row in rows if row.primary_valuation]
    if reviewed:
        return ["按输入顺序比较核验主估值的三情景回报；方法、币种、期限和风险须人工对齐，不自动排序。"]
    rateable = [row for row in rows if row.valuation_status in {"ok", "partial"} and row.conclusion]
    if not rateable:
        return ["没有可评级标的，无法生成相对便宜/昂贵排序。"]
    summary = ["按输入顺序展示；五档标签和诊断倍数不用于便宜/昂贵排序。"]

    pe_rows = [r for r in rows if r.pe is not None]
    if pe_rows:
        best_pe = min(pe_rows, key=lambda x: x.pe or 9999)
        summary.append(f"PE 锚最低的是 {best_pe.symbol}，PE={best_pe.pe}。")

    return summary[:4]


def generate_compare(symbols: list[str], company_type_override: str, *, snapshots=None, primary_inputs=None) -> CompareResult:
    rows: list[CompareRow] = []
    final_company_type = ""
    for symbol in symbols:
        snapshot = snapshots[symbol] if snapshots is not None else build_snapshot(symbol)
        report = generate_report_from_snapshot(snapshot, company_type_override, (primary_inputs or {}).get(symbol))
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
                f"  状态={row['valuation_status']} | 结论={row['conclusion'] or ('已核验（无标签）' if row.get('primary_valuation') else '不可评级')} | 置信度={row['confidence']} | PE={row['pe']} | PB={row['pb']} | PS={row['ps']} | PEG={row['peg']} | 增速={row['earnings_growth_pct']}% | 分位代理={row['percentile_proxy']} | 操作={row['action'] or '无'}",
            ]
        )
    for row in result.rows:
        primary = row.get("primary_valuation")
        if primary:
            lines.append(f"### {row['symbol']} 主估值：{primary['method']}；来源={primary['source']}；时点={primary['as_of']}；币种={primary['currency']}；期限={primary['years']}年")
            for name, label in (("conservative", "保守"), ("base", "基准"), ("optimistic", "乐观")):
                item = primary['scenarios'][name]
                lines.append(f"- {label}：终值={item['value_per_share']}；现金分配={item['cash_distributions']}；总回报={item['total_return_pct']:.2f}%；年化={item['annualized_return_pct']:.2f}%；假设={item['assumptions']}")
    return "\n".join(lines)


def render_markdown(result: CompareResult) -> str:
    lines = [
        "## 对比结论",
        f"- 公司类型：{result.company_type}",
        *[f"- {line}" for line in result.ranking_summary],
        "",
        "## 对比明细",
        "",
        "| 代码 | 名称 | 状态 | 结论 | 置信度 | PE | PB | PS | PEG | 增速% | 分位代理 | 操作 |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in result.rows:
        lines.append(
            f"| {row['symbol']} | {row['company_name'] or ''} | {row['valuation_status']} | {row['conclusion'] or ('已核验（无标签）' if row.get('primary_valuation') else '不可评级')} | {row['confidence']} | "
            f"{'' if row['pe'] is None else row['pe']} | {'' if row['pb'] is None else row['pb']} | "
            f"{'' if row['ps'] is None else row['ps']} | {'' if row['peg'] is None else row['peg']} | "
            f"{'' if row['earnings_growth_pct'] is None else row['earnings_growth_pct']} | "
            f"{'' if row['percentile_proxy'] is None else row['percentile_proxy']} | {row['action'] or '无'} |"
        )
    for row in result.rows:
        primary = row.get("primary_valuation")
        if primary:
            lines.append(f"### {row['symbol']} 主估值：{primary['method']}；来源={primary['source']}；时点={primary['as_of']}；币种={primary['currency']}；期限={primary['years']}年")
            for name, label in (("conservative", "保守"), ("base", "基准"), ("optimistic", "乐观")):
                item = primary['scenarios'][name]
                lines.append(f"- {label}：终值={item['value_per_share']}；现金分配={item['cash_distributions']}；总回报={item['total_return_pct']:.2f}%；年化={item['annualized_return_pct']:.2f}%；假设={item['assumptions']}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    try:
        bundle = {}
        if args.input:
            with open(args.input, encoding="utf-8") as stream:
                bundle = json.load(stream)
        snapshots = {key: Snapshot(**value) for key, value in bundle["snapshots"].items()} if "snapshots" in bundle else None
        if snapshots is not None and any(snapshots[symbol].symbol != symbol for symbol in args.symbols):
            raise ValueError("snapshot symbol does not match requested symbol")
        result = generate_compare(args.symbols, args.company_type, snapshots=snapshots, primary_inputs=bundle.get("primary_inputs"))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2
    if args.output == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    elif args.output == "markdown":
        print(render_markdown(result))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
