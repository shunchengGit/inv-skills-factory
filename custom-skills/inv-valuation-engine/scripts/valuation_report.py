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
import os
import statistics
from dataclasses import asdict, dataclass
from typing import Any

from valuation_snapshot import Snapshot, build_snapshot


RATINGS = ["低估", "合理偏低", "合理", "合理偏高", "高估"]
RATING_SCORE = {name: idx for idx, name in enumerate(RATINGS)}


@dataclass
class MetricView:
    name: str
    value: float | None
    rating: str | None
    comment: str


@dataclass
class ValuationReport:
    symbol: str
    company_name: str | None
    company_type: str
    conclusion: str
    confidence: str
    data_time: str
    data_sources: list[str]
    key_reasons: list[str]
    framework_views: dict[str, str]
    metrics_used: list[dict[str, Any]]
    core_assumptions: list[str]
    risks: list[str]
    action_reference: str
    notes: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成五档价值投资估值报告")
    parser.add_argument("symbol", help="股票代码，如 600660 / AAPL / 0700.HK")
    parser.add_argument(
        "--company-type",
        default="auto",
        choices=["auto", "consumer", "internet", "tech", "cyclical", "financial", "distressed"],
        help="可选公司类型覆盖",
    )
    parser.add_argument("--output", default="text", choices=["text", "json", "markdown"], help="输出格式")
    return parser.parse_args()


def score_to_rating(score: float) -> str:
    if score < 0.5:
        return "低估"
    if score < 1.5:
        return "合理偏低"
    if score < 2.5:
        return "合理"
    if score < 3.5:
        return "合理偏高"
    return "高估"


def metric_rating_by_ranges(value: float | None, ranges: list[tuple[float | None, float | None, str]]) -> str | None:
    if value is None:
        return None
    for lower, upper, rating in ranges:
        lower_ok = lower is None or value >= lower
        upper_ok = upper is None or value < upper
        if lower_ok and upper_ok:
            return rating
    return None


def infer_company_type(metrics: dict[str, Any], override: str) -> str:
    if override != "auto":
        mapping = {
            "consumer": "消费/医疗",
            "internet": "互联网/软件",
            "tech": "半导体/科技制造",
            "cyclical": "周期行业",
            "financial": "金融/地产",
            "distressed": "困境反转",
        }
        return mapping[override]
    # auto 模式：由 LLM 根据 sector/industry 判断
    return "待确认"


def build_metric_views(metrics: dict[str, Any], company_type: str) -> tuple[list[MetricView], list[str]]:
    views: list[MetricView] = []
    notes_for_report: list[str] = []

    trailing_pe = metrics.get("trailing_pe")
    forward_pe = metrics.get("forward_pe")
    pb = metrics.get("pb")
    ps_ttm = metrics.get("ps_ttm")
    percentile = metrics.get("price_percentile_5y_proxy")
    earnings_growth = metrics.get("earnings_growth_pct")
    dividend_yield = metrics.get("dividend_yield_pct")
    roe = metrics.get("roe_pct")
    fcf = metrics.get("free_cash_flow")
    analyst_upside = metrics.get("analyst_upside_pct")
    earnings_yield = metrics.get("earnings_yield_pct")
    event_score = None  # removed: LLM interprets raw announcements

    peg = None
    if trailing_pe and earnings_growth and earnings_growth > 0:
        peg = round(trailing_pe / earnings_growth, 2)
        views.append(
            MetricView(
                name="PEG",
                value=peg,
                rating=metric_rating_by_ranges(
                    peg,
                    [
                        (None, 0.6, "低估"),
                        (0.6, 0.8, "合理偏低"),
                        (0.8, 1.2, "合理"),
                        (1.2, 1.5, "合理偏高"),
                        (1.5, None, "高估"),
                    ],
                ),
                comment="来自 `PE / 利润增速`，适合成长型公司。",
            )
        )

    if percentile is not None:
        views.append(
            MetricView(
                name="历史分位代理",
                value=percentile,
                rating=metric_rating_by_ranges(
                    percentile,
                    [
                        (None, 20, "低估"),
                        (20, 30, "合理偏低"),
                        (30, 70, "合理"),
                        (70, 90, "合理偏高"),
                        (90, None, "高估"),
                    ],
                ),
                comment="当前仅为价格分位代理，保守使用。",
            )
        )

    if analyst_upside is not None:
        analyst_rating = metric_rating_by_ranges(
            analyst_upside,
            [
                (20, None, "低估"),
                (10, 20, "合理偏低"),
                (0, 10, "合理"),
                (-10, 0, "合理偏高"),
                (None, -10, "高估"),
            ],
        )
        views.append(
            MetricView(
                name="目标价上行空间",
                value=analyst_upside,
                rating=analyst_rating,
                comment="基于分析师目标价的辅助判断。",
            )
        )

    if company_type in {"半导体/科技制造", "互联网/软件"} and ps_ttm is not None:
        views.append(
            MetricView(
                name="PS(TTM)",
                value=ps_ttm,
                rating=metric_rating_by_ranges(
                    ps_ttm,
                    [
                        (None, 2, "低估"),
                        (2, 4, "合理偏低"),
                        (4, 8, "合理"),
                        (8, 15, "合理偏高"),
                        (15, None, "高估"),
                    ],
                ),
                comment="成长股辅助估值指标。",
            )
        )

    if company_type == "金融/地产" and pb is not None and roe is not None:
        pb_roe_ratio = round(pb / roe * 100, 2) if roe else None
        views.append(
            MetricView(
                name="PB-ROE代理",
                value=pb_roe_ratio,
                rating=score_to_rating(2.0 if pb_roe_ratio is not None and pb_roe_ratio < 15 else 3.0)
                if pb_roe_ratio is not None
                else None,
                comment="仅作 PB-ROE 代理，非严格行业比较。",
            )
        )

    if company_type in {"消费/医疗", "金融/地产"} and dividend_yield is not None:
        dividend_rating = "合理偏低" if dividend_yield >= 4 else "合理" if dividend_yield >= 2 else "合理偏高"
        views.append(
            MetricView(
                name="股息率",
                value=dividend_yield,
                rating=dividend_rating,
                comment="成熟型公司可用作估值补充。",
            )
        )

    pe_anchor = first_non_null(forward_pe, trailing_pe)
    # Forward PE 合理性校验：若 Forward PE 暗含的盈利增速与 trailing PE 差距过大（>30%），
    # 大概率是 Yahoo earningsGrowth 失真（常见于港股互联网/平台公司），降级使用 trailing_pe
    pe_anchor_source = "forward_pe" if forward_pe is not None else "trailing_pe"
    if forward_pe is not None and trailing_pe is not None and trailing_pe > 0:
        implied_growth = (trailing_pe / forward_pe - 1) * 100
        if implied_growth > 30:
            pe_anchor = trailing_pe
            pe_anchor_source = "trailing_pe(fwd_pe_implied_{:.0f}pct_growth_suspect)".format(implied_growth)
            notes_for_report.append(
                "Forward PE({:.2f})暗含{:.0f}%盈利增速，疑似Yahoo earningsGrowth失真，已降级使用trailing_pe({:.2f})".format(
                    forward_pe, implied_growth, trailing_pe
                )
            )
    if pe_anchor is not None:
        pe_comment = "行业 PE 参考锚（{}）。".format(pe_anchor_source)
        if company_type == "消费/医疗":
            pe_rating = metric_rating_by_ranges(
                pe_anchor,
                [(None, 16, "低估"), (16, 20, "合理偏低"), (20, 30, "合理"), (30, 35, "合理偏高"), (35, None, "高估")],
            )
        elif company_type == "互联网/软件":
            pe_rating = metric_rating_by_ranges(
                pe_anchor,
                [(None, 12, "低估"), (12, 15, "合理偏低"), (15, 40, "合理"), (40, 50, "合理偏高"), (50, None, "高估")],
            )
        elif company_type == "半导体/科技制造":
            pe_rating = metric_rating_by_ranges(
                pe_anchor,
                [(None, 10, "低估"), (10, 15, "合理偏低"), (15, 35, "合理"), (35, 45, "合理偏高"), (45, None, "高估")],
            )
        elif company_type == "周期行业":
            pe_rating = metric_rating_by_ranges(
                pe_anchor,
                [(None, 5, "低估"), (5, 8, "合理偏低"), (8, 15, "合理"), (15, 20, "合理偏高"), (20, None, "高估")],
            )
        else:
            pe_rating = metric_rating_by_ranges(
                pe_anchor,
                [(None, 8, "低估"), (8, 10, "合理偏低"), (10, 20, "合理"), (20, 30, "合理偏高"), (30, None, "高估")],
            )
        views.append(MetricView(name="PE锚", value=pe_anchor, rating=pe_rating, comment=pe_comment))

    if fcf is not None:
        views.append(
            MetricView(
                name="自由现金流质量",
                value=fcf,
                rating="合理" if fcf > 0 else "合理偏高",
                comment="FCF 为负时下调结论置信度。",
            )
        )

    if earnings_yield is not None:
        views.append(
            MetricView(
                name="盈利收益率",
                value=earnings_yield,
                rating=metric_rating_by_ranges(
                    earnings_yield,
                    [
                        (8, None, "低估"),
                        (6, 8, "合理偏低"),
                        (4, 6, "合理"),
                        (2.5, 4, "合理偏高"),
                        (None, 2.5, "高估"),
                    ],
                ),
                comment="PE 的倒数，便于和债券/股息收益率对照。",
            )
        )

    # event_score 已移除，LLM 根据原始公告/调研数据判断

    return views, notes_for_report


def first_non_null(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def choose_conclusion(views: list[MetricView]) -> str:
    usable = [v for v in views if v.rating]
    if not usable:
        return "合理"

    scores = sorted(RATING_SCORE[v.rating] for v in usable)
    average = sum(scores) / len(scores)
    median_score = statistics.median(scores)
    baseline = score_to_rating(median_score)

    # 仅当集中度很高且不存在明显冲突时，才直接采用重复档位
    for score in sorted(set(scores)):
        count = scores.count(score)
        if count >= 3 and max(scores) - min(scores) <= 1:
            return RATINGS[score]

    # 若存在低估与高估同时出现，优先回到中间并偏保守
    if max(scores) - min(scores) >= 3:
        return score_to_rating(min(4, average + 0.5))

    return baseline


def confidence_level(snapshot_gaps: list[str], views: list[MetricView]) -> str:
    usable = [v for v in views if v.rating]
    critical_missing = {"trailing_pe", "forward_pe", "pb", "revenue_growth_pct", "earnings_growth_pct", "price_percentile_5y_proxy"}
    missing_count = len([g for g in snapshot_gaps if g in critical_missing])
    if len(usable) >= 3 and missing_count == 0:
        return "高"
    if len(usable) >= 2 and missing_count <= 2:
        return "中"
    return "低"


def framework_views(metrics: dict[str, Any], company_type: str, conclusion: str) -> dict[str, str]:
    peg = None
    if metrics.get("trailing_pe") and metrics.get("earnings_growth_pct"):
        growth = metrics["earnings_growth_pct"]
        if growth:
            peg = round(metrics["trailing_pe"] / growth, 2)

    buffett = "默认主框架。ROE与现金流决定是否应享有溢价；当前结论为 `{}`。".format(conclusion)
    duan = "适用。若商业模式稳定且长期年化回报仍在 10% 左右，可支持至少“合理”。" if company_type in {"消费/医疗", "互联网/软件", "半导体/科技制造"} else "非优先框架。"
    lynch = "PEG={0}，适合作为成长股辅助锚。".format(peg) if peg is not None and company_type != "周期行业" else "暂不适用或参考价值有限。"
    templeton = "仅在周期底部或困境反转中启用；当前不作为主结论依据。"
    return {
        "巴菲特/芒格": buffett,
        "段永平": duan,
        "彼得·林奇": lynch,
        "邓普顿": templeton,
    }


def build_key_reasons(metrics: dict[str, Any], conclusion: str, views: list[MetricView]) -> list[str]:
    reasons: list[str] = []
    top = [v for v in views if v.rating][:3]
    for item in top:
        reasons.append(f"{item.name}={item.value}，落在“{item.rating}”区间。")

    if metrics.get("free_cash_flow") is not None and metrics["free_cash_flow"] < 0:
        reasons.append("自由现金流为负，说明估值不能只看利润口径。")
    if metrics.get("roe_pct") is not None and metrics["roe_pct"] >= 15:
        reasons.append("ROE 处于较好水平，对估值中枢有支撑。")
    if not reasons:
        reasons.append(f"当前数据有限，结论暂偏向“{conclusion}”。")
    return reasons[:3]


def build_assumptions(metrics: dict[str, Any]) -> list[str]:
    assumptions = []
    earnings_growth = metrics.get("earnings_growth_pct")
    if earnings_growth is not None:
        # 合理性校验：Yahoo earningsGrowth 对互联网/平台公司常严重失真
        # 若增速 >40% 或 < -30%，大概率是 GAAP 单季度扭曲，标记警告而非直接采信
        if earnings_growth > 40:
            assumptions.append(
                f"⚠ 数据源利润增速 {earnings_growth}% 异常偏高（疑似GAAP单季度扭曲），"
                "请用 Normalized/Non-GAAP 净利润手动重算增速，勿直接采信此值。"
            )
        elif earnings_growth < -30:
            assumptions.append(
                f"⚠ 数据源利润增速 {earnings_growth}% 异常偏低（疑似一次性项目拖累），"
                "请确认是否为 Non-GAAP 口径，勿直接采信此值。"
            )
        else:
            assumptions.append(f"未来 2-3 年利润增速大致维持在 {earnings_growth}% 附近，不明显下修。")
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


def action_reference(conclusion: str) -> str:
    mapping = {
        "低估": "逢低加仓",
        "合理偏低": "持有 / 逢低加仓",
        "合理": "持有 / 观望",
        "合理偏高": "观望 / 分批减仓",
        "高估": "回避 / 分批减仓",
    }
    return mapping[conclusion]


def generate_report_from_snapshot(snapshot: Snapshot, company_type_override: str) -> ValuationReport:
    company_type = infer_company_type(snapshot.metrics, company_type_override)
    views, report_notes = build_metric_views(snapshot.metrics, company_type)
    conclusion = choose_conclusion(views)
    confidence = confidence_level(snapshot.data_gaps, views)

    return ValuationReport(
        symbol=snapshot.symbol,
        company_name=snapshot.company_name,
        company_type=company_type,
        conclusion=conclusion,
        confidence=confidence,
        data_time=snapshot.data_time,
        data_sources=snapshot.data_sources,
        key_reasons=build_key_reasons(snapshot.metrics, conclusion, views),
        framework_views=framework_views(snapshot.metrics, company_type, conclusion),
        metrics_used=[asdict(v) for v in views],
        core_assumptions=build_assumptions(snapshot.metrics),
        risks=build_risks(snapshot.metrics),
        action_reference=action_reference(conclusion),
        notes=snapshot.notes + report_notes,
    )


def generate_report(symbol: str, company_type_override: str) -> ValuationReport:
    snapshot = build_snapshot(symbol)
    return generate_report_from_snapshot(snapshot, company_type_override)


def render_text(report: ValuationReport) -> str:
    metric_lines = []
    for item in report.metrics_used:
        metric_lines.append(f"- {item['name']}: {item['value']} -> {item['rating']}（{item['comment']}）")

    framework_lines = [
        f"- 巴菲特/芒格：{report.framework_views['巴菲特/芒格']}",
        f"- 段永平：{report.framework_views['段永平']}",
        f"- 彼得·林奇：{report.framework_views['彼得·林奇']}",
        f"- 邓普顿：{report.framework_views['邓普顿']}",
    ]

    return "\n".join(
        [
            "## 核心结论",
            f"- 估值结论：{report.conclusion}",
            f"- 结论置信度：{report.confidence}",
            f"- 公司类型：{report.company_type}",
            "",
            "## 关键依据",
            *[f"- {x}" for x in report.key_reasons],
            "",
            "## 分框架判断",
            *framework_lines,
            "",
            "## 定量指标验证",
            f"- 数据时点：{report.data_time}",
            f"- 数据源：{', '.join(report.data_sources)}",
            *metric_lines,
            "",
            "## 核心假设",
            *[f"- {x}" for x in report.core_assumptions],
            "",
            "## 风险与失效条件",
            *[f"- {x}" for x in report.risks],
            "",
            "## 操作参考",
            f"- {report.action_reference}",
        ]
    )


def render_markdown(report: ValuationReport) -> str:
    lines = [
        "## 核心结论",
        f"- 估值结论：{report.conclusion}",
        f"- 结论置信度：{report.confidence}",
        f"- 公司类型：{report.company_type}",
        "",
        "## 关键依据",
        *[f"- {x}" for x in report.key_reasons],
        "",
        "## 分框架判断",
        f"- 巴菲特/芒格：{report.framework_views['巴菲特/芒格']}",
        f"- 段永平：{report.framework_views['段永平']}",
        f"- 彼得·林奇：{report.framework_views['彼得·林奇']}",
        f"- 邓普顿：{report.framework_views['邓普顿']}",
        "",
        "## 定量指标验证",
        f"- 数据时点：{report.data_time}",
        f"- 数据源：{', '.join(report.data_sources)}",
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
            "## 核心假设",
            *[f"- {x}" for x in report.core_assumptions],
            "",
            "## 风险与失效条件",
            *[f"- {x}" for x in report.risks],
            "",
            "## 操作参考",
            f"- {report.action_reference}",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    report = generate_report(args.symbol, args.company_type)
    if args.output == "json":
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    elif args.output == "markdown":
        print(render_markdown(report))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
