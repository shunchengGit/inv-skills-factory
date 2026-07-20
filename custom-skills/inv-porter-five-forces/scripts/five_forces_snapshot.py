#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pandas>=2.0.0",
# ]
# ///
"""
为波特五力分析抓取跨市场事实底稿。
数据层统一通过 inv-stock-data CLI 获取。

支持:
- A股: 600519 / 000001 / 300750
- 港股: 0700.HK / 1810.HK
- 美股: AAPL / NVDA / MSFT
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd



SUPPLIER_HINTS = [
    "自研",
    "自产",
    "自制",
    "垂直整合",
    "供应链",
    "核心零部件",
    "self-developed",
    "in-house",
    "vertical",
    "manufacturing",
    "supply chain",
    "proprietary",
]

BUYER_HINTS = [
    "品牌",
    "渠道",
    "会员",
    "订阅",
    "平台",
    "生态",
    "网络效应",
    "brand",
    "channel",
    "subscription",
    "platform",
    "ecosystem",
    "network",
    "premium",
]

ENTRY_HINTS = [
    "专利",
    "认证",
    "牌照",
    "合规",
    "研发",
    "平台",
    "生态",
    "网络效应",
    "patent",
    "certification",
    "license",
    "regulatory",
    "compliance",
    "capital",
    "capacity",
]

SUBSTITUTE_HINTS = [
    "标准",
    "基础设施",
    "核心",
    "关键",
    "必需",
    "platform",
    "ecosystem",
    "standard",
    "infrastructure",
    "mission-critical",
    "essential",
]

RIVALRY_KEYWORDS = [
    "价格战",
    "降价",
    "竞争",
    "price cut",
    "competition",
    "competitive",
]

EVENT_FORCE_HINTS = [
    ("回购", "buyer_power", "最近公告出现回购，通常反映管理层对品牌力、盈利质量或股东回报有信心。"),
    ("增持", "buyer_power", "最近公告出现增持，通常说明管理层或重要股东对经营韧性更积极。"),
    ("提价", "buyer_power", "最近事件出现提价线索，可重点验证公司是否具备向下游传导成本的能力。"),
    ("中标", "entry_threat", "最近公告出现中标，通常说明客户认证、渠道或技术壁垒仍在发挥作用。"),
    ("订单", "entry_threat", "最近公告出现订单线索，可辅助判断客户黏性和进入壁垒是否有效。"),
    ("专利", "entry_threat", "最近事件出现专利线索，可辅助判断技术和进入壁垒。"),
    ("认证", "entry_threat", "最近事件出现认证线索，可辅助判断资质和准入门槛。"),
    ("降价", "rivalry", "最近事件出现降价线索，需重点检查行业是否进入价格竞争阶段。"),
    ("价格战", "rivalry", "最近事件出现价格战线索，说明同业竞争强度可能上升。"),
    ("扩产", "rivalry", "最近事件出现扩产线索，需关注供给增加是否会加剧竞争。"),
    ("替代", "substitute_threat", "最近事件出现替代线索，需重点检查新技术或新路线对需求的影响。"),
    ("AI", "substitute_threat", "最近事件出现 AI 相关线索，需判断其是护城河强化还是替代风险。"),
]

INDUSTRY_MATCH_RULES = [
    (["wineries", "distilleries", "baijiu"], "高端白酒"),
    (["酒", "饮料"], "高端白酒"),
    (["beer"], "啤酒"),
    (["consumer electronics"], "消费电子品牌"),
    (["electronic components", "semiconductor"], "半导体设计"),
    (["semiconductor equipment"], "半导体设备"),
    (["semiconductor materials"], "半导体材料"),
    (["internet content", "social"], "互联网社交"),
    (["internet content", "information"], "互联网社交"),
    (["social", "network"], "互联网社交"),
    (["internet retail", "e-commerce", "online retail"], "互联网电商"),
    (["software", "saas"], "软件 SaaS"),
    (["software", "industrial"], "工业软件"),
    (["cloud", "infrastructure"], "云计算基础设施"),
    (["auto manufacturers", "automobile manufacturers"], "新能源整车"),
    (["auto parts", "automobile parts"], "汽车零部件"),
    (["medical devices"], "医疗器械"),
    (["biotechnology"], "创新药"),
    (["drug manufacturers"], "仿制药"),
    (["insurance"], "保险"),
    (["banks"], "金融服务"),
    (["capital markets"], "券商"),
]


@dataclass
class NewsItem:
    title: str
    publisher: str | None
    published_at: str | None
    link: str | None


@dataclass
class Snapshot:
    symbol: str
    normalized_symbol: str
    company_name: str | None
    market: str
    currency: str | None
    data_time: str | None
    data_sources: list[dict[str, Any]]
    upstream: dict[str, Any]
    company_profile: dict[str, Any]
    financial_metrics: dict[str, Any]
    market_signals: dict[str, Any]
    peer_reference: dict[str, Any]
    industry_benchmark: dict[str, Any]
    recent_developments: dict[str, Any]
    five_forces_facts: dict[str, list[str]]
    pre_scoring: dict[str, Any]
    data_gaps: list[dict[str, Any]]
    notes: list[str]


def first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _parse_pct(val) -> float | None:
    """将百分比字符串或数值转为 float。'48.01%' → 48.01, 0.4801 → 48.01, None → None"""
    if val is None or val is False:
        return None
    if isinstance(val, (int, float)):
        v = float(val)
        return v if v > 1 else round(v * 100, 2)
    s = str(val).strip().rstrip("%").replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_num(val) -> float | None:
    """将数值字符串转为 float。None/False → None"""
    if val is None or val is False:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _pct_str(val) -> float | None:
    """将百分比字符串转为 float。'48.01%' → 48.01, '12.34' → 12.34, False → None"""
    if val is None or val is False:
        return None
    s = str(val).strip().rstrip("%").replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None
    message = str(exc).strip()
    if "None of [Index(" in message and "are in the [columns]" in message:
        return "上游接口字段变动"
    return message or exc.__class__.__name__


def clamp_score(value: float, low: int = 1, high: int = 20) -> int:
    return max(low, min(high, int(round(value))))


def score_band(score: int) -> str:
    if score >= 18:
        return "18-20"
    if score >= 14:
        return "14-17"
    if score >= 10:
        return "10-13"
    if score >= 6:
        return "6-9"
    return "1-5"


def confidence_label(evidence_count: int, missing_count: int) -> str:
    if evidence_count >= 3 and missing_count <= 1:
        return "高"
    if evidence_count >= 2 and missing_count <= 3:
        return "中"
    return "低"


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return "".join(str(value).strip().lower().split())


def parse_industry_benchmarks() -> list[dict[str, Any]]:
    from pathlib import Path

    benchmark_path = Path(__file__).resolve().parent.parent / "references" / "industry-benchmark.md"
    rows: list[dict[str, Any]] = []
    if not benchmark_path.exists():
        return rows

    for raw_line in benchmark_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "行业" in line or "---" in line:
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) != 7:
            continue
        industry = parts[0]
        try:
            rows.append(
                {
                    "industry": industry,
                    "supplier_power": int(parts[1]),
                    "buyer_power": int(parts[2]),
                    "entry_threat": int(parts[3]),
                    "substitute_threat": int(parts[4]),
                    "rivalry": int(parts[5]),
                    "total_score": int(parts[6]),
                }
            )
        except ValueError:
            continue
    return rows


def match_industry_benchmark(industry: str | None, sector: str | None, summary: str | None) -> dict[str, Any]:
    benchmarks = parse_industry_benchmarks()
    if not benchmarks:
        return {"matched": False, "reason": "未读取到行业基准表"}

    normalized_candidates = [normalize_text(industry), normalize_text(sector), normalize_text(summary)]

    # 正向匹配：benchmark key 是否出现在 candidate 中
    for row in benchmarks:
        key = normalize_text(row["industry"])
        if key and any(key in candidate for candidate in normalized_candidates if candidate):
            return {
                "matched": True,
                "match_type": "exact-ish",
                "matched_industry": row["industry"],
                "benchmark": row,
            }

    # 反向匹配：candidate 是否包含 benchmark key 的核心词
    for row in benchmarks:
        key = normalize_text(row["industry"])
        if not key:
            continue
        for candidate in normalized_candidates:
            if candidate and key in candidate:
                return {
                    "matched": True,
                    "match_type": "reverse",
                    "matched_industry": row["industry"],
                    "benchmark": row,
                }

    combined_text = " ".join(part for part in [industry, sector, summary] if part).lower()
    best_target = None
    best_score = 0.0
    for keywords, target in INDUSTRY_MATCH_RULES:
        matched = [keyword for keyword in keywords if keyword.lower() in combined_text]
        if not matched:
            continue
        score = len(matched) / len(keywords)
        if len(matched) > 1:
            score += 0.2
        if score > best_score:
            best_score = score
            best_target = target

    if best_target:
        for row in benchmarks:
            if row["industry"] == best_target:
                return {
                    "matched": True,
                    "match_type": "heuristic",
                    "matched_industry": row["industry"],
                    "benchmark": row,
                }

    return {
        "matched": False,
        "reason": "未找到可自动映射的细分行业基准",
    }


def safe_round(value: Any, ndigits: int = 2) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), ndigits)
    except Exception:
        return None


def pct(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value) * 100, 2)
    except Exception:
        return None


def normalize_symbol(symbol: str, market: str = "auto") -> str:
    s = symbol.strip().upper()
    if market == "hk" and not s.endswith(".HK") and s.isdigit():
        return f"{s}.HK"
    if market == "a":
        if "." in s:
            return s.replace(".SH", ".SS")
        if s.isdigit() and len(s) == 6:
            return f"{s}.SS" if s.startswith(("6", "9")) else f"{s}.SZ"
    if "." in s:
        return s.replace(".SH", ".SS")
    if s.isdigit() and len(s) == 6:
        return f"{s}.SS" if s.startswith(("6", "9")) else f"{s}.SZ"
    return s


def is_a_share(symbol: str) -> bool:
    s = symbol.strip().upper()
    if "." in s:
        base, suffix = s.split(".", 1)
        return base.isdigit() and len(base) == 6 and suffix in {"SS", "SZ", "SH"}
    return s.isdigit() and len(s) == 6


def to_a_share_code(symbol: str) -> str:
    s = symbol.strip().upper()
    return s.split(".", 1)[0] if "." in s else s


def detect_market(normalized_symbol: str, forced_market: str, info: dict[str, Any]) -> str:
    if forced_market == "a":
        return "A-share"
    if forced_market == "hk":
        return "HK"
    if forced_market == "us":
        return "US"
    if normalized_symbol.endswith((".SS", ".SZ", ".SH")):
        return "A-share"
    if normalized_symbol.endswith(".HK"):
        return "HK"
    exchange = str(first_not_none(info.get("exchange"), info.get("market"), "")).upper()
    if exchange in {"NMS", "NYQ", "NAS", "ASE", "PCX", "BTS", "OEM"}:
        return "US"
    if exchange in {"HKG"}:
        return "HK"
    return "US"


def normalize_dividend_yield(value: Any) -> float | None:
    try:
        if value is None:
            return None
        value = float(value)
        if 0 <= value <= 0.2:
            return round(value * 100, 2)
        return round(value, 2)
    except Exception:
        return None


# ── inv-stock-data CLI 调用 ────────────────────────────────────────────────


def _call_cs_stock(*args: str) -> dict:
    """调用数据层；非零退出时仍优先保留 stdout 中的合法 v1 failed envelope。"""
    from pathlib import Path

    cs_dir = Path(__file__).resolve().parent.parent.parent / "inv-stock-data"
    cmd = ["uv", "run", str(cs_dir / "scripts" / "cs_stock_info.py"), *args, "--output", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cs_dir, timeout=90)
        try:
            payload = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict) and payload.get("schema_version"):
            return payload
        message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        return {"error": message[:300]}
    except Exception as exc:
        return {"error": str(exc)[:200]}


def _dig(data: dict[str, Any], *keys: str) -> Any:
    """安全嵌套取值，类似 dict.get 但支持多层。"""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


# ── 分析逻辑 ──────────────────────────────────────────────────────────


def _event_time_decay(days: int) -> float:
    """公告事件时间衰减：7 天内 1.0，20 天内 0.8，45 天内 0.55，更早 0.35。"""
    if days <= 7:
        return 1.0
    if days <= 20:
        return 0.8
    if days <= 45:
        return 0.55
    return 0.35


def extract_event_force_hints(titles: list[str]) -> dict[str, list[str]]:
    result = {
        "supplier_power": [],
        "buyer_power": [],
        "entry_threat": [],
        "substitute_threat": [],
        "rivalry": [],
    }
    seen: set[tuple[str, str]] = set()
    for title in titles:
        lowered = title.lower()
        for keyword, dimension, message in EVENT_FORCE_HINTS:
            if keyword.lower() in lowered and (dimension, message) not in seen:
                result[dimension].append(f"{message} 相关标题：{title}")
                seen.add((dimension, message))
    return result


def build_pre_scoring(
    financial_metrics: dict[str, Any],
    industry_benchmark: dict[str, Any],
    five_forces_facts: dict[str, list[str]],
    event_titles: list[str],
    event_time_map: dict[str, str] | None,
    data_gaps: list[dict[str, Any]],
    upstream_status: str = "ok",
) -> dict[str, Any]:
    benchmark = industry_benchmark.get("benchmark") if industry_benchmark.get("matched") else None
    gross_margin = financial_metrics.get("gross_margin_pct")
    operating_margin = financial_metrics.get("operating_margin_pct")
    net_margin = financial_metrics.get("net_margin_pct")
    revenue_growth = financial_metrics.get("revenue_growth_pct")
    roe = financial_metrics.get("roe_pct")
    debt_to_equity = financial_metrics.get("debt_to_equity")

    lowered_titles = " | ".join(event_titles).lower()

    dimensions = {
        "supplier_power": {
            "label": "供应商议价能力",
            "base": benchmark["supplier_power"] if benchmark else 12,
            "reasons": [],
            "score": benchmark["supplier_power"] if benchmark else 12,
        },
        "buyer_power": {
            "label": "购买者议价能力",
            "base": benchmark["buyer_power"] if benchmark else 12,
            "reasons": [],
            "score": benchmark["buyer_power"] if benchmark else 12,
        },
        "entry_threat": {
            "label": "新进入者威胁",
            "base": benchmark["entry_threat"] if benchmark else 12,
            "reasons": [],
            "score": benchmark["entry_threat"] if benchmark else 12,
        },
        "substitute_threat": {
            "label": "替代品威胁",
            "base": benchmark["substitute_threat"] if benchmark else 12,
            "reasons": [],
            "score": benchmark["substitute_threat"] if benchmark else 12,
        },
        "rivalry": {
            "label": "同业竞争程度",
            "base": benchmark["rivalry"] if benchmark else 12,
            "reasons": [],
            "score": benchmark["rivalry"] if benchmark else 12,
        },
    }

    if gross_margin is not None:
        if gross_margin >= 60:
            dimensions["supplier_power"]["score"] += 2
            dimensions["buyer_power"]["score"] += 2
            dimensions["rivalry"]["score"] += 1
            dimensions["supplier_power"]["reasons"].append(f"毛利率 {gross_margin}% 很高，说明成本传导和议价能力较强。")
            dimensions["buyer_power"]["reasons"].append(f"毛利率 {gross_margin}% 很高，说明公司对客户压价有较强抵御能力。")
        elif gross_margin >= 35:
            dimensions["supplier_power"]["score"] += 1
            dimensions["buyer_power"]["score"] += 1
            dimensions["supplier_power"]["reasons"].append(f"毛利率 {gross_margin}% 处于较好水平，支持中高分判断。")
        elif gross_margin < 20:
            dimensions["supplier_power"]["score"] -= 2
            dimensions["buyer_power"]["score"] -= 2
            dimensions["rivalry"]["score"] -= 1
            dimensions["supplier_power"]["reasons"].append(f"毛利率 {gross_margin}% 偏低，说明上游或价格竞争压力较大。")

    if operating_margin is not None:
        if operating_margin >= 25:
            dimensions["rivalry"]["score"] += 1
            dimensions["rivalry"]["reasons"].append(f"营业利润率 {operating_margin}% 较高，说明行业竞争对利润侵蚀有限。")
        elif operating_margin < 8:
            dimensions["rivalry"]["score"] -= 1
            dimensions["rivalry"]["reasons"].append(f"营业利润率 {operating_margin}% 偏低，需警惕同业竞争或价格战。")

    if net_margin is not None:
        if net_margin >= 20:
            dimensions["buyer_power"]["score"] += 1
            dimensions["substitute_threat"]["score"] += 1
            dimensions["buyer_power"]["reasons"].append(f"净利率 {net_margin}% 较高，通常意味着产品差异化和客户黏性较好。")
        elif net_margin < 5:
            dimensions["buyer_power"]["score"] -= 1
            dimensions["substitute_threat"]["score"] -= 1
            dimensions["buyer_power"]["reasons"].append(f"净利率 {net_margin}% 偏低，客户议价空间和产品差异化可能不足。")
            dimensions["substitute_threat"]["reasons"].append(f"净利率 {net_margin}% 偏低，替代品吸引力可能相对上升。")

    if revenue_growth is not None:
        if revenue_growth >= 15:
            dimensions["buyer_power"]["score"] += 1
            dimensions["entry_threat"]["score"] += 1
            dimensions["buyer_power"]["reasons"].append(f"收入增速 {revenue_growth}% 较快，说明需求侧承接和产品竞争力较强。")
        elif revenue_growth <= 3:
            dimensions["rivalry"]["score"] -= 1
            dimensions["substitute_threat"]["score"] -= 1
            dimensions["rivalry"]["reasons"].append(f"收入增速 {revenue_growth}% 偏低，需警惕需求放缓或竞争加剧。")
            dimensions["substitute_threat"]["reasons"].append(f"收入增速 {revenue_growth}% 偏低，需求放缓可能使替代品更具吸引力。")

    if roe is not None:
        if roe >= 20:
            dimensions["entry_threat"]["score"] += 1
            dimensions["substitute_threat"]["score"] += 1
            dimensions["entry_threat"]["reasons"].append(f"ROE {roe}% 较高，说明公司在行业中可能具备较强壁垒或效率优势。")
        elif roe < 8:
            dimensions["entry_threat"]["score"] -= 1
            dimensions["entry_threat"]["reasons"].append(f"ROE {roe}% 偏低，说明行业壁垒或效率优势可能不足，新进入者威胁相对更大。")

    if debt_to_equity is not None:
        if debt_to_equity <= 0.5:
            dimensions["supplier_power"]["score"] += 1
            dimensions["supplier_power"]["reasons"].append(f"负债水平较稳健（D/E {debt_to_equity}），扩产和采购谈判空间更大。")
        elif debt_to_equity >= 2:
            dimensions["supplier_power"]["score"] -= 1
            dimensions["supplier_power"]["reasons"].append(f"负债水平偏高（D/E {debt_to_equity}），上游议价和资金灵活性可能受限。")

    # 事件关键词评分（带时间衰减）
    now = pd.Timestamp.now().normalize()
    event_keywords = [
        (["回购", "增持", "提价"], "buyer_power", 1, "近期公告含回购/增持/提价线索，支持品牌力或定价权判断。"),
        (["中标", "订单", "认证", "专利"], "entry_threat", 1, "近期事件含中标/订单/认证/专利线索，支持进入壁垒判断。"),
        (["替代", "ai", "新技术"], "substitute_threat", -1, "近期事件出现替代或新技术线索，替代风险需更谨慎。"),
        (["降价", "价格战", "扩产"], "rivalry", -2, "近期事件出现降价/价格战/扩产线索，竞争强度可能上升。"),
    ]
    for keywords, dimension, delta, reason in event_keywords:
        if not any(keyword in lowered_titles for keyword in keywords):
            continue
        # 找到最早匹配的标题，计算衰减
        best_decay = 0.35
        for title in event_titles:
            if any(keyword in title.lower() for keyword in keywords):
                time_str = (event_time_map or {}).get(title)
                if time_str:
                    try:
                        days = max(0, (now - pd.Timestamp(time_str).normalize()).days)
                        decay = _event_time_decay(days)
                        best_decay = max(best_decay, decay)
                    except Exception:
                        best_decay = 1.0
                else:
                    best_decay = 1.0
        adjusted_delta = round(delta * best_decay)
        if adjusted_delta != 0:
            dimensions[dimension]["score"] += adjusted_delta
            dimensions[dimension]["reasons"].append(reason)

    results: dict[str, Any] = {}
    missing_count = len(data_gaps)
    minimum_evidence = 6  # 3 个评分子维度 × 每维至少 2 条独立事实
    for key, payload in dimensions.items():
        evidence_count = len(five_forces_facts.get(key, []))
        ready = upstream_status != "failed" and evidence_count >= minimum_evidence
        suggested = clamp_score(payload["score"]) if ready else None
        force_gaps = []
        if upstream_status == "failed":
            force_gaps.append({
                "code": "upstream_failed",
                "field": key,
                "reason": "上游快照失败，结构化预评分不可用",
                "retryable": True,
            })
        if evidence_count < minimum_evidence:
            force_gaps.append({
                "code": "insufficient_force_evidence",
                "field": key,
                "reason": f"需要至少 {minimum_evidence} 条覆盖三个子维度的独立事实，当前 {evidence_count} 条",
                "retryable": False,
            })
        confidence = "低" if not ready else "中" if upstream_status == "partial" or missing_count else "高"
        results[key] = {
            "label": payload["label"],
            "base_score": payload["base"] if benchmark else None,
            "score": suggested,
            "suggested_score": suggested,
            "score_band": score_band(suggested) if suggested is not None else None,
            "evidence_count": evidence_count,
            "confidence": confidence,
            "gaps": force_gaps,
            "reasoning": (payload["reasons"] or ["证据不足，暂不生成结构化预评分。"]),
        }

    scored = [(key, item) for key, item in results.items() if item["score"] is not None]
    complete = len(scored) == len(results)
    strongest = max(scored, key=lambda item: item[1]["score"]) if complete else None
    weakest = min(scored, key=lambda item: item[1]["score"]) if complete else None

    return {
        "status": "ok" if complete else "insufficient_evidence",
        "dimensions": results,
        "total_score": sum(item["score"] for _, item in scored) if complete else None,
        "overall_confidence": "高" if complete and not missing_count and upstream_status == "ok" else "中" if complete else "低",
        "strongest_dimension": {
            "key": strongest[0], "label": strongest[1]["label"], "score": strongest[1]["score"],
        } if strongest else None,
        "weakest_dimension": {
            "key": weakest[0], "label": weakest[1]["label"], "score": weakest[1]["score"],
        } if weakest else None,
        "note": "只有五力全部达到证据门槛时才生成总分；外部研究可继续补充证据。",
    }


def scan_summary(summary: str | None, keywords: list[str]) -> list[str]:
    if not summary:
        return []
    lowered = summary.lower()
    hits: list[str] = []
    for keyword in keywords:
        if keyword.lower() in lowered and keyword not in hits:
            hits.append(keyword)
    return hits[:6]


def build_force_facts(
    company_name: str | None,
    summary: str | None,
    market: str,
    info: dict[str, Any],
    enhancements: dict[str, Any],
    recent_news: list[NewsItem],
    event_titles: list[str],
    benchmark_match: dict[str, Any],
) -> dict[str, list[str]]:
    gross_margin_pct = first_not_none(
        _parse_num(info.get("grossMargins")),
        enhancements.get("ths_gross_margin_pct"),
    )
    operating_margin_pct = _parse_num(info.get("operatingMargins"))
    net_margin_pct = first_not_none(
        _parse_num(info.get("profitMargins")),
        enhancements.get("ths_net_margin_pct"),
    )
    revenue_growth_pct = _parse_num(info.get("revenueGrowth"))
    roe_pct = first_not_none(
        _parse_num(info.get("returnOnEquity")),
        enhancements.get("ths_roe_pct"),
    )
    market_cap = info.get("marketCap")
    employees = info.get("fullTimeEmployees")
    industry = first_not_none(info.get("industry"), enhancements.get("xq_industry"))

    supplier_hits = scan_summary(summary, SUPPLIER_HINTS)
    buyer_hits = scan_summary(summary, BUYER_HINTS)
    entry_hits = scan_summary(summary, ENTRY_HINTS)
    substitute_hits = scan_summary(summary, SUBSTITUTE_HINTS)

    rivalry_news = [item.title for item in recent_news if any(k.lower() in item.title.lower() for k in RIVALRY_KEYWORDS)]
    event_force_hints = extract_event_force_hints(event_titles)

    facts = {
        "supplier_power": [],
        "buyer_power": [],
        "entry_threat": [],
        "substitute_threat": [],
        "rivalry": [],
    }

    if gross_margin_pct is not None:
        facts["supplier_power"].append(f"毛利率 {gross_margin_pct}%，可用于判断成本传导与上游涨价吸收能力。")
    if operating_margin_pct is not None:
        facts["supplier_power"].append(f"营业利润率 {operating_margin_pct}%，可交叉验证采购和制造环节的成本控制。")
    for hit in supplier_hits:
        facts["supplier_power"].append(f"公司简介出现 `{hit}`，提示自研、自制或供应链控制线索。")
    if enhancements.get("ths_debt_asset_ratio_pct") is not None:
        facts["supplier_power"].append(
            "A股补充财务摘要显示资产负债率约 {0}%，可结合资本开支和扩产能力判断对上游的依赖程度。".format(
                enhancements["ths_debt_asset_ratio_pct"]
            )
        )
    if market_cap is not None:
        facts["supplier_power"].append(f"公司市值约 {market_cap:,}，规模可作为采购谈判能力的辅助证据。")
    if employees is not None:
        facts["supplier_power"].append(f"员工数约 {employees:,}，组织和制造规模可辅助判断供应链管理能力。")
    facts["supplier_power"].extend(event_force_hints["supplier_power"])

    if gross_margin_pct is not None:
        facts["buyer_power"].append(f"毛利率 {gross_margin_pct}% 是观察定价权和客户压价能力的直接线索。")
    if net_margin_pct is not None:
        facts["buyer_power"].append(f"净利率 {net_margin_pct}% 可辅助判断产品差异化是否转化为股东收益。")
    for hit in buyer_hits:
        facts["buyer_power"].append(f"公司简介出现 `{hit}`，对应品牌、渠道、平台或用户粘性线索。")
    if revenue_growth_pct is not None:
        facts["buyer_power"].append(f"最新收入增速约 {revenue_growth_pct}%，可结合毛利率变化判断提价是否成立。")
    facts["buyer_power"].extend(event_force_hints["buyer_power"])

    if market_cap is not None:
        facts["entry_threat"].append(f"当前市值约 {market_cap:,}，可作为规模、资本壁垒和行业地位的参考。")
    if employees is not None:
        facts["entry_threat"].append(f"员工数约 {employees:,}，可辅助判断组织规模、渠道覆盖和交付壁垒。")
    for hit in entry_hits:
        facts["entry_threat"].append(f"公司简介出现 `{hit}`，提示专利、认证、平台或监管壁垒线索。")
    if industry:
        facts["entry_threat"].append(f"细分行业识别为 `{industry}`，后续应对照行业基准判断进入门槛高低。")
    facts["entry_threat"].extend(event_force_hints["entry_threat"])

    for hit in substitute_hits:
        facts["substitute_threat"].append(f"公司简介出现 `{hit}`，提示产品处于标准、基础设施或关键环节。")
    if recent_news:
        facts["substitute_threat"].append("最近新闻可用于检查是否出现新技术、替代路线或商业模式变化。")
    if roe_pct is not None:
        facts["substitute_threat"].append(f"ROE 约 {roe_pct}% 可作为产品/模式是否具备持续价值的辅助验证。")
    facts["substitute_threat"].extend(event_force_hints["substitute_threat"])

    if industry:
        facts["rivalry"].append(f"当前行业标签为 `{industry}`，应先匹配 `references/industry-benchmark.md` 的最近行业基准。")
    if benchmark_match.get("matched") and benchmark_match.get("benchmark"):
        benchmark = benchmark_match["benchmark"]
        facts["rivalry"].append(
            "自动匹配行业基准 `{0}`，基准总分 {1}/100，可作为后续校准起点。".format(
                benchmark_match["matched_industry"],
                benchmark["total_score"],
            )
        )
    if gross_margin_pct is not None and revenue_growth_pct is not None:
        facts["rivalry"].append(f"收入增速 {revenue_growth_pct}% 与毛利率 {gross_margin_pct}% 的组合，可用于观察竞争是否侵蚀利润。")
    if rivalry_news:
        facts["rivalry"].append("近期新闻标题含 `{0}`，需重点检查是否存在价格战或竞争加剧。".format(" / ".join(rivalry_news[:3])))
    elif recent_news:
        facts["rivalry"].append("最近新闻标题可用于识别价格战、监管、产能扩张或行业出清线索。")
    facts["rivalry"].extend(event_force_hints["rivalry"])

    if company_name and market != "A-share":
        facts["rivalry"].append(f"{company_name} 当前主要依赖 Yahoo Finance 跨市场数据，同行名单建议结合用户指定可比公司补充。")

    return facts


def _parse_news_items(raw_news: list[dict[str, Any]] | None, limit: int = 5) -> list[NewsItem]:
    """将 inv-stock-data 返回的 news 列表转为 NewsItem。"""
    items: list[NewsItem] = []
    for raw in raw_news or []:
        title = raw.get("title")
        if not title:
            continue
        items.append(
            NewsItem(
                title=str(title),
                publisher=raw.get("publisher"),
                published_at=raw.get("published_at"),
                link=raw.get("link"),
            )
        )
        if len(items) >= limit:
            break
    return items


def build_snapshot(symbol: str, forced_market: str) -> Snapshot:
    """Build a Porter fact sheet from the inv-stock-data v1 public contract."""
    from porter_data_adapter import adapt_snapshot_envelope

    normalized = normalize_symbol(symbol, forced_market)
    raw = _call_cs_stock("snapshot", normalized)
    facts = adapt_snapshot_envelope(raw)
    upstream = facts.upstream
    data_gaps = [dict(item) for item in upstream["gaps"]]

    announcements: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    if facts.market == "A-share":
        plain = to_a_share_code(symbol)
        for command, target in (("announcements", announcements), ("relations", relations)):
            payload = _call_cs_stock(command, plain)
            if payload.get("schema_version") == "1.0":
                data = payload.get("data") or {}
                target.extend(data.get(command) or [])
                data_gaps.extend(dict(item) for item in payload.get("gaps") or [])
                upstream["sources"].extend(dict(item) for item in payload.get("sources") or [])

    fund = facts.fundamentals
    info = {
        "industry": facts.industry,
        "sector": facts.sector,
        "marketCap": fund.get("market_cap"),
        "fullTimeEmployees": fund.get("employees"),
        "grossMargins": fund.get("gross_margin_pct"),
        "operatingMargins": fund.get("operating_margin_pct"),
        "profitMargins": fund.get("net_margin_pct"),
        "returnOnEquity": fund.get("roe_pct"),
        "returnOnAssets": fund.get("roa_pct"),
        "revenueGrowth": fund.get("revenue_growth_pct"),
        "earningsGrowth": fund.get("earnings_growth_pct"),
        "debtToEquity": fund.get("debt_to_equity"),
        "freeCashflow": fund.get("free_cashflow") or fund.get("free_cash_flow"),
        "totalRevenue": fund.get("total_revenue"),
    }
    enhancements: dict[str, Any] = {}
    financial_metrics = {
        "market_cap": info["marketCap"],
        "enterprise_value": fund.get("enterprise_value"),
        "total_revenue": info["totalRevenue"],
        "gross_margin_pct": _parse_num(info["grossMargins"]),
        "operating_margin_pct": _parse_num(info["operatingMargins"]),
        "net_margin_pct": _parse_num(info["profitMargins"]),
        "roe_pct": _parse_num(info["returnOnEquity"]),
        "roa_pct": _parse_num(info["returnOnAssets"]),
        "revenue_growth_pct": _parse_num(info["revenueGrowth"]),
        "earnings_growth_pct": _parse_num(info["earningsGrowth"]),
        "free_cash_flow": info["freeCashflow"],
        "debt_to_equity": _parse_num(info["debtToEquity"]),
        "employees": info["fullTimeEmployees"],
        "a_share_report_date": None,
    }
    benchmark = match_industry_benchmark(facts.industry, facts.sector, facts.business_summary)
    event_titles = [
        str(item.get("title") or item.get("标题") or item.get("公告标题"))
        for item in announcements + relations
        if item.get("title") or item.get("标题") or item.get("公告标题")
    ]
    force_facts = build_force_facts(
        company_name=facts.company_name,
        summary=facts.business_summary,
        market=facts.market,
        info=info,
        enhancements=enhancements,
        recent_news=[],
        event_titles=event_titles,
        benchmark_match=benchmark,
    )
    for field, label in ((facts.company_name, "公司名称"), (facts.industry, "细分行业"), (facts.business_summary, "主营/商业模式摘要")):
        if not field:
            data_gaps.append({
                "code": "field_unavailable", "field": f"company.{label}",
                "reason": f"缺少{label}", "retryable": False,
            })
    if not benchmark.get("matched"):
        data_gaps.append({
            "code": "benchmark_unmatched", "field": "industry_benchmark",
            "reason": "未自动匹配到行业基准", "retryable": False,
        })
    pre_scoring = build_pre_scoring(
        financial_metrics=financial_metrics,
        industry_benchmark=benchmark,
        five_forces_facts=force_facts,
        event_titles=event_titles,
        event_time_map=None,
        data_gaps=data_gaps,
        upstream_status=upstream["status"],
    )
    return Snapshot(
        symbol=symbol,
        normalized_symbol=normalized,
        company_name=facts.company_name,
        market=facts.market,
        currency=facts.currency,
        data_time=upstream["data_as_of"],
        data_sources=upstream["sources"],
        upstream=upstream,
        company_profile={
            "sector": facts.sector,
            "industry": facts.industry,
            "country": None,
            "exchange": None,
            "business_summary": facts.business_summary,
        },
        financial_metrics=financial_metrics,
        market_signals={
            "current_price": facts.price,
            "currency": facts.currency,
            "high_52w": None,
            "low_52w": None,
            "position_in_52w_range_pct": None,
            "analyst_target_price": None,
            "analyst_upside_pct": None,
            "analyst_count": None,
            "next_earnings_date": None,
            "last_earnings_date": None,
        },
        peer_reference={"industry_label": facts.industry, "sector_label": facts.sector, "peer_candidates": [], "industry_peer_count": len(relations)},
        industry_benchmark=benchmark,
        recent_developments={"recent_news": [], "a_share_announcements": announcements, "a_share_research_records": relations},
        five_forces_facts=force_facts,
        pre_scoring=pre_scoring,
        data_gaps=data_gaps,
        notes=upstream["notes"],
    )


def render_text(snapshot: Snapshot) -> str:
    lines = [
        "=" * 72,
        f"波特五力事实底稿: {snapshot.symbol} ({snapshot.company_name or '未知标的'})",
        "=" * 72,
        f"市场: {snapshot.market} | 币种: {snapshot.currency or '--'} | 数据时间: {snapshot.data_time}",
        f"上游状态: {snapshot.upstream.get('status')} | 数据源: {json.dumps(snapshot.data_sources, ensure_ascii=False)}",
        "",
        "【公司画像】",
        f"行业: {snapshot.company_profile.get('industry') or '--'}",
        f"板块: {snapshot.company_profile.get('sector') or '--'}",
        f"国家/地区: {snapshot.company_profile.get('country') or '--'}",
        f"交易所: {snapshot.company_profile.get('exchange') or '--'}",
        "",
        "【关键财务】",
        f"市值: {snapshot.financial_metrics.get('market_cap')}",
        f"收入: {snapshot.financial_metrics.get('total_revenue')}",
        "毛利率/营业利润率/净利率: {0}% / {1}% / {2}%".format(
            snapshot.financial_metrics.get("gross_margin_pct") or "--",
            snapshot.financial_metrics.get("operating_margin_pct") or "--",
            snapshot.financial_metrics.get("net_margin_pct") or "--",
        ),
        "ROE/ROA/收入增速: {0}% / {1}% / {2}%".format(
            snapshot.financial_metrics.get("roe_pct") or "--",
            snapshot.financial_metrics.get("roa_pct") or "--",
            snapshot.financial_metrics.get("revenue_growth_pct") or "--",
        ),
        "",
        "【行业基准】",
    ]

    benchmark = snapshot.industry_benchmark
    if benchmark.get("matched") and benchmark.get("benchmark"):
        bench = benchmark["benchmark"]
        lines.extend(
            [
                "匹配行业: {0} ({1})".format(
                    benchmark.get("matched_industry"),
                    benchmark.get("match_type"),
                ),
                "基准分: 供应商 {0} / 购买者 {1} / 新进入者 {2} / 替代品 {3} / 同业竞争 {4} / 总分 {5}".format(
                    bench["supplier_power"],
                    bench["buyer_power"],
                    bench["entry_threat"],
                    bench["substitute_threat"],
                    bench["rivalry"],
                    bench["total_score"],
                ),
                "",
            ]
        )
    else:
        lines.extend([benchmark.get("reason", "未匹配到行业基准"), ""])

    lines.extend(["【预评分】"])
    total = snapshot.pre_scoring["total_score"]
    strongest = snapshot.pre_scoring.get("strongest_dimension")
    weakest = snapshot.pre_scoring.get("weakest_dimension")
    lines.append(
        "建议总分: {0} | 状态 {1} | 置信度 {2} | 最强维度 {3} | 最弱维度 {4}".format(
            "未生成（证据不足）" if total is None else f"{total}/100",
            snapshot.pre_scoring["status"],
            snapshot.pre_scoring["overall_confidence"],
            strongest["label"] if strongest else "--",
            weakest["label"] if weakest else "--",
        )
    )
    for key in ["supplier_power", "buyer_power", "entry_threat", "substitute_threat", "rivalry"]:
        item = snapshot.pre_scoring["dimensions"][key]
        score = "未评分" if item["score"] is None else f"{item['score']}/20"
        lines.append(f"{item['label']}: {score}（证据 {item['evidence_count']}，置信度 {item['confidence']}）")
        for gap in item["gaps"]:
            lines.append(f"- 缺口：{gap['reason']}")
        for reason in item["reasoning"][:3]:
            lines.append(f"- {reason}")

    lines.extend(["", "【五力线索】"])

    label_map = {
        "supplier_power": "供应商议价能力",
        "buyer_power": "购买者议价能力",
        "entry_threat": "新进入者威胁",
        "substitute_threat": "替代品威胁",
        "rivalry": "同业竞争程度",
    }
    for key, label in label_map.items():
        lines.append(f"{label}:")
        items = snapshot.five_forces_facts.get(key) or ["暂无可用线索"]
        for item in items:
            lines.append(f"- {item}")

    lines.extend(["", "【近期动态】"])
    news = snapshot.recent_developments.get("recent_news") or []
    if news:
        for item in news[:5]:
            lines.append("- {0} | {1}".format(item.get("published_at") or "--", item.get("title")))
    else:
        lines.append("- 暂无 Yahoo Finance 新闻")

    if snapshot.market == "A-share":
        announcements = snapshot.recent_developments.get("a_share_announcements") or []
        if announcements:
            lines.append("")
            lines.append("【A股公告】")
            for item in announcements[:5]:
                lines.append(f"- {item.get('published_at') or item.get('time') or '--'} | {item.get('title')}")

    peers = snapshot.peer_reference.get("peer_candidates") or []
    if peers:
        lines.extend(["", "【A股行业可比】"])
        for peer in peers[:8]:
            lines.append(f"- {peer.get('symbol') or '--'} {peer.get('name') or '--'}")

    if snapshot.data_gaps:
        lines.extend(["", "【数据缺口】"])
        for gap in snapshot.data_gaps:
            lines.append(f"- {gap.get('field')}: {gap.get('reason')} ({gap.get('code')})")

    if snapshot.notes:
        lines.extend(["", "【备注】"])
        for note in snapshot.notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def render_markdown(snapshot: Snapshot) -> str:
    lines = [
        f"# 波特五力事实底稿：{snapshot.symbol} {f'({snapshot.company_name})' if snapshot.company_name else ''}",
        "",
        "## 基本信息",
        f"- 市场：{snapshot.market}",
        f"- 币种：{snapshot.currency or '--'}",
        f"- 数据时间：{snapshot.data_time}",
        f"- 上游状态：{snapshot.upstream.get('status')}",
        f"- 数据源：{json.dumps(snapshot.data_sources, ensure_ascii=False)}",
        "",
        "## 公司画像",
        f"- 行业：{snapshot.company_profile.get('industry') or '--'}",
        f"- 板块：{snapshot.company_profile.get('sector') or '--'}",
        f"- 国家/地区：{snapshot.company_profile.get('country') or '--'}",
        f"- 交易所：{snapshot.company_profile.get('exchange') or '--'}",
        "",
        "## 关键财务",
        f"- 市值：{snapshot.financial_metrics.get('market_cap') or '--'}",
        f"- 收入：{snapshot.financial_metrics.get('total_revenue') or '--'}",
        f"- 毛利率/营业利润率/净利率：{snapshot.financial_metrics.get('gross_margin_pct') or '--'}% / {snapshot.financial_metrics.get('operating_margin_pct') or '--'}% / {snapshot.financial_metrics.get('net_margin_pct') or '--'}%",
        f"- ROE/ROA/收入增速：{snapshot.financial_metrics.get('roe_pct') or '--'}% / {snapshot.financial_metrics.get('roa_pct') or '--'}% / {snapshot.financial_metrics.get('revenue_growth_pct') or '--'}%",
        "",
        "## 行业基准",
    ]

    benchmark = snapshot.industry_benchmark
    if benchmark.get("matched") and benchmark.get("benchmark"):
        bench = benchmark["benchmark"]
        lines.extend(
            [
                f"- 匹配行业：{benchmark.get('matched_industry')} ({benchmark.get('match_type')})",
                f"- 基准总分：{bench['total_score']}/100",
                "| 维度 | 基准分 |",
                "|------|--------|",
                f"| 供应商议价能力 | {bench['supplier_power']} |",
                f"| 购买者议价能力 | {bench['buyer_power']} |",
                f"| 新进入者威胁 | {bench['entry_threat']} |",
                f"| 替代品威胁 | {bench['substitute_threat']} |",
                f"| 同业竞争程度 | {bench['rivalry']} |",
            ]
        )
    else:
        lines.append(f"- {benchmark.get('reason', '未匹配到行业基准')}")

    lines.extend(["", "## 预评分"])
    total = snapshot.pre_scoring["total_score"]
    lines.append(f"- 状态：{snapshot.pre_scoring['status']}")
    lines.append(f"- 建议总分：{'未生成（证据不足）' if total is None else f'{total}/100'}")
    lines.append(f"- 整体置信度：{snapshot.pre_scoring['overall_confidence']}")
    strongest = snapshot.pre_scoring.get("strongest_dimension")
    weakest = snapshot.pre_scoring.get("weakest_dimension")
    lines.append(f"- 最强维度：{strongest['label'] if strongest else '--'}")
    lines.append(f"- 最弱维度：{weakest['label'] if weakest else '--'}")
    for key in ["supplier_power", "buyer_power", "entry_threat", "substitute_threat", "rivalry"]:
        item = snapshot.pre_scoring["dimensions"][key]
        score = "未评分" if item["score"] is None else f"{item['score']}/20"
        lines.append(f"### {item['label']}：{score}（证据 {item['evidence_count']}，置信度 {item['confidence']}）")
        for gap in item["gaps"]:
            lines.append(f"- 缺口：{gap['reason']}")
        for reason in item["reasoning"][:3]:
            lines.append(f"- {reason}")

    lines.extend(["", "## 五力线索"])
    label_map = {
        "supplier_power": "供应商议价能力",
        "buyer_power": "购买者议价能力",
        "entry_threat": "新进入者威胁",
        "substitute_threat": "替代品威胁",
        "rivalry": "同业竞争程度",
    }
    for key, label in label_map.items():
        lines.append(f"### {label}")
        items = snapshot.five_forces_facts.get(key) or ["暂无可用线索"]
        for item in items:
            lines.append(f"- {item}")

    lines.extend(["", "## 近期动态"])
    news = snapshot.recent_developments.get("recent_news") or []
    if news:
        for item in news[:5]:
            lines.append(f"- {item.get('published_at') or '--'} | {item.get('title')}")
    else:
        lines.append("- 暂无 Yahoo Finance 新闻")

    if snapshot.market == "A-share":
        announcements = snapshot.recent_developments.get("a_share_announcements") or []
        if announcements:
            lines.extend(["", "## A股公告"])
            for item in announcements[:5]:
                lines.append(f"- {item.get('published_at') or item.get('time') or '--'} | {item.get('title')}")

    if snapshot.data_gaps:
        lines.extend(["", "## 数据缺口"])
        for gap in snapshot.data_gaps:
            lines.append(f"- {gap.get('field')}: {gap.get('reason')} ({gap.get('code')})")

    if snapshot.notes:
        lines.extend(["", "## 备注"])
        for note in snapshot.notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="波特五力分析事实快照")
    parser.add_argument("symbol", help="股票代码，例如 600519 / 0700.HK / AAPL")
    parser.add_argument(
        "--market",
        default="auto",
        choices=["auto", "a", "hk", "us"],
        help="市场类型，默认自动识别",
    )
    parser.add_argument(
        "--output",
        default="text",
        choices=["text", "json", "markdown"],
        help="输出格式",
    )
    args = parser.parse_args()

    try:
        snapshot = build_snapshot(args.symbol, args.market)
        if args.output == "json":
            print(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2))
        elif args.output == "markdown":
            print(render_markdown(snapshot))
        else:
            print(render_text(snapshot))
        return 1 if snapshot.upstream.get("status") == "failed" else 0
    except Exception as exc:
        print(f"五力数据抓取失败: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
