"""前置指标框架 — 指标配置数据结构与 handler 注册表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndicatorConfig:
    """单个前置指标的元数据配置。

    每个 IndicatorConfig 实例描述一个指标的完整信息：
    - 基础属性：key/name/direction/weight/unit
    - 数据来源：data_method（script | agent_search）、handler 类型
    - 传导与评分：transmission_summary、scoring_guide
    - 可选属性：tier（层级分组）、threshold（阈值）、search_hint
    """

    key: str
    name: str
    direction: str
    weight: float
    unit: str
    data_method: str  # "script" | "agent_search"
    handler: str  # "kline" | "macro" | "ranking" | "agent_search"
    transmission_summary: str = ""
    scoring_guide: str = ""
    tier: int | None = None
    threshold: dict[str, Any] | None = None
    search_hint: str | None = None

    # handler 特有参数（仅部分 handler 使用）
    handler_extra: dict[str, Any] = field(default_factory=dict)


# handler 类型 → 处理函数的注册表（由 handlers.py 在导入时填充）
HANDLER_REGISTRY: dict[str, Any] = {}


def register_handler(handler_type: str, handler_fn) -> None:
    """注册一个 handler 处理函数。"""
    HANDLER_REGISTRY[handler_type] = handler_fn


def get_handler(handler_type: str):
    """获取已注册的 handler，未注册则返回 None。"""
    return HANDLER_REGISTRY.get(handler_type)