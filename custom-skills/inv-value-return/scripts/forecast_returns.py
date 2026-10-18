#!/usr/bin/env python3
"""Offline, deterministic annual scenario returns; no investment recommendation."""
import math
from datetime import date
import json
import argparse
from pathlib import Path

REQUIRED_SCENARIOS = ('pessimistic', 'base', 'optimistic')
OPTIONAL_SCENARIOS = ('no_rerating',)
TOLERANCE = 1e-12


def main(argv=None):
    """Read only the explicitly supplied JSON input, emit the result to stdout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Input JSON file path')
    parser.add_argument('--output', choices=('json', 'text'), default='json')
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.input).read_text(encoding='utf-8'))
        result = forecast(data)
        output = (json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
                  if args.output == 'json' else render_text(result))
    except (ValueError, OSError, OverflowError, ZeroDivisionError) as exc:
        parser.error(str(exc))
    print(output)
    return 0


def pct(value):
    return 'n/a' if value is None else f'{value:.1%}'


def pp(value):
    return 'n/a' if value is None else f'{value * 100:+.1f}pp'


def money(value):
    return 'n/a' if value is None else f'{value:.2f}'


def render_text(result):
    """Render scenario comparisons, assumptions and unverified provenance."""
    low, high = result['target_cagr_range']
    lines = [f"inv-value-return | {result['as_of']} | {result['currency']} | {result['years']} years",
             f"initial_cost={money(result['initial_cost'])}; target_cagr_range={pct(low)}~{pct(high)}",
             f"fees_and_tax={result['fees_and_tax']}"]
    lines.extend(result['notes'])
    for scenario in result['scenarios']:
        buffers = scenario['target_buffers']
        prices = scenario['max_buy_prices_for_target']
        lines.append(f"{scenario['name']}: IRR={pct(scenario['annual_irr'])}; "
                     f"terminal collected CAGR (non-IRR)={pct(scenario['terminal_collected_cagr_non_irr'])}; "
                     f"{scenario['target_comparison']} (vs low {pp(buffers[0])}, vs high {pp(buffers[1])})")
        lines.append('  annual_net_cash_flows=[' + ', '.join(money(c) for c in scenario['annual_net_cash_flows']) + ']')
        lines.append(f"  max_buy_prices_for_target: low={money(prices[0])}, high={money(prices[1])}")
        lines.append('  terminal_bridge (unverified): ' + json.dumps(scenario['terminal_bridge'], ensure_ascii=False))
    floor = result['pessimistic_floor']
    if floor['rate'] is None:
        lines.append('pessimistic_floor: not provided, not certified')
    else:
        lines.append(f"pessimistic_floor={pct(floor['rate'])} ({floor['basis'] or 'basis not stated'}); "
                     f"buffer={pp(floor['irr_buffer'])}; max_buy_price={money(floor['max_buy_price'])}; "
                     f"pass={floor['pass']}")
    return '\n'.join(lines)


def number(value, label, minimum=None, maximum=None, exclusive=False):
    """Require a finite JSON number, never a boolean."""
    if type(value) not in (int, float):
        raise ValueError(label + ' must be a finite number')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (minimum is not None and (value <= minimum if exclusive else value < minimum)) or (maximum is not None and value > maximum):
        raise ValueError(label + ' outside allowed range')
    return value


def validate(data):
    """Validate the annual, single-currency input contract without mutation."""
    if not isinstance(data, dict):
        raise ValueError('input must be an object')
    try:
        json.dumps(data, allow_nan=False)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('input must contain only finite JSON values') from exc
    if 'annual_rf_after_tax' in data:
        raise ValueError('annual_rf_after_tax was replaced by pessimistic_floor_rate/pessimistic_floor_basis')
    years = data.get('years')
    if type(years) is not int or years <= 0:
        raise ValueError('years must be a positive integer')
    number(data.get('current_price'), 'current_price', 0, exclusive=True)
    if not isinstance(data.get('currency'), str) or not data['currency'].strip():
        raise ValueError('currency is required')
    stamp = data.get('as_of')
    if not isinstance(stamp, str) or len(stamp) != 10:
        raise ValueError('as_of must be YYYY-MM-DD')
    try:
        if date.fromisoformat(stamp).isoformat() != stamp:
            raise ValueError('as_of must be YYYY-MM-DD')
    except ValueError as exc:
        raise ValueError('as_of must be a valid YYYY-MM-DD') from exc
    for key in ('buy_fee_rate', 'exit_fee_rate', 'dividend_tax_rate'):
        number(data.get(key, 0), key, 0, 1)
    targets = data.get('target_cagr_range')
    if not isinstance(targets, list) or len(targets) != 2:
        raise ValueError('target_cagr_range requires [low, high]')
    for target in targets:
        number(target, 'target_cagr_range', -1, exclusive=True)
    if targets[0] > targets[1]:
        raise ValueError('target_cagr_range must be ordered')
    if data.get('pessimistic_floor_rate') is not None:
        number(data['pessimistic_floor_rate'], 'pessimistic_floor_rate', -1, exclusive=True)
    basis = data.get('pessimistic_floor_basis')
    if basis is not None and not isinstance(basis, str):
        raise ValueError('pessimistic_floor_basis must be a string')
    scenarios = data.get('scenarios')
    if not isinstance(scenarios, list) or len(scenarios) not in (3, 4):
        raise ValueError('pessimistic/base/optimistic scenarios required, plus optional no_rerating')
    names = []
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(scenario.get('name'), str):
            raise ValueError('scenario name required')
        names.append(scenario['name'])
        number(scenario.get('terminal_price'), 'terminal_price', 0)
        dividends = scenario.get('dividends')
        if not isinstance(dividends, list) or len(dividends) != years:
            raise ValueError('dividends length must equal years')
        for dividend in dividends:
            number(dividend, 'dividend', 0)
        if 'terminal_bridge' in scenario and not isinstance(scenario['terminal_bridge'], dict):
            raise ValueError('terminal_bridge must be an object')
    if (len(set(names)) != len(names) or not set(REQUIRED_SCENARIOS) <= set(names)
            or not set(names) <= set(REQUIRED_SCENARIOS + OPTIONAL_SCENARIOS)):
        raise ValueError('unique pessimistic/base/optimistic scenarios required, plus optional no_rerating')


def present_value(cash, rate, buy):
    """Highest quote whose fee-inclusive cost equals cash discounted at rate."""
    return sum(c/(1+rate)**t for t, c in enumerate(cash, 1))/(1+buy)


def at_least(value, threshold):
    return value > threshold or math.isclose(value, threshold, abs_tol=TOLERANCE, rel_tol=TOLERANCE)


def forecast(data):
    """Compute per-share cash flows and price ceilings from explicit assumptions."""
    validate(data)
    years = data['years']
    buy = data.get('buy_fee_rate', 0)
    sell = data.get('exit_fee_rate', 0)
    tax = data.get('dividend_tax_rate', 0)
    cost = data['current_price'] * (1 + buy)
    targets = data['target_cagr_range']
    floor_rate = data.get('pessimistic_floor_rate')
    floor = {'rate': floor_rate, 'basis': data.get('pessimistic_floor_basis'),
             'max_buy_price': None, 'irr_buffer': None, 'pass': None}
    scenarios = []
    for scenario in data['scenarios']:
        cash = [d * (1-tax) for d in scenario['dividends']]
        cash[-1] += scenario['terminal_price'] * (1-sell)
        irr = annual_irr(cost, cash)
        if scenario['name'] == 'pessimistic' and floor_rate is not None:
            floor.update(max_buy_price=present_value(cash, floor_rate, buy),
                         irr_buffer=irr - floor_rate, **{'pass': at_least(irr, floor_rate)})
        scenarios.append({
            'name': scenario['name'], 'annual_net_cash_flows': cash,
            'terminal_price': scenario['terminal_price'],
            'terminal_bridge': scenario.get('terminal_bridge'),
            'annual_irr': irr,
            'terminal_collected_cagr_non_irr': (sum(cash)/cost)**(1/years)-1,
            'max_buy_prices_for_target': [present_value(cash, r, buy) for r in targets],
            'target_buffers': [irr - r for r in targets],
            'target_comparison': ('below_range' if not at_least(irr, targets[0]) else
                                  'above_range' if not at_least(targets[1], irr) else 'within_range'),
        })
    return {'skill': 'inv-value-return', 'currency': data['currency'],
            'as_of': data['as_of'], 'years': years,
            'target_cagr_range': targets,
            'fees_and_tax': {'buy_fee_rate': buy, 'exit_fee_rate': sell, 'dividend_tax_rate': tax},
            'notes': ['税费未核：省略的税费比例显式按0计算；已给比例亦未独立核验。',
                      'Year-end annual cash-flow IRR; not calendar-date XIRR.',
                      'Terminal collected CAGR is non-IRR: dividends held without reinvestment.',
                      'Single currency per share; prepare FX/ADR/unit conversions externally.',
                      'Buffers are IRR minus target/floor in return points, not valuation margin of safety.',
                      'No probabilities, parameter fitting or trade recommendations.'],
            'initial_cost': cost, 'scenarios': scenarios,
            'pessimistic_floor': floor}


def annual_irr(initial_cost, annual_cash):
    """Solve -cost + sum(cash[t]/(1+r)**t) = 0, cash at year ends.

    Nonnegative future cash ensures a unique root; no recovery is exactly -100%.
    Log-growth bisection avoids discount-power overflow near total loss.
    """
    number(initial_cost, 'initial_cost', 0, exclusive=True)
    if not isinstance(annual_cash, (list, tuple)) or not annual_cash:
        raise ValueError('annual_cash must be a nonempty sequence')
    for cash in annual_cash:
        number(cash, 'annual_cash', 0)
    terms = [(t, math.log(c)) for t, c in enumerate(annual_cash, 1) if c > 0]
    if not terms:
        return -1.0
    log_cost = math.log(initial_cost)

    def residual(x):
        logs = [log_c - t * x for t, log_c in terms]
        peak = max(logs)
        return peak + math.log(sum(math.exp(v - peak) for v in logs)) - log_cost

    low, high = -1.0, 1.0
    while residual(low) < 0:
        low *= 2
    while residual(high) > 0:
        high *= 2
    for _ in range(200):
        x = (low + high) / 2
        if residual(x) > 0:
            low = x
        else:
            high = x
        if high - low < 1e-14:
            break
    return math.expm1((low + high) / 2)


if __name__ == '__main__':
    raise SystemExit(main())
