import copy
import json
import subprocess
import sys
import unittest
from dataclasses import asdict
from pathlib import Path

from test_readiness import snapshot
from valuation_report import generate_report_from_snapshot

ROOT = Path(__file__).resolve().parents[1]


def verified_input():
    return {
        'verified': True, 'method': 'normalized PE',
        'source': 'offline example, not market data', 'as_of': '2026-10-03',
        'rationale': 'normalized earnings and independently justified exit multiples',
        'currency': 'USD', 'years': 3,
        'auxiliary': {'method': 'asset value', 'verified': True, 'assessment': 'consistent',
                      'source': 'offline fixture', 'rationale': 'asset reconciliation'},
        'scenarios': {
            'conservative': {'value_per_share': 80, 'cash_distributions': 6, 'assumptions': 'weak demand'},
            'base': {'value_per_share': 120, 'cash_distributions': 6, 'assumptions': 'normal demand'},
            'optimistic': {'value_per_share': 150, 'cash_distributions': 6, 'assumptions': 'strong demand'},
        },
        'conclusion': '合理偏低',
    }


class PrimaryInputTest(unittest.TestCase):
    def test_verified_primary_exposes_scenario_returns_not_trade_mapping(self):
        report = generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', verified_input())
        self.assertEqual(report.valuation_status, 'ok')
        self.assertEqual(report.conclusion, '合理偏低')
        self.assertIsNone(report.action_reference)
        data = asdict(report)['primary_valuation']
        self.assertEqual(data['scenarios']['base']['total_return_pct'], 26)
        self.assertAlmostEqual(data['scenarios']['base']['annualized_return_pct'], ((1.26 ** (1 / 3)) - 1) * 100)
        self.assertAlmostEqual(data['scenarios']['conservative']['margin_of_safety_pct'], -25)

    def test_invalid_primary_and_failure_never_rate(self):
        cases = []
        for key, value in [('verified', False), ('years', 0), ('years', float('nan')), ('currency', 'HKD'), ('source', ''), ('method', 'PEG')]:
            item = verified_input()
            item[key] = value
            cases.append(item)
        for key, value in [('assessment', 'conflict'), ('method', 'PEG'), ('verified', False)]:
            item = verified_input()
            item['auxiliary'][key] = value
            cases.append(item)
        for value in [-1, float('inf')]:
            item = verified_input()
            item['scenarios']['base']['value_per_share'] = value
            cases.append(item)
        for item in cases:
            with self.subTest(item=item):
                report = generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', item)
                self.assertIsNone(report.conclusion)
                self.assertIsNone(report.action_reference)
        failed = generate_report_from_snapshot(snapshot({'current_price': 100}, upstream='failed'), 'auto', verified_input())
        self.assertEqual(failed.valuation_status, 'upstream_failed')
        self.assertIsNone(failed.conclusion)
        partial = generate_report_from_snapshot(snapshot({'current_price': 100}, upstream='partial'), 'auto', verified_input())
        self.assertEqual(partial.valuation_status, 'partial')
        self.assertIsNone(partial.action_reference)

    def test_cli_input_errors_are_explicit_without_traceback(self):
        for path in [ROOT / 'examples' / 'missing.json', ROOT / 'SKILL.md']:
            proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'valuation_report.py'), 'TEST',
                                   '--snapshot-input', str(path)], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 2)
            self.assertIn('输入错误', proc.stderr)
            self.assertNotIn('Traceback', proc.stderr)

    def test_machine_policy_disables_voting_and_fixed_margin(self):
        policy = json.loads((ROOT / 'scripts' / 'scoring_rules.json').read_text())['policy']
        self.assertFalse(policy['metric_voting'])
        self.assertFalse(policy['automatic_action'])
        self.assertEqual(policy['safety_margin'], 'scenario_review')
        self.assertIsNone(policy['fixed_cyclical_discount'])
        self.assertIsNone(policy['mandatory_peak_multiplier'])

    def test_background_metrics_do_not_break_comparison_ties(self):
        from valuation_compare import build_row, sort_rows
        a = build_row(generate_report_from_snapshot(snapshot({'trailing_pe': 12, 'price_percentile_5y_proxy': 90}), 'auto'), {})
        b = build_row(generate_report_from_snapshot(snapshot({'trailing_pe': 12, 'price_percentile_5y_proxy': 1}), 'auto'), {})
        self.assertEqual(sort_rows([a, b]), [a, b])

    def test_offline_cli_reviewed_and_diagnostic_paths(self):
        fixture = ROOT / 'examples' / 'offline-snapshot.json'
        primary = ROOT / 'examples' / 'reviewed-primary.json'
        for options, conclusion in [([], None), (['--primary-input', str(primary)], '合理偏低')]:
            proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'valuation_report.py'), 'TEST',
                                   '--snapshot-input', str(fixture), '--output', 'json', *options],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result['conclusion'], conclusion)
            self.assertIsNone(result['action_reference'])
        proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'valuation_report.py'), 'TEST',
                               '--snapshot-input', str(fixture), '--primary-input', str(primary), '--output', 'markdown'],
                              capture_output=True, text=True)
        self.assertIn('保守', proc.stdout)
        self.assertIn('26.00%', proc.stdout)


if __name__ == '__main__':
    unittest.main()
