"""前置指标框架 — 快照构建与文本渲染。

核心函数：
- build_snapshot(): 从 config + fetcher 结果构建统一快照
- render_text_snapshot(): 将快照渲染为 Markdown 文本
- fetch_all_concurrent(): 并发调用 fetcher 函数
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from .config import IndicatorConfig, get_handler
from . import handlers  # noqa: F401 — 触发 handler 注册


def fetch_all_concurrent(
    fetchers: dict[str, Callable],
    max_workers: int = 3,
) -> tuple[dict[str, dict], dict[str, str]]:
    """并发调用已注册的 fetcher 函数。

    Args:
        fetchers: {indicator_key: fetcher_callable} 映射。
        max_workers: 最大并发线程数。

    Returns:
        (results, errors) — results 为 {key: fetcher返回值}，errors 为 {key: 错误信息}。
        单个 fetcher 失败不影响其他。
    """
    results: dict[str, dict] = {}
    errors: dict[str, str] = {}

    if not fetchers:
        return results, errors

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_key = {
            executor.submit(fn): key
            for key, fn in fetchers.items()
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as e:
                errors[key] = str(e)

    return results, errors


def build_snapshot(
    indicators_config: dict[str, dict],
    fetchers: dict[str, Callable] | None = None,
    fetch_results: dict[str, dict] | None = None,
    fetch_errors: dict[str, str] | None = None,
    *,
    snapshot_version: str = "3.0",
    max_workers: int = 3,
) -> dict:
    """构建统一格式的指标快照。

    工作流：
    1. 如果传入了 fetchers 且未传 fetch_results，先并发获取数据
    2. 遍历 indicators_config，按 handler 类型分发处理
    3. 组装四态 data_quality 快照

    Args:
        indicators_config: {key: {字段字典}} 指标配置（兼容现有 dict 格式）。
        fetchers: {key: fetcher_callable} 可选，传入后自动并发获取。
        fetch_results: {key: fetcher返回值} 可选，已有结果时直接传入。
        fetch_errors: {key: 错误信息} 可选。
        snapshot_version: 快照版本号。
        max_workers: 并发获取时的最大线程数。

    Returns:
        快照 dict，顶层包含 snapshot_version、fetched_at、indicators。
    """
    # 1. 获取数据
    if fetchers and fetch_results is None:
        fetch_results, fetch_errors = fetch_all_concurrent(fetchers, max_workers)

    results = fetch_results or {}
    errors = fetch_errors or {}

    # 2. 遍历 config，构建指标条目
    snapshot_indicators: dict[str, Any] = {}

    for key, cfg_raw in indicators_config.items():
        cfg = _dict_to_config(key, cfg_raw)

        entry: dict[str, Any] = {
            "name": cfg.name,
            "direction": cfg.direction,
            "weight": cfg.weight,
            "unit": cfg.unit,
            "data_method": cfg.data_method,
            "data_quality": "missing",
            "transmission_summary": cfg.transmission_summary,
            "scoring_guide": cfg.scoring_guide,
        }
        if cfg.tier is not None:
            entry["tier"] = cfg.tier
        if cfg.threshold is not None:
            entry["threshold"] = cfg.threshold

        # 处理数据
        if key in errors:
            entry["data_quality"] = "missing"
            entry["error"] = errors[key]
        elif key in results:
            raw = results[key]
            handler_fn = get_handler(cfg.handler)
            if handler_fn:
                processed = handler_fn(cfg, raw)
                entry.update(processed)
            else:
                entry["data_quality"] = "missing"
                entry["error"] = f"unknown_handler: {cfg.handler}"
        elif cfg.data_method == "agent_search":
            handler_fn = get_handler("agent_search")
            if handler_fn:
                processed = handler_fn(cfg, {})
                entry.update(processed)
        elif cfg.data_method == "script":
            entry["data_quality"] = "missing"
            entry["error"] = "no_fetcher_registered"

        snapshot_indicators[key] = entry

    return {
        "snapshot_version": snapshot_version,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "indicators": snapshot_indicators,
    }


def render_text_snapshot(snapshot: dict) -> str:
    """将快照渲染为人类可读的 Markdown 文本。

    Args:
        snapshot: build_snapshot() 返回的快照 dict。

    Returns:
        Markdown 格式的文本。
    """
    lines: list[str] = []
    indicators = snapshot.get("indicators", {})

    for key, entry in indicators.items():
        name = entry.get("name", key)
        direction = entry.get("direction", "")
        weight = entry.get("weight", 0)
        tier = entry.get("tier")
        quality = entry.get("data_quality", "missing")

        if tier is not None:
            lines.append(f"## {name} (Tier{tier}, {direction}, 权重{weight:.0%})")
        else:
            lines.append(f"## {name} ({direction}，权重{weight:.0%})")

        if quality == "agent_required":
            search_hint = entry.get("search_hint", "")
            lines.append(f"**数据质量**: agent_required")
            if search_hint:
                lines.append(f"**搜索建议**: {search_hint}")
        elif quality == "missing":
            error = entry.get("error", "")
            lines.append(f"**数据质量**: missing")
            if error:
                lines.append(f"**错误**: {error}")
        elif quality == "partial":
            lines.append(f"**数据质量**: partial")
            _render_data_fields(lines, entry)
            raw_text = entry.get("raw_text", "")
            if raw_text:
                lines.append(f"- 原始文本（供LLM提取）：{raw_text[:100]}...")
        elif quality == "complete":
            lines.append(f"**数据质量**: complete")
            _render_data_fields(lines, entry)
        else:
            lines.append(f"**数据质量**: {quality}")
            _render_data_fields(lines, entry)

        ts = entry.get("transmission_summary", "")
        if ts:
            lines.append(f"**传导机制**: {ts}")
        sg = entry.get("scoring_guide", "")
        if sg:
            lines.append(f"**评分指引**: {sg}")

        lines.append("")

    return "\n".join(lines)


def _dict_to_config(key: str, cfg_raw: dict) -> IndicatorConfig:
    """从 dict 构建 IndicatorConfig 实例。"""
    return IndicatorConfig(
        key=key,
        name=cfg_raw.get("name", key),
        direction=cfg_raw.get("direction", ""),
        weight=cfg_raw.get("weight", 0),
        unit=cfg_raw.get("unit", ""),
        data_method=cfg_raw.get("data_method", "script"),
        handler=cfg_raw.get("handler", "macro"),
        transmission_summary=cfg_raw.get("transmission_summary", ""),
        scoring_guide=cfg_raw.get("scoring_guide", ""),
        tier=cfg_raw.get("tier"),
        threshold=cfg_raw.get("threshold"),
        search_hint=cfg_raw.get("search_hint"),
        handler_extra=cfg_raw.get("handler_extra", {}),
    )


def _render_data_fields(lines: list[str], entry: dict) -> None:
    """渲染数据字段（排除元数据字段）。"""
    skip_keys = {
        "name", "direction", "weight", "unit", "data_method",
        "data_quality", "transmission_summary", "scoring_guide",
        "tier", "threshold", "search_hint", "error", "raw_text",
    }
    for k, v in entry.items():
        if k in skip_keys:
            continue
        if isinstance(v, bool):
            v = "⚠️ 是" if v else "否"
        lines.append(f"- {k}: {v}")