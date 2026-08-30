"""Thin adapter from inv-stock-data v1 envelopes to valuation inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class UnsupportedSchemaError(ValueError):
    pass


class InvalidEnvelopeError(ValueError):
    pass


@dataclass(frozen=True)
class Envelope:
    command: str
    status: str
    symbol: dict[str, Any]
    data_as_of: str | None
    sources: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    notes: list[str]
    data: dict[str, Any]
    window: dict[str, Any] | None = None


def parse_v1_envelope(payload: Mapping[str, Any], *, expected_command: str | None = None) -> Envelope:
    version = payload.get("schema_version")
    if not isinstance(version, str) or version.split(".", 1)[0] != "1":
        raise UnsupportedSchemaError(f"unsupported investment data schema: {version!r}")
    required = {"command", "status", "symbol", "data_as_of", "sources", "gaps", "notes", "data"}
    missing = sorted(required.difference(payload))
    if missing:
        raise InvalidEnvelopeError(f"missing envelope fields: {', '.join(missing)}")
    command = str(payload["command"])
    if expected_command and command != expected_command:
        raise InvalidEnvelopeError(f"expected {expected_command}, got {command}")
    status = str(payload["status"])
    if status not in {"ok", "partial", "failed"}:
        raise InvalidEnvelopeError(f"invalid status: {status}")
    data = payload["data"]
    if not isinstance(data, Mapping):
        raise InvalidEnvelopeError("data must be an object")
    return Envelope(
        command=command,
        status=status,
        symbol=dict(payload["symbol"]),
        data_as_of=payload.get("data_as_of"),
        sources=[dict(item) for item in payload["sources"]],
        gaps=[dict(item) for item in payload["gaps"]],
        notes=[str(item) for item in payload["notes"]],
        data=dict(data),
        window=dict(payload["window"]) if payload.get("window") else None,
    )


def parse_all_components(payload: Mapping[str, Any]) -> tuple[Envelope, dict[str, dict[str, Any]]]:
    envelope = parse_v1_envelope(payload, expected_command="all")
    components = envelope.data.get("components")
    if not isinstance(components, Mapping):
        raise InvalidEnvelopeError("all.data.components is required")
    expected = {"snapshot", "financial", "financials"}
    missing = sorted(expected.difference(components))
    if missing:
        raise InvalidEnvelopeError(f"missing all components: {', '.join(missing)}")
    result: dict[str, dict[str, Any]] = {}
    for name in expected:
        component = components[name]
        if not isinstance(component, Mapping) or component.get("status") not in {"ok", "partial", "failed"}:
            raise InvalidEnvelopeError(f"invalid component: {name}")
        result[name] = dict(component)
    return envelope, result


def component_data(component: Mapping[str, Any]) -> dict[str, Any]:
    data = component.get("data")
    return dict(data) if isinstance(data, Mapping) else {}


def percent(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number * 100, 2) if abs(number) <= 1 else round(number, 2)


def number(value: Any) -> float | None:
    return _number(value)


def has_fallback(sources: list[dict[str, Any]]) -> bool:
    return any(item.get("fallback") and item.get("status") == "ok" for item in sources)


def merge_gaps(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen = set()
    for group in groups:
        for gap in group:
            key = (gap.get("code"), gap.get("field"), gap.get("reason"))
            if key not in seen:
                result.append(dict(gap))
                seen.add(key)
    return result


def _number(value: Any) -> float | None:
    """解析带中文量级单位（亿/万）与百分号的数值。

    - "104.13亿" → 10413000000.0
    - "2.3万"    → 23000.0
    - "38.5%"    → 38.5
    """
    if value is None or value is False:
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
