"""inv-stock-data v1 public payload contract.

This module is intentionally network- and provider-independent so producers,
consumers, and offline contract tests share one source of truth.
"""

from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "1.0"
VALID_STATUSES = frozenset({"ok", "partial", "failed"})
VALID_PERIODS = frozenset({"1mo", "1y", "5y", "max"})

MIN_52W_OBSERVATIONS = 200
MIN_52W_DAYS = 350
MIN_250D_OBSERVATIONS = 251
MIN_5Y_OBSERVATIONS = 1000
MIN_5Y_DAYS = 1643  # 4.5 years, rounded down


def make_symbol(raw: str, code: str, market: str) -> dict[str, str]:
    """Build the normalized symbol descriptor used by every command."""
    return {"input": raw, "code": code, "market": market}


def make_source(
    name: str,
    status: str,
    *,
    fallback: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    """Describe one provider attempt."""
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid source status: {status}")
    result: dict[str, Any] = {
        "name": name,
        "status": status,
        "fallback": bool(fallback),
    }
    if reason:
        result["reason"] = reason
    return result


def make_gap(
    code: str,
    field: str,
    reason: str,
    *,
    retryable: bool = False,
) -> dict[str, Any]:
    """Build a machine-readable data gap."""
    if not code or not field or not reason:
        raise ValueError("gap code, field, and reason are required")
    return {
        "code": code,
        "field": field,
        "reason": reason,
        "retryable": bool(retryable),
    }


def make_window(
    requested: str,
    observations: int,
    first_date: str | None,
    last_date: str | None,
) -> dict[str, Any]:
    """Describe the requested and actual historical coverage."""
    if requested not in VALID_PERIODS:
        raise ValueError(f"invalid period: {requested}")
    if observations < 0:
        raise ValueError("observations must be non-negative")
    return {
        "requested": requested,
        "observations": observations,
        "first_date": first_date,
        "last_date": last_date,
    }


def make_envelope(
    command: str,
    status: str,
    symbol: Mapping[str, Any],
    data: Mapping[str, Any] | None,
    *,
    data_as_of: str | None = None,
    sources: Iterable[Mapping[str, Any]] = (),
    gaps: Iterable[Mapping[str, Any]] = (),
    notes: Iterable[str] = (),
    window: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a v1 public command response."""
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "symbol": dict(symbol),
        "data_as_of": data_as_of,
        "sources": [dict(item) for item in sources],
        "gaps": [dict(item) for item in gaps],
        "notes": [str(item) for item in notes],
        "data": sanitize_json(dict(data or {})),
    }
    if window is not None:
        payload["window"] = dict(window)
    validate_envelope(payload)
    return payload


def make_component(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Project a command envelope into an ``all`` component."""
    validate_envelope(payload)
    component = {
        "status": payload["status"],
        "data": dict(payload["data"]),
        "sources": [dict(item) for item in payload["sources"]],
        "gaps": [dict(item) for item in payload["gaps"]],
        "data_as_of": payload.get("data_as_of"),
    }
    if "window" in payload:
        component["window"] = dict(payload["window"])
    return component


def aggregate_status(statuses: Iterable[str]) -> str:
    """Aggregate component statuses without hiding partial failures."""
    values = list(statuses)
    if not values:
        return "failed"
    unknown = [value for value in values if value not in VALID_STATUSES]
    if unknown:
        raise ValueError(f"invalid component status: {unknown[0]}")
    if all(value == "ok" for value in values):
        return "ok"
    if all(value == "failed" for value in values):
        return "failed"
    return "partial"


def validate_envelope(payload: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` when a payload violates the v1 contract."""
    required = {
        "schema_version", "command", "status", "symbol", "data_as_of",
        "sources", "gaps", "notes", "data",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"missing envelope fields: {', '.join(missing)}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema version: {payload['schema_version']}")
    if payload["status"] not in VALID_STATUSES:
        raise ValueError(f"invalid status: {payload['status']}")
    symbol = payload["symbol"]
    if not isinstance(symbol, Mapping) or not all(symbol.get(key) for key in ("input", "code", "market")):
        raise ValueError("symbol must contain input, code, and market")
    if not isinstance(payload["data"], Mapping):
        raise ValueError("data must be an object")
    if not isinstance(payload["sources"], list) or not isinstance(payload["gaps"], list):
        raise ValueError("sources and gaps must be arrays")
    for source in payload["sources"]:
        if not isinstance(source, Mapping) or source.get("status") not in VALID_STATUSES:
            raise ValueError("invalid source entry")
        if not source.get("name") or not isinstance(source.get("fallback"), bool):
            raise ValueError("source requires name and boolean fallback")
    for gap in payload["gaps"]:
        if not isinstance(gap, Mapping) or not all(gap.get(key) for key in ("code", "field", "reason")):
            raise ValueError("invalid gap entry")
        if not isinstance(gap.get("retryable"), bool):
            raise ValueError("gap retryable must be boolean")
    if payload["status"] == "failed" and payload["data"]:
        components = payload["data"].get("components") if payload.get("command") == "all" else None
        diagnostic_only = (
            isinstance(components, Mapping)
            and components
            and all(
                isinstance(component, Mapping)
                and component.get("status") == "failed"
                and not component.get("data")
                for component in components.values()
            )
        )
        if not diagnostic_only:
            raise ValueError("failed envelopes must not contain domain data")
    if payload["status"] != "ok" and not payload["gaps"]:
        raise ValueError("partial and failed envelopes require at least one gap")
    if "window" in payload:
        window = payload["window"]
        if not isinstance(window, Mapping) or window.get("requested") not in VALID_PERIODS:
            raise ValueError("invalid window")
        if not isinstance(window.get("observations"), int) or window["observations"] < 0:
            raise ValueError("window observations must be a non-negative integer")


def sanitize_json(value: Any) -> Any:
    """Recursively replace non-finite provider numbers with JSON null."""
    if isinstance(value, Mapping):
        return {str(key): sanitize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def extract_date(value: Any) -> str | None:
    """Normalize common provider date values to ``YYYY-MM-DD``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    return text[:10] if len(text) >= 10 else text or None


def historical_eligibility(window: Mapping[str, Any]) -> dict[str, bool]:
    """Return long-horizon metric eligibility from actual coverage."""
    observations = int(window.get("observations") or 0)
    days = _coverage_days(window.get("first_date"), window.get("last_date"))
    return {
        "52w": observations >= MIN_52W_OBSERVATIONS and days >= MIN_52W_DAYS,
        "250d_return": observations >= MIN_250D_OBSERVATIONS,
        "5y_percentile": observations >= MIN_5Y_OBSERVATIONS and days >= MIN_5Y_DAYS,
    }


def historical_gaps(window: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Describe every long-horizon metric blocked by insufficient history."""
    eligible = historical_eligibility(window)
    definitions = (
        ("52w", "metrics.position_52w", "52 周指标需要至少 200 个观测且覆盖 350 天"),
        ("250d_return", "metrics.return_250d_pct", "250 日收益需要至少 251 个观测"),
        ("5y_percentile", "metrics.price_percentile_5y_proxy", "5 年分位需要至少 1000 个观测且覆盖 4.5 年"),
    )
    return [
        make_gap("insufficient_history", field, reason)
        for key, field, reason in definitions
        if not eligible[key]
    ]


def _coverage_days(first_date: Any, last_date: Any) -> int:
    first = _parse_date(first_date)
    last = _parse_date(last_date)
    if first is None or last is None or last < first:
        return 0
    return (last - first).days


def _parse_date(value: Any) -> date | None:
    normalized = extract_date(value)
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None
