#!/usr/bin/env python3
"""Read-only audit; performance requires a complete broker-derived CSV."""
import argparse
import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re


def portfolio_gaps(path):
    Path(path).read_text(encoding="utf-8")  # Verify the requested source is readable.
    return ["broker_statement_required", "historical_transaction_basis_missing",
            "historical_cash_flows_unverified", "historical_fx_and_fees_unverified"]


def portfolio_section(path):
    text = Path(path).read_text(encoding="utf-8")
    return text.split("## 当前持仓", 1)[1].split("\n## ", 1)[0]


def portfolio_cash(path):
    section = portfolio_section(path)
    cash = {}
    labels = {"港币": "HKD", "人民币": "CNY", "美元": "USD"}
    for label, currency in labels.items():
        match = re.search(rf"{label}现金：\*\*([\d,.]+)\s*(万)?\s*(?:HKD|CNY|USD)?\*\*", section)
        if match:
            cash[currency] = Decimal(match[1].replace(",", "")) * (Decimal(10000) if match[2] else Decimal(1))
    return cash


def portfolio_holdings(path):
    section = portfolio_section(path)
    holdings = {}
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        fields = [field.strip().replace("**", "") for field in line.strip("|").split("|")]
        if len(fields) >= 5 and fields[1] not in ("代码", "---", "—") and not set(fields[1]) <= {"-"}:
            quantity = fields[4].replace(",", "")
            if re.fullmatch(r"\d+(?:\.\d+)?", quantity):
                holdings[fields[1]] = quantity
    return holdings


FIELDS = ("date", "type", "symbol", "quantity", "price", "currency", "fee",
          "fee_currency", "cash_delta", "cash_currency", "fx_rate", "nav_cny",
          "external_flow_cny", "reference")
KINDS = {"OPEN_POSITION", "CLOSE_POSITION", "OPEN_CASH", "CLOSE_CASH", "BUY", "SELL",
         "DIVIDEND", "DEPOSIT", "WITHDRAWAL"}


def number(row, name, line):
    try:
        value = Decimal(row[name])
        if not value.is_finite():
            raise InvalidOperation
        return value
    except (InvalidOperation, KeyError):
        raise ValueError(f"row {line}: invalid or missing {name}") from None


def audit_statement(path, holdings=None, portfolio_balances=None):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    if not rows:
        raise ValueError("statement has no records")
    positions, cash = defaultdict(Decimal), defaultdict(Decimal)
    opening_positions, opening_cash = set(), set()
    closing_positions, closing_cash = {}, {}
    basis, attribution = {}, defaultdict(Decimal)
    gaps = []
    previous_date = None
    for line, row in enumerate(rows, 2):
        try:
            day = date.fromisoformat(row["date"])
        except (ValueError, TypeError):
            raise ValueError(f"row {line}: invalid date") from None
        if previous_date and day < previous_date:
            raise ValueError(f"row {line}: dates out of order")
        previous_date = day
        kind = row["type"]
        if kind not in KINDS:
            raise ValueError(f"row {line}: unsupported type {kind}")
        if not row["reference"].strip():
            raise ValueError(f"row {line}: missing reference")
        for key in ("currency", "fee_currency", "cash_currency"):
            if not row[key] or not re.fullmatch(r"[A-Z]{3}", row[key]):
                raise ValueError(f"row {line}: invalid {key}")
        qty, price, fee, delta, fx = (number(row, key, line) for key in
                                      ("quantity", "price", "fee", "cash_delta", "fx_rate"))
        if fee < 0 or fx <= 0:
            raise ValueError(f"row {line}: invalid fee or fx_rate")
        if kind != "BUY" and kind != "SELL" and fee != 0:
            raise ValueError(f"row {line}: non-trade fee requires separately documented event")
        nav = number(row, "nav_cny", line)
        flow = number(row, "external_flow_cny", line)
        if kind in ("DEPOSIT", "WITHDRAWAL") and flow != delta * fx:
            raise ValueError(f"row {line}: external_flow_cny must equal cash_delta * fx_rate")
        if kind not in ("DEPOSIT", "WITHDRAWAL") and flow != 0:
            raise ValueError(f"row {line}: non-external event cannot have external_flow_cny")
        if kind == "DEPOSIT" and delta <= 0 or kind == "WITHDRAWAL" and delta >= 0:
            raise ValueError(f"row {line}: invalid external cash_delta")
        if nav < 0:
            raise ValueError(f"row {line}: negative nav_cny")
        symbol, currency = row["symbol"], row["currency"]
        if kind in ("BUY", "SELL", "OPEN_POSITION", "CLOSE_POSITION") and (not symbol or qty <= 0 or price < 0):
            raise ValueError(f"row {line}: position requires symbol, positive quantity and price")
        if kind in ("BUY", "SELL"):
            if currency != row["cash_currency"] or currency != row["fee_currency"]:
                raise ValueError(f"row {line}: cross-currency trade requires explicit FX rows")
            expected = (-(qty * price) if kind == "BUY" else qty * price) - fee
            if delta != expected:
                raise ValueError(f"row {line}: cash_delta does not equal gross trade less fee")
            positions[symbol] += qty if kind == "BUY" else -qty
            cash[row["cash_currency"]] += delta
            attribution["fees"] -= fee * fx
            if kind == "BUY":
                basis[symbol] = basis.get(symbol, Decimal(0)) + qty * price * fx
            else:
                if symbol not in basis or positions[symbol] < 0:
                    gaps.append(f"opening_position_basis:{symbol}")
                else:
                    before = positions[symbol] + qty
                    cost = basis[symbol] * qty / before
                    attribution["price_and_fx_change"] += qty * price * fx - cost
                    basis[symbol] -= cost
        elif kind == "OPEN_POSITION":
            if symbol in opening_positions:
                raise ValueError(f"row {line}: duplicate opening position")
            opening_positions.add(symbol)
            positions[symbol] += qty
            basis[symbol] = qty * price * fx
        elif kind == "CLOSE_POSITION":
            if symbol in closing_positions:
                raise ValueError(f"row {line}: duplicate closing position")
            closing_positions[symbol] = (qty, price, fx)
        elif kind == "OPEN_CASH":
            if row["cash_currency"] in opening_cash:
                raise ValueError(f"row {line}: duplicate opening cash")
            opening_cash.add(row["cash_currency"])
            cash[row["cash_currency"]] += delta
        elif kind == "CLOSE_CASH":
            if row["cash_currency"] in closing_cash:
                raise ValueError(f"row {line}: duplicate closing cash")
            closing_cash[row["cash_currency"]] = delta
        else:
            cash[row["cash_currency"]] += delta
            if kind == "DIVIDEND":
                attribution["dividends"] += delta * fx
    for symbol in positions:
        if symbol not in opening_positions:
            gaps.append(f"opening_position_basis:{symbol}")
        if symbol not in closing_positions:
            gaps.append(f"closing_position:{symbol}")
    for currency in set(cash) | set(closing_cash):
        if currency not in opening_cash:
            gaps.append(f"opening_cash:{currency}")
        if currency not in closing_cash:
            gaps.append(f"closing_cash:{currency}")
    position_checks = {}
    for symbol, (quantity, price, fx) in closing_positions.items():
        reconstructed = positions[symbol]
        position_checks[symbol] = ("matched" if reconstructed == quantity else
                                   f"mismatch: expected {quantity}, reconstructed {reconstructed}")
        if reconstructed != quantity:
            gaps.append(f"position_mismatch:{symbol}")
        elif symbol in basis:
            attribution["price_and_fx_change"] += quantity * price * fx - basis[symbol]
    cash_checks = {}
    for currency, expected in closing_cash.items():
        reconstructed = cash[currency]
        cash_checks[currency] = ("matched" if reconstructed == expected else
                                 f"mismatch: expected {expected}, reconstructed {reconstructed}")
        if reconstructed != expected:
            gaps.append(f"cash_mismatch:{currency}")
    if holdings is not None:
        for symbol in closing_positions.keys() - holdings.keys():
            gaps.append(f"portfolio_unexpected_position:{symbol}")
        for symbol, quantity in holdings.items():
            if symbol not in closing_positions:
                gaps.append(f"portfolio_unreconciled:{symbol}")
            elif closing_positions[symbol][0] != Decimal(quantity):
                gaps.append(f"portfolio_mismatch:{symbol}")
    if portfolio_balances is not None:
        for currency in closing_cash.keys() - portfolio_balances.keys():
            gaps.append(f"portfolio_cash_unexpected:{currency}")
        for currency, balance in portfolio_balances.items():
            if currency not in closing_cash:
                gaps.append(f"portfolio_cash_unreconciled:{currency}")
            elif closing_cash[currency] != balance:
                gaps.append(f"portfolio_cash_mismatch:{currency}")
    synthetic = bool(rows) and all(row["reference"].startswith("SYNTHETIC-") for row in rows)
    result = {"status": "incomplete", "source": "synthetic_fixture" if synthetic else "user_supplied_csv_unverified",
              "gaps": sorted(set(gaps + ["synthetic_not_actual" if synthetic else "broker_provenance_unverified", "performance_not_established"])),
              "reconciliation": {"positions": position_checks, "cash": cash_checks}}
    if not gaps and opening_positions and closing_positions and opening_cash and closing_cash:
        result["attribution_cny"] = {k: str(attribution[k]) for k in
                                     ("price_and_fx_change", "fees", "dividends")}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio", type=Path, help="Read-only PORTFOLIO.md path")
    parser.add_argument("--statement", type=Path, help="Explicit transaction CSV, never inferred from portfolio notes")
    args = parser.parse_args()
    if not args.portfolio and not args.statement:
        parser.error("provide --portfolio and/or --statement")
    try:
        holdings = portfolio_holdings(args.portfolio) if args.portfolio else None
        result = audit_statement(args.statement, holdings, portfolio_cash(args.portfolio) if args.portfolio else None) if args.statement else {
            "status": "incomplete", "holdings": holdings,
            "cash": {k: str(v) for k, v in portfolio_cash(args.portfolio).items()},
            "gaps": portfolio_gaps(args.portfolio)}
    except (OSError, ValueError, IndexError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
