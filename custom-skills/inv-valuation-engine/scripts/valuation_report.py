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
基于估值快照生成五档价值投资估值报告。

示例:
  python3 valuation_report.py 600660 --proxy http://127.0.0.1:7890
  python3 valuation_report.py AAPL --output json --proxy http://127.0.0.1:7890
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from typing import Any

from valuation_snapshot import Snapshot, build_snapshot

from scoring_rules import EARNINGS_GROWTH_HIGH, EARNINGS_GROWTH_LOW


RATINGS = ["低估", "合理偏低", "合理", "合理偏高", "高估"]
RATING_SCORE = {name: idx for idx, name in enumerate(RATINGS)}


@dataclass
class MetricView:
    name: str
    value: float | None
    rating: str | None
    comment: str
    role: str = "diagnostic"


@dataclass
class ValuationReport:
    symbol: str
    company_name: str | None
    company_type: str
    valuation_status: str
    upstream_status: str
    conclusion: str | None
    confidence: str
    data_time: str | None
    data_sources: list[dict[str, Any]]
    data_gaps: list[dict[str, Any]]
    key_reasons: list[str]
    framework_views: dict[str, str]
    metrics_used: list[dict[str, Any]]
    core_assumptions: list[str]
    risks: list[str]
    action_reference: str | None
    notes: list[str]
    primary_valuation: dict[str, Any] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成五档价值投资估值报告")
    parser.add_argument("symbol", help="股票代码，如 600660 / AAPL / 0700.HK")
    parser.add_argument(
        "--company-type",
        default="auto",
        choices=["auto", "consumer", "internet", "tech", "cyclical", "financial"],
        help="可选公司类型覆盖",
    )
    parser.add_argument("--output", default="text", choices=["text", "json", "markdown"], help="输出格式")
    parser.add_argument("--snapshot-input", help="离线 Snapshot JSON，保留上游状态")
    parser.add_argument("--primary-input", help="核验的一主一辅与三情景 JSON")
    return parser.parse_args()


def infer_company_type(metrics: dict[str, Any], override: str) -> str:
    if override != "auto":
        mapping = {
            "consumer": "消费/医疗",
            "internet": "互联网/软件",
            "tech": "半导体/科技制造",
            "cyclical": "周期行业",
            "financial": "金融/地产",
        }
        return mapping[override]
    # auto 模式：由 LLM 根据 sector/industry 判断
    return "待确认"


def build_metric_views(metrics: dict[str, Any], company_type: str) -> tuple[list[MetricView], list[str]]:
    """Raw metrics are diagnostics, not independent valuation ballots."""
    fields = [("PE锚", "trailing_pe"), ("Forward PE", "forward_pe"), ("PB", "pb"),
              ("PS(TTM)", "ps_ttm"), ("历史分位代理", "price_percentile_5y_proxy"),
              ("目标价上行空间", "analyst_upside_pct"), ("股息率", "dividend_yield_pct"),
              ("自由现金流质量", "free_cash_flow"), ("盈利收益率", "earnings_yield_pct")]
    views = [MetricView(name, metrics[key], None, "仅 diagnostic / 背景；不参与整体估值或交易映射。")
             for name, key in fields if metrics.get(key) is not None]
    growth, pe = metrics.get("earnings_growth_pct"), metrics.get("trailing_pe")
    if growth and growth > 0 and pe:
        views.append(MetricView("PEG", round(pe / growth, 2), None, "仅历史背景，不能决定安全边际。"))
    return views, []


def first_non_null(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def confidence_level(snapshot_gaps: list[dict[str, Any]], views: list[MetricView]) -> str:
    usable = [v for v in views if v.rating]
    critical_fields = {
        "metrics.trailing_pe", "metrics.forward_pe", "metrics.pb",
        "metrics.revenue_growth_pct", "metrics.earnings_growth_pct",
        "metrics.price_percentile_5y_proxy", "window",
    }
    missing_count = len([gap for gap in snapshot_gaps if gap.get("field") in critical_fields])
    if len(usable) >= 3 and missing_count == 0:
        return "高"
    if len(usable) >= 2 and missing_count <= 2:
        return "中"
    return "低"


def determine_readiness(snapshot: Snapshot, views: list[MetricView]) -> tuple[str, list[dict[str, Any]]]:
    """Return valuation readiness independently from upstream data status."""
    gaps = [dict(item) for item in snapshot.data_gaps]
    if snapshot.upstream_status == "failed":
        gaps.append({
            "code": "valuation_upstream_failed",
            "field": "snapshot",
            "reason": "数据层核心快照失败",
            "retryable": True,
        })
        return "upstream_failed", gaps

    gaps.append({
        "code": "valuation_missing_verified_primary", "field": "valuation.primary",
        "reason": "缺少核验主估值与保守/基准/乐观情景；指标仅 diagnostic", "retryable": False,
    })
    return "insufficient_for_valuation", gaps


def framework_views(metrics: dict[str, Any], company_type: str, conclusion: str | None) -> dict[str, str]:
    peg = None
    if metrics.get("trailing_pe") and metrics.get("earnings_growth_pct"):
        growth = metrics["earnings_growth_pct"]
        if growth:
            peg = round(metrics["trailing_pe"] / growth, 2)

    views = {
        "公司经济类型": company_type,
        "质量与现金流": "ROE与现金流用于校验溢价或折价；当前定量结论为 `{}`。".format(conclusion),
    }
    if company_type == "周期行业":
        views["适用估值口径"] = "先核验周期位置与正常化盈利，不以单一年份利润或 PEG 为核心依据。"
    elif company_type == "金融/地产":
        views["适用估值口径"] = "优先核验 PB-ROE、股息率、NAV 与资产负债质量。"
    else:
        views["适用估值口径"] = "按现金流稳定性选择 DCF、PE、股息率或适用的成长指标。"
        views["增长辅助锚"] = "PEG={0}，仅在盈利稳定、增速可估时作辅助参考。".format(peg) if peg is not None else "增长数据不足或不适用，不能强行使用 PEG。"
    return views


def build_key_reasons(metrics: dict[str, Any], conclusion: str | None, views: list[MetricView]) -> list[str]:
    reasons: list[str] = []
    top = [v for v in views if v.rating][:3]
    for item in top:
        reasons.append(f"{item.name}={item.value}，落在“{item.rating}”区间。")

    if metrics.get("free_cash_flow") is not None and metrics["free_cash_flow"] < 0:
        reasons.append("自由现金流为负，说明估值不能只看利润口径。")
    if not reasons:
        reasons.append("当前数据不足，无法形成可靠估值结论。" if conclusion is None else f"当前数据有限，结论暂偏向“{conclusion}”。")
    return reasons[:3]


def build_assumptions(metrics: dict[str, Any]) -> list[str]:
    assumptions = []
    earnings_growth = metrics.get("earnings_growth_pct")
    if earnings_growth is not None:
        # 合理性校验：Yahoo earningsGrowth 对互联网/平台公司常严重失真
        # 若增速 >40% 或 < -30%，大概率是 GAAP 单季度扭曲，标记警告而非直接采信
        if earnings_growth > EARNINGS_GROWTH_HIGH:
            assumptions.append(
                f"⚠ 数据源利润增速 {earnings_growth}% 异常偏高（疑似GAAP单季度扭曲），"
                "请用 Normalized/Non-GAAP 净利润手动重算增速，勿直接采信此值。"
            )
        elif earnings_growth < EARNINGS_GROWTH_LOW:
            assumptions.append(
                f"⚠ 数据源利润增速 {earnings_growth}% 异常偏低（疑似一次性项目拖累），"
                "请确认是否为 Non-GAAP 口径，勿直接采信此值。"
            )
        else:
            assumptions.append(f"观测利润增速为 {earnings_growth}%；仅历史背景，不作为未来假设。")
    if metrics.get("gross_margin_pct") is not None:
        assumptions.append("毛利率与净利率不发生结构性恶化。")
    if metrics.get("next_earnings_date") is not None:
        assumptions.append(f"下一次财报日 {metrics['next_earnings_date']} 前后不出现显著负面预期差。")
    assumptions.append("估值口径与市场风险偏好不出现剧烈切换。")
    assumptions.append("当前公开数据不存在重大失真或一次性项目大幅扰动。")
    return assumptions[:4]


def build_risks(metrics: dict[str, Any]) -> list[str]:
    risks = []
    if metrics.get("price_percentile_5y_proxy") is not None and metrics["price_percentile_5y_proxy"] >= 85:
        risks.append("历史位置已偏高，若业绩不及预期，估值回撤压力会放大。")
    if metrics.get("free_cash_flow") is not None and metrics["free_cash_flow"] < 0:
        risks.append("自由现金流为负，若持续时间拉长，估值中枢可能下移。")
    if metrics.get("debt_to_equity") is not None and metrics["debt_to_equity"] >= 1:
        risks.append("杠杆不低，若景气走弱或利率环境变化，会压制估值。")
    # event_bias removed — LLM interprets raw announcements
    risks.append("当前历史分位仍是价格代理值，不是严格 PE/PB 分位，需降低确定性表达。")
    return risks[:4]


def evaluate_primary(snapshot: Snapshot, primary: dict[str, Any] | None) -> dict[str, Any] | None:
    """Read explicit, reviewed assumptions; never select a method or fit returns."""
    if not primary:
        return None
    price = snapshot.metrics.get("current_price")
    if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or price <= 0:
        return None
    if primary.get("verified") is not True:
        return None
    if any(not isinstance(primary.get(key), str) or not primary[key].strip()
           for key in ("method", "source", "as_of", "rationale", "currency")):
        return None
    if primary["method"].lower() in {"peg", "historical percentile", "analyst target price", "历史分位", "卖方目标价"}:
        return None
    if primary["currency"] != snapshot.currency:
        return None
    auxiliary = primary.get("auxiliary", {})
    if not isinstance(auxiliary, dict) or auxiliary.get("verified") is not True:
        return None
    if any(not isinstance(auxiliary.get(key), str) or not auxiliary[key].strip()
           for key in ("method", "source", "rationale", "assessment")):
        return None
    if auxiliary["assessment"] != "consistent" or auxiliary["method"] == primary["method"]:
        return None
    if auxiliary["method"].lower() in {"peg", "historical percentile", "analyst target price"}:
        return None
    years = primary.get("years")
    if not isinstance(years, (int, float)) or isinstance(years, bool) or not math.isfinite(years) or years <= 0:
        return None
    if primary.get("conclusion") not in RATINGS:
        return None
    scenarios = primary.get("scenarios", {})
    if not isinstance(scenarios, dict):
        return None
    output = {}
    for name in ("conservative", "base", "optimistic"):
        item = scenarios.get(name, {})
        if not isinstance(item, dict) or not isinstance(item.get("assumptions"), str) or not item["assumptions"].strip():
            return None
        value, cash = item.get("value_per_share"), item.get("cash_distributions")
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in (value, cash)) or value <= 0:
            return None
        output[name] = dict(item, total_return_pct=((value + cash) / price - 1) * 100,
                            annualized_return_pct=(((value + cash) / price) ** (1 / years) - 1) * 100,
                            margin_of_safety_pct=(1 - price / value) * 100)
    if not output["conservative"]["value_per_share"] <= output["base"]["value_per_share"] <= output["optimistic"]["value_per_share"]:
        return None
    return dict(primary, scenarios=output)


def generate_report_from_snapshot(snapshot: Snapshot, company_type_override: str,
                                  primary: dict[str, Any] | None = None) -> ValuationReport:
    company_type = infer_company_type(snapshot.metrics, company_type_override)
    views, report_notes = build_metric_views(snapshot.metrics, company_type)
    valuation_status, data_gaps = determine_readiness(snapshot, views)
    reviewed = evaluate_primary(snapshot, primary) if valuation_status != "upstream_failed" else None
    if reviewed:
        data_gaps = [gap for gap in data_gaps if gap["code"] != "valuation_missing_verified_primary"]
        valuation_status = "partial" if snapshot.upstream_status != "ok" or snapshot.used_fallback or snapshot.data_gaps else "ok"
    conclusion = reviewed["conclusion"] if reviewed else None
    action = None  # Capital allocation is separate; no valuation-to-trade mapping.
    confidence = confidence_level(data_gaps, views)

    return ValuationReport(
        symbol=snapshot.symbol,
        company_name=snapshot.company_name,
        company_type=company_type,
        valuation_status=valuation_status,
        upstream_status=snapshot.upstream_status,
        conclusion=conclusion,
        confidence=confidence,
        data_time=snapshot.data_time,
        data_sources=snapshot.data_sources,
        data_gaps=data_gaps,
        key_reasons=build_key_reasons(snapshot.metrics, conclusion, views),
        framework_views=framework_views(snapshot.metrics, company_type, conclusion),
        metrics_used=[asdict(v) for v in views],
        core_assumptions=build_assumptions(snapshot.metrics),
        risks=build_risks(snapshot.metrics),
        action_reference=action,
        notes=snapshot.notes + report_notes,
        primary_valuation=reviewed,
    )


def generate_report(symbol: str, company_type_override: str) -> ValuationReport:
    snapshot = build_snapshot(symbol)
    return generate_report_from_snapshot(snapshot, company_type_override)


def _source_labels(sources: list[dict[str, Any]]) -> str:
    labels = []
    for source in sources:
        suffix = "(fallback)" if source.get("fallback") else ""
        labels.append(f"{source.get('name')}:{source.get('status')}{suffix}")
    return ", ".join(labels) or "none"


def _gap_lines(gaps: list[dict[str, Any]]) -> list[str]:
    return [f"- {gap.get('field')}：{gap.get('reason')}（{gap.get('code')}）" for gap in gaps]


def render_primary(report: ValuationReport) -> list[str]:
    primary = report.primary_valuation
    if not primary:
        return ["## 主估值与情景", "- 未提供可核验的一主一辅及三情景；指标仅 diagnostic。"]
    lines = ["## 主估值与情景", f"- 主方法：{primary['method']}；辅助：{primary['auxiliary']['method']}",
             f"- 来源/时点：{primary['source']} / {primary['as_of']}",
             f"- 依据：{primary['rationale']}；期限：{primary['years']} 年；币种：{primary['currency']}"]
    for key, label in (("conservative", "保守"), ("base", "基准"), ("optimistic", "乐观")):
        item = primary["scenarios"][key]
        lines.append(f"- {label}：每股终值={item['value_per_share']}；累计现金分配={item['cash_distributions']}；"
                     f"总回报={item['total_return_pct']:.2f}%；年化={item['annualized_return_pct']:.2f}%；"
                     f"终值折让={item['margin_of_safety_pct']:.2f}%；假设={item['assumptions']}")
    lines.append("- 终值折让不是折现内在价值安全边际；须结合期限、下行情景与假设脆弱性人工判断。")
    return lines


def render_text(report: ValuationReport) -> str:
    metric_lines = [f"- {item['name']}: {item['value']} -> {item['rating']}（{item['comment']}）" for item in report.metrics_used]
    conclusion = report.conclusion or "数据不足，无法评级"
    action = report.action_reference or "无（估值闸门未通过）"
    return "\n".join(
        [
            "## 核心结论",
            f"- 估值状态：{report.valuation_status}",
            f"- 上游状态：{report.upstream_status}",
            f"- 估值结论：{conclusion}",
            f"- 结论置信度：{report.confidence}",
            f"- 公司类型：{report.company_type}",
            "",
            "## 关键依据",
            *[f"- {x}" for x in report.key_reasons],
            "",
            "## 定量指标验证",
            f"- 数据时点：{report.data_time or '未知'}",
            f"- 数据源：{_source_labels(report.data_sources)}",
            *metric_lines,
            "",
            "## 数据缺口",
            *_gap_lines(report.data_gaps),
            "",
            "## 核心假设",
            *[f"- {x}" for x in report.core_assumptions],
            "",
            "## 风险与失效条件",
            *[f"- {x}" for x in report.risks],
            "",
            *render_primary(report),
            "## 操作参考",
            f"- {action}",
        ]
    )


def render_markdown(report: ValuationReport) -> str:
    lines = [
        "## 核心结论",
        f"- 估值状态：{report.valuation_status}",
        f"- 上游状态：{report.upstream_status}",
        f"- 估值结论：{report.conclusion or '数据不足，无法评级'}",
        f"- 结论置信度：{report.confidence}",
        f"- 公司类型：{report.company_type}",
        "",
        "## 关键依据",
        *[f"- {x}" for x in report.key_reasons],
        "",
        "## 定量指标验证",
        f"- 数据时点：{report.data_time or '未知'}",
        f"- 数据源：{_source_labels(report.data_sources)}",
        "",
        "| 指标 | 数值 | 档位 | 说明 |",
        "|---|---:|---|---|",
    ]
    for item in report.metrics_used:
        value = "" if item["value"] is None else item["value"]
        rating = "" if item["rating"] is None else item["rating"]
        lines.append(f"| {item['name']} | {value} | {rating} | {item['comment']} |")

    lines.extend(
        [
            "",
            "## 数据缺口",
            *_gap_lines(report.data_gaps),
            "",
            "## 核心假设",
            *[f"- {x}" for x in report.core_assumptions],
            "",
            "## 风险与失效条件",
            *[f"- {x}" for x in report.risks],
            "",
            *render_primary(report),
            "## 操作参考",
            f"- {report.action_reference or '无（估值闸门未通过）'}",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    try:
        if args.snapshot_input:
            with open(args.snapshot_input, encoding="utf-8") as stream:
                snapshot = Snapshot(**json.load(stream))
            if snapshot.symbol != args.symbol:
                raise ValueError("snapshot symbol does not match requested symbol")
        else:
            snapshot = build_snapshot(args.symbol)
        primary = None
        if args.primary_input:
            with open(args.primary_input, encoding="utf-8") as stream:
                primary = json.load(stream)
    except (OSError, ValueError, TypeError) as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2
    report = generate_report_from_snapshot(snapshot, args.company_type, primary)
    if args.output == "json":
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    elif args.output == "markdown":
        print(render_markdown(report))
    else:
        print(render_text(report))
    return 1 if report.valuation_status == "upstream_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
