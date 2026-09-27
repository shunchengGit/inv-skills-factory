#!/usr/bin/env python3
"""Read-only weekly decision audit; fails closed on absent inputs and obsolete rules."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path.home() / '.hermes' / 'memories'


def _cap(user, key):
    found = re.search(rf'{key}[^\n]*?[<≤]\s*=?\s*(\d+(?:\.\d+)?)\s*%', user)
    return float(found.group(1)) if found else None


def _held_symbols(portfolio):
    section = portfolio.split('## 当前持仓', 1)[1].split('\n## ', 1)[0]
    held = set()
    for line in section.splitlines():
        if not line.startswith('|'):
            continue
        cells = [x.strip().replace('**', '') for x in line.strip('|').split('|')]
        if len(cells) > 1 and cells[0] not in ('标的', '现金') and re.fullmatch(r'[A-Za-z0-9.]+', cells[1]):
            held.add(cells[1])
    return held


def check(user_path, portfolio_path, audit_path, review_path):
    checks = dict.fromkeys(('rules_current', 'portfolio_present', 'holding_coverage', 'ledger_integrity', 'research_ready', 'weekly_artifact'), False)
    blockers = []
    unresolved = []
    held = set()
    missing_holdings = []
    try:
        user = Path(user_path).read_text(encoding='utf-8')
        single, sector = _cap(user, '单只股票仓位上限'), _cap(user, '单一行业集中度')
        cash_record_only = bool(re.search(r'现金[^\n]*(?:只记账|不作否决|不作为.*门槛)', user))
        if single is None or sector is None or not cash_record_only:
            blockers.append('user_rules_unparseable')
    except (OSError, UnicodeError):
        single = sector = None
        cash_record_only = False
        blockers.append('user_rules_missing')
    try:
        portfolio = Path(portfolio_path).read_text(encoding='utf-8')
        checks['portfolio_present'] = '## 当前持仓' in portfolio and '| 现金 |' in portfolio
        if checks['portfolio_present']:
            held = _held_symbols(portfolio)
            checks['portfolio_present'] = bool(held)
        if not checks['portfolio_present']:
            blockers.append('portfolio_unparseable')
    except (OSError, UnicodeError):
        blockers.append('portfolio_missing')
    try:
        audit = json.loads(Path(audit_path).read_text(encoding='utf-8'))
        rows = audit['rows']
        checks['ledger_integrity'] = audit.get('integrity') == 'ok' and len(rows) == audit.get('coverage') and bool(rows)
        if not checks['ledger_integrity']:
            blockers.append('ledger_integrity_failed')
        ledger_symbols = {row['symbol'] for row in rows}
        missing_holdings = sorted(held - ledger_symbols)
        checks['holding_coverage'] = checks['ledger_integrity'] and bool(held) and not missing_holdings
        if missing_holdings:
            blockers.append('holding_coverage_incomplete')
        unresolved = sorted(set(missing_holdings) | {row['symbol'] for row in rows if row.get('status') != 'decision_ready' or row.get('gaps')})
        checks['research_ready'] = checks['holding_coverage'] and not unresolved
    except (OSError, ValueError, KeyError, TypeError):
        blockers.append('ledger_audit_missing_or_invalid')
    try:
        review = Path(review_path).read_text(encoding='utf-8')
        checks['weekly_artifact'] = bool(review.strip())
        if not checks['weekly_artifact']:
            blockers.append('weekly_artifact_empty')
        elif held and not all(code in review for code in held):
            checks['weekly_artifact'] = False
            blockers.append('review_missing_holdings')
        # Only active prescriptions are checked; archive/history is evidence, not authorization.
        active = '\n'.join(line for line in review.splitlines() if not re.search(r'旧规|作废|撤销|暂停使用|已失效|不再生效', line))
        stale_cash = bool(re.search(r'现金\s*[<＜]\s*\d+\s*%[^\n]*(?:停止|禁止|暂停|不开|不买|限制|闸门|生效)|现金\s*[≥>]\s*\d+\s*%', active))
        stale_price = bool(re.search(r'(?:触价|到价|跌至)[^\n]*(?:立即|直接|自动)[^\n]*(?:加仓|买入)|(?:触发条件清单)[^\n]*(?:未触发|已触发)', active))
        values = [(_cap(active, '单只上限') or _cap(active, '单只股票仓位上限'), single),
                  (_cap(active, '行业上限') or _cap(active, '单一行业集中度'), sector)]
        stale_caps = any(a is not None and b is not None and a != b for a, b in values)
        checks['rules_current'] = single is not None and sector is not None and cash_record_only and not (stale_cash or stale_price or stale_caps)
        if stale_cash or stale_price or stale_caps:
            blockers.append('obsolete_action_rule')
    except (OSError, UnicodeError):
        blockers.append('weekly_artifact_missing')
    return {'checks': checks, 'blockers': blockers, 'unresolved': unresolved,
            'missing_holdings': missing_holdings, 'rule_source': str(user_path),
            'research_authorized': all(checks.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', type=Path, default=BASE/'USER.md')
    parser.add_argument('--portfolio', type=Path, default=BASE/'PORTFOLIO.md')
    parser.add_argument('--review', type=Path, required=True, help='weekly report to validate')
    parser.add_argument('--audit', type=Path, help='existing read-only decision_ledger audit JSON (otherwise generated via CLI)')
    args = parser.parse_args()
    if args.audit:
        result = check(args.user, args.portfolio, args.audit, args.review)
    else:
        script = Path(__file__).resolve().parent/'decision_ledger.py'
        try:
            cp = subprocess.run([sys.executable, '-B', str(script), 'audit'], capture_output=True, text=True, timeout=30, check=True)
            import tempfile
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/'audit.json'
                path.write_text(cp.stdout, encoding='utf-8')
                result = check(args.user, args.portfolio, path, args.review)
        except (subprocess.SubprocessError, OSError):
            result = {'checks': {'ledger_integrity': False}, 'blockers': ['ledger_audit_unavailable'], 'unresolved': [], 'research_authorized': False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if all(result['checks'].get(key) for key in ('rules_current', 'portfolio_present', 'holding_coverage', 'ledger_integrity', 'weekly_artifact')) else 2


if __name__ == '__main__':
    raise SystemExit(main())
