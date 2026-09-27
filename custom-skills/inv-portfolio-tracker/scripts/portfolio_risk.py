"""Read-only portfolio joint-risk audit. No market data or database writes."""

import argparse
from datetime import date
import json
import math
from pathlib import Path
import re


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def parse_portfolio(text):
    """Read the current-holdings section only; percentages are authoritative."""
    match = re.search(r"(?m)^## 当前持仓\s*$([\s\S]*?)(?=^## |\Z)", text)
    if not match:
        raise ValueError("missing current holdings section")
    section = match.group(1)
    stamp = re.search(r"估值生成时间[^\n]*?(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", section)
    if not stamp:
        raise ValueError("missing snapshot timestamp")
    weights, etfs = {}, {}
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        columns = [c.strip().replace("**", "") for c in line.strip().strip("|").split("|")]
        if len(columns) != 13 or columns[1] in ("代码", "------") or set(columns[1]) == {"-"}:
            continue
        code = "CASH" if columns[0] == "现金" else columns[1]
        if code in weights:
            raise ValueError(f"duplicate position: {code}")
        if not re.fullmatch(r"\d+(?:\.\d+)?%", columns[8]):
            raise ValueError(f"invalid weight for {code}")
        weights[code] = float(columns[8][:-1])
        if "ETF" in columns[0] or "ETF" in columns[3].upper():
            etfs[code] = weights[code]
    if not weights or "CASH" not in weights:
        raise ValueError("missing holdings or cash")
    total = round(sum(weights.values()), 4)
    if abs(total - 100) > 0.5:
        raise ValueError(f"weights do not reconcile to 100%: {total}")
    return {"snapshot": stamp.group(1), "weights": weights, "total_weight": total, "etfs": etfs}


def joint_exposure(portfolio, mapping):
    """Manual fractional factor allocations, not statistical correlations or betas."""
    weights = portfolio["weights"]
    if set(mapping) - (set(weights) - {"CASH"}):
        raise ValueError("mapping contains unheld security")
    factors, unknown, by_asset = {}, {}, {}
    for code, weight in weights.items():
        if code == "CASH":
            continue
        allocations = mapping.get(code, {})
        if any(not isinstance(x, (int, float)) or not 0 <= x <= 1 for x in allocations.values()) or sum(allocations.values()) > 1 + 1e-9:
            raise ValueError(f"invalid factor allocations: {code}")
        by_asset[code] = {factor: weight * fraction for factor, fraction in allocations.items()}
        for factor, exposure in by_asset[code].items():
            factors[factor] = factors.get(factor, 0) + exposure
        remainder = weight * (1 - sum(allocations.values()))
        if remainder > 1e-9:
            unknown[code] = remainder
    overlaps = {}
    codes = sorted(by_asset)
    for index, code in enumerate(codes):
        for other in codes[index + 1:]:
            common = by_asset[code].keys() & by_asset[other].keys()
            if common:
                overlaps[f"{code}|{other}"] = sum(min(by_asset[code][f], by_asset[other][f]) for f in common)
    return {"factors": factors, "unknown": unknown, "pair_overlap": overlaps,
            "etf_lookthrough_unknown": portfolio.get("etfs", {}),
            "classification": "manual scenario mapping; not proven beta/correlation"}


def scenario_impact(portfolio, name, horizon, assumptions):
    """Compute percentage-point impact only if every asset (including ETF/cash) is covered."""
    weights = portfolio["weights"]
    if not name or not horizon:
        raise ValueError("scenario name and horizon required")
    if set(assumptions) - set(weights):
        raise ValueError("scenario contains unheld security")
    missing = [code for code in weights if code not in assumptions or
               not _finite(assumptions[code].get("return_pct")) or
               not str(assumptions[code].get("evidence", "")).strip()]
    result = {"name": name, "horizon": horizon, "missing": missing,
              "portfolio_impact_pct": None, "contributions_pct": None,
              "status": "incomplete assumptions" if missing else "hypothetical, not forecast"}
    if not missing:
        contributions = {code: weight * assumptions[code]["return_pct"] / 100
                         for code, weight in weights.items()}
        result.update(contributions_pct=contributions,
                      portfolio_impact_pct=sum(contributions.values()))
    return result


def compare_opportunities(options):
    """Net-return ordering is conditional, not a recommendation or risk-adjusted score."""
    fields = ("name", "horizon", "asof_date", "evidence_gate", "expected_return_pct", "downside_pct", "cost_pct", "evidence")
    missing = []
    if len(options) < 2:
        missing.append("at least two alternatives")
    for index, option in enumerate(options):
        missing.extend(f"option[{index}].{field}" for field in fields
                       if field not in option or option[field] is None or
                       (field in ("name", "horizon", "asof_date", "evidence_gate", "evidence") and not str(option[field]).strip()) or
                       (field in ("expected_return_pct", "downside_pct", "cost_pct") and not _finite(option[field])))
    if not missing and len({option["horizon"] for option in options}) != 1:
        missing.append("same horizon")
    if not missing:
        try:
            dates = [date.fromisoformat(option["asof_date"]) for option in options]
            if any(day.isoformat() != option["asof_date"] for day, option in zip(dates, options)):
                raise ValueError("noncanonical date")
        except (ValueError, TypeError):
            missing.append("valid asof_date")
        if len({option["asof_date"] for option in options}) != 1:
            missing.append("same asof_date")
        for index, option in enumerate(options):
            if option["evidence_gate"] != "passed":
                missing.append(f"option[{index}] evidence_gate not passed")
    if not missing and len({option["name"] for option in options}) != len(options):
        missing.append("unique option names")
    if not missing:
        for index, option in enumerate(options):
            if option["cost_pct"] < 0 or option["downside_pct"] > 0:
                missing.append(f"option[{index}] invalid cost/downside")
    if missing:
        return {"ranking": None, "missing": missing, "status": "unranked: incomplete or incomparable"}
    ranking = sorted(({**option, "net_return_pct": option["expected_return_pct"] - option["cost_pct"]}
                      for option in options), key=lambda item: item["net_return_pct"], reverse=True)
    return {"ranking": ranking, "missing": [], "status": "conditional net-return ranking; assumptions not independently verified"}


def main():
    """Audit a local snapshot with optional explicit, user-supplied JSON assumptions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio", type=Path, default=Path.home() / ".hermes/memories/PORTFOLIO.md")
    parser.add_argument("--assumptions", type=Path, help="JSON: exposures, scenario, opportunities; never inferred")
    args = parser.parse_args()
    portfolio = parse_portfolio(args.portfolio.read_text(encoding="utf-8"))
    config = json.loads(args.assumptions.read_text(encoding="utf-8")) if args.assumptions else {}
    exposure = joint_exposure(portfolio, config.get("exposures", {}))
    scenario = config.get("scenario", {})
    impact = (scenario_impact(portfolio, scenario["name"], scenario["horizon"], scenario.get("assumptions", {}))
              if scenario.get("name") and scenario.get("horizon") else
              {"portfolio_impact_pct": None, "status": "unassessed: no scenario horizon and assumptions"})
    comparison = compare_opportunities(config.get("opportunities", []))
    print(json.dumps({"portfolio": portfolio, "joint_exposure": exposure, "scenario": impact,
                      "comparison": comparison}, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
