"""Thin adapter from inv-stock-data v1 snapshot envelopes to Porter facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class UnsupportedSchemaError(ValueError):
    pass


class InvalidEnvelopeError(ValueError):
    pass


@dataclass(frozen=True)
class PorterCompanyFacts:
    company_name: str | None
    market: str
    currency: str | None
    sector: str | None
    industry: str | None
    business_summary: str | None
    price: float | None
    fundamentals: dict[str, Any]
    upstream: dict[str, Any]


def adapt_snapshot_envelope(payload: Mapping[str, Any]) -> PorterCompanyFacts:
    version = payload.get("schema_version")
    if not isinstance(version, str) or version.split(".", 1)[0] != "1":
        raise UnsupportedSchemaError(f"unsupported investment data schema: {version!r}")
    required = {"command", "status", "symbol", "data_as_of", "sources", "gaps", "notes", "data"}
    missing = sorted(required.difference(payload))
    if missing:
        raise InvalidEnvelopeError(f"missing envelope fields: {', '.join(missing)}")
    if payload.get("command") != "snapshot":
        raise InvalidEnvelopeError(f"expected snapshot, got {payload.get('command')}")
    if payload.get("status") not in {"ok", "partial", "failed"}:
        raise InvalidEnvelopeError(f"invalid status: {payload.get('status')}")
    symbol = payload.get("symbol")
    data = payload.get("data")
    if not isinstance(symbol, Mapping) or not isinstance(data, Mapping):
        raise InvalidEnvelopeError("symbol and data must be objects")
    fundamentals = data.get("fundamentals")
    return PorterCompanyFacts(
        company_name=data.get("name"),
        market={"a": "A-share", "hk": "HK", "us": "US", "etf": "ETF"}.get(str(symbol.get("market")), str(symbol.get("market") or "unknown")),
        currency=data.get("currency"),
        sector=data.get("sector"),
        industry=data.get("industry"),
        business_summary=data.get("description") or data.get("business_summary"),
        price=_number(data.get("price")),
        fundamentals=dict(fundamentals) if isinstance(fundamentals, Mapping) else {},
        upstream={
            "schema_version": version,
            "command": payload["command"],
            "status": payload["status"],
            "symbol": dict(symbol),
            "data_as_of": payload.get("data_as_of"),
            "sources": [dict(item) for item in payload.get("sources") or []],
            "gaps": [dict(item) for item in payload.get("gaps") or []],
            "notes": [str(item) for item in payload.get("notes") or []],
        },
    )


def _number(value: Any) -> float | None:
    if value is None or value is False:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
