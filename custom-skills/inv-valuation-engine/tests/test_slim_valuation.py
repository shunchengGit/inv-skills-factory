import unittest
from test_readiness import snapshot
from test_primary_input import verified_input
from valuation_report import generate_report_from_snapshot, render_text, render_markdown


class SlimValuationTest(unittest.TestCase):
    def test_missing_diagnostic_metrics_are_background_not_core(self):
        from unittest.mock import patch
        from valuation_snapshot import build_snapshot
        def fetch(command, symbol, **kwargs):
            return {'schema_version': '1.0', 'command': 'all', 'status': 'ok', 'symbol': {'market': 'us'}, 'data_as_of': '2026-10-03', 'sources': [], 'gaps': [], 'notes': [], 'data': {'components': {n: {'status': 'ok', 'data': {'price': 100, 'currency': 'USD'} if n == 'snapshot' else {}, 'gaps': []} for n in ('snapshot', 'financial', 'financials')}}}
        with patch('valuation_snapshot._call_cs_stock', side_effect=fetch):
            result = build_snapshot('TEST')
        self.assertEqual(result.upstream_status, 'ok')
        self.assertTrue(all(g.get('scope') == 'background' for g in result.data_gaps))
        self.assertEqual(generate_report_from_snapshot(result, 'auto', verified_input()).valuation_status, 'ok')


    def test_compare_cli_accepts_offline_bundle(self):
        import json, tempfile, subprocess, sys
        from dataclasses import asdict
        from pathlib import Path
        bundle = {'snapshots': {'TEST': asdict(snapshot({'current_price': 100}))}, 'primary_inputs': {'TEST': verified_input()}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
            json.dump(bundle, f); f.flush()
            proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/valuation_compare.py'), 'TEST', '--input', f.name, '--output', 'json'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['rows'][0]['primary_valuation']['scenarios']['base']['total_return_pct'], 26)


    def test_compare_accepts_reviewed_primary_inputs_without_rating(self):
        from valuation_compare import generate_compare, render_text as compare_text, render_markdown as compare_md
        primary = verified_input()
        primary.pop('conclusion')
        result = generate_compare(['TEST'], 'auto', snapshots={'TEST': snapshot({'current_price': 100})}, primary_inputs={'TEST': primary})
        row = result.rows[0]
        self.assertEqual(row['primary_valuation']['method'], 'normalized PE')
        self.assertEqual(row['primary_valuation']['scenarios']['base']['total_return_pct'], 26)
        self.assertIn('不自动排序', ' '.join(result.ranking_summary))
        for render in (compare_text, compare_md):
            self.assertIn('保守', render(result))
            self.assertIn('26.00%', render(result))
            self.assertNotIn('不可评级', render(result))


    def test_explicit_background_failure_remains_visible_without_core_failure(self):
        from unittest.mock import patch
        from valuation_snapshot import build_snapshot
        def fetch(command, symbol, **kwargs):
            data = {'components': {n: {'status': 'ok', 'data': {'price': 100, 'currency': 'USD', 'fundamentals': {k: 10 for k in ('pe_trailing', 'pe_forward', 'pb', 'revenue_growth_pct', 'earnings_growth_pct')}} if n == 'snapshot' else {}, 'gaps': []} for n in ('snapshot', 'financial', 'financials')}} if command == 'all' else {}
            return {'schema_version': '1.0', 'command': command, 'status': 'ok' if command == 'all' else 'failed', 'symbol': {'market': 'us'}, 'data_as_of': '2026-10-03', 'sources': [], 'gaps': [] if command == 'all' else [{'code': 'provider_unavailable', 'field': 'data', 'reason': 'offline failure', 'retryable': True}], 'notes': [], 'data': data}
        with patch('valuation_snapshot._call_cs_stock', side_effect=fetch) as call:
            result = build_snapshot('TEST', history_period='1y')
        self.assertEqual([c.args[0] for c in call.call_args_list], ['all', 'daily'])
        self.assertEqual(call.call_args_list[-1].kwargs['period'], '1y')
        self.assertEqual(result.upstream_status, 'ok')
        self.assertTrue(result.data_gaps)
        self.assertTrue(all(g['scope'] == 'background' for g in result.data_gaps))
        self.assertEqual(generate_report_from_snapshot(result, 'auto', verified_input()).valuation_status, 'ok')


    def test_compare_preserves_input_order_not_rating_order(self):
        from valuation_compare import build_row, sort_rows, build_summary
        rows = []
        for label in ('高估', '低估'):
            primary = verified_input()
            primary['conclusion'] = label
            rows.append(build_row(generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', primary), {}))
        self.assertEqual(sort_rows(rows), rows)
        self.assertFalse(any('更便宜' in x or '更不便宜' in x for x in build_summary(rows)))


    def test_background_gap_does_not_block_reviewed_primary(self):
        g = {'code': 'window_too_short', 'field': 'window', 'reason': 'background only', 'retryable': False, 'scope': 'background'}
        report = generate_report_from_snapshot(snapshot({'current_price': 100}, gaps=[g]), 'auto', verified_input())
        self.assertEqual(report.valuation_status, 'ok')
        self.assertEqual(report.data_gaps[0]['scope'], 'background')
        self.assertIn('[background]', render_text(report))


    def test_standard_leverage_fields_are_not_interchanged(self):
        from unittest.mock import patch
        from valuation_snapshot import build_snapshot
        def fetch(command, symbol, **kwargs):
            data = {'price': 100, 'currency': 'CNY', 'financial': {'资产负债率': 99}, 'fundamentals': {'debt_to_asset_pct': 40, 'debt_to_equity': 150}}
            return {'schema_version': '1.0', 'command': 'all', 'status': 'ok', 'symbol': {'market': 'a'}, 'data_as_of': '2026-10-03', 'sources': [], 'gaps': [], 'notes': [], 'data': {'components': {n: {'status': 'ok', 'data': data if n == 'snapshot' else {}, 'gaps': []} for n in ('snapshot', 'financial', 'financials')}}}
        with patch('valuation_snapshot._call_cs_stock', side_effect=fetch):
            a = build_snapshot('600519')
            y = build_snapshot('TEST')
        self.assertEqual(a.metrics['debt_to_asset_pct'], 40)
        self.assertIsNone(a.metrics.get('debt_to_equity'))
        self.assertEqual(y.metrics['debt_to_equity'], 150)
        from valuation_report import build_risks
        self.assertFalse(any('杠杆不低' in r for r in build_risks({'debt_to_equity': 1.5})))
        self.assertTrue(any('杠杆不低' in r for r in build_risks({'debt_to_equity': 150})))


    def test_cli_background_requests_are_explicit(self):
        from unittest.mock import patch
        from valuation_snapshot import parse_args
        with patch('sys.argv', ['valuation_snapshot', '600519', '--history-period', '1y', '--include-announcements', '--include-relations']):
            args = parse_args()
        self.assertEqual(args.history_period, '1y')
        self.assertTrue(args.include_announcements)
        self.assertTrue(args.include_relations)


    def test_snapshot_default_requests_only_core_components(self):
        from unittest.mock import patch
        from valuation_snapshot import build_snapshot
        def fetch(command, symbol, **kwargs):
            data = {'components': {name: {'status': 'ok', 'data': {'price': 100, 'currency': 'USD', 'fundamentals': {}} if name == 'snapshot' else {}, 'gaps': []} for name in ('snapshot', 'financial', 'financials')}} if command == 'all' else {}
            return {'schema_version': '1.0', 'command': command, 'status': 'ok', 'symbol': {'market': 'us'}, 'data_as_of': '2026-10-03', 'sources': [], 'gaps': [], 'notes': [], 'data': data}
        for symbol in ('TEST', '600519'):
            with patch('valuation_snapshot._call_cs_stock', side_effect=fetch) as call:
                result = build_snapshot(symbol)
            self.assertEqual([c.args[0] for c in call.call_args_list], ['all'])
            self.assertIsNone(result.history_window)
            self.assertFalse(any(g.get('field') == 'window' for g in result.data_gaps))


    def test_terminal_discount_has_correct_name_and_legacy_read(self):
        report = generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', verified_input())
        base = report.primary_valuation['scenarios']['base']
        self.assertAlmostEqual(base['terminal_value_discount_pct'], (1-100/120)*100)
        self.assertNotIn('margin_of_safety_pct', base)
        base['margin_of_safety_pct'] = base.pop('terminal_value_discount_pct')
        self.assertIn('终值折让=16.67%', render_text(report))


    def test_empty_action_is_separation_not_failed_gate(self):
        for primary in (None, verified_input()):
            report = generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', primary)
            for render in (render_text, render_markdown):
                self.assertNotIn('估值闸门未通过', render(report))
                self.assertIn('资本配置交由QARP', render(report))


    def test_confidence_is_not_inferred_from_diagnostic_ratings(self):
        report = generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', verified_input())
        self.assertEqual(report.confidence, '未评定（程序不认证研究置信度）')


    def test_explained_auxiliary_disagreement_is_preserved(self):
        primary = verified_input()
        primary['auxiliary'].update(assessment='conflict', explanation='Asset value omits franchise earnings; retain earnings model with downside risk.')
        report = generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', primary)
        self.assertIsNotNone(report.primary_valuation)
        self.assertIn('Asset value omits', render_text(report))
        primary['auxiliary'].pop('explanation')
        self.assertIsNone(generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', primary).primary_valuation)

    def test_reviewed_primary_does_not_require_display_rating(self):
        primary = verified_input()
        primary.pop('conclusion')
        report = generate_report_from_snapshot(snapshot({'current_price': 100}), 'auto', primary)
        self.assertEqual(report.valuation_status, 'ok')
        self.assertIsNone(report.conclusion)
        self.assertIsNotNone(report.primary_valuation)
        self.assertFalse(any('无法形成可靠估值结论' in reason for reason in report.key_reasons))
        for render in (render_text, render_markdown):
            self.assertNotIn('数据不足，无法评级', render(report))
