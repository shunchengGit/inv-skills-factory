import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'forecast_returns.py'
if SCRIPT.exists():
    spec = importlib.util.spec_from_file_location('forecast_returns', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
else:
    mod = None


class ReturnTests(unittest.TestCase):
    def test_annual_irr_respects_cash_timing_and_negative_returns(self):
        self.assertTrue(callable(getattr(mod, 'annual_irr', None)), 'annual_irr is required')
        self.assertAlmostEqual(mod.annual_irr(100, [60, 60]), 0.1306623862918075)
        self.assertNotAlmostEqual(mod.annual_irr(100, [60, 60]), math.sqrt(1.2) - 1)
        self.assertAlmostEqual(mod.annual_irr(100, [0, 81]), -0.1)
        self.assertEqual(mod.annual_irr(100, [0, 0]), -1.0)
        self.assertAlmostEqual(mod.annual_irr(100, [100, 0]), 0.0)

    def test_forecast_cash_flows_fees_targets_and_rf(self):
        self.assertTrue(callable(getattr(mod, 'forecast', None)), 'forecast is required')
        data = {'years': 2, 'current_price': 100, 'currency': 'USD',
                'as_of': '2026-10-18', 'buy_fee_rate': .01, 'exit_fee_rate': .02,
                'dividend_tax_rate': .25, 'pessimistic_floor_rate': .03,
                'target_cagr_range': [.1, .2],
                'scenarios': [{'name': name, 'terminal_price': 120, 'dividends': [8, 8]}
                              for name in ['pessimistic', 'base', 'optimistic']]}
        result = mod.forecast(data)
        base = result['scenarios'][1]
        self.assertEqual(base['annual_net_cash_flows'], [6, 123.6])
        self.assertEqual(result['initial_cost'], 101)
        self.assertAlmostEqual(base['annual_irr'], mod.annual_irr(101, [6, 123.6]))
        self.assertAlmostEqual(base['terminal_collected_cagr_non_irr'], (129.6/101)**.5-1)
        for rate, price in zip([.1, .2], base['max_buy_prices_for_target']):
            self.assertAlmostEqual(price, (6/(1+rate)+123.6/(1+rate)**2)/1.01)
            self.assertAlmostEqual(mod.annual_irr(price*1.01, [6, 123.6]), rate)
        floor = result['pessimistic_floor']
        self.assertAlmostEqual(floor['max_buy_price'], (6/1.03+123.6/1.03**2)/1.01)
        self.assertAlmostEqual(floor['irr_buffer'], result['scenarios'][0]['annual_irr'] - .03)
        self.assertTrue(floor['pass'])
        self.assertEqual(base['target_comparison'], 'within_range')
        for rate, buffer in zip([.1, .2], base['target_buffers']):
            self.assertAlmostEqual(buffer, base['annual_irr'] - rate)

    def test_invalid_inputs_are_rejected_explicitly(self):
        data = {'years': 2, 'current_price': 100, 'currency': 'USD',
                'as_of': '2026-10-18', 'target_cagr_range': [.1, .2],
                'scenarios': [{'name': name, 'terminal_price': 120, 'dividends': [0, 0]}
                              for name in ['pessimistic', 'base', 'optimistic']]}
        cases = [None, [], {}, dict(data, years=0), dict(data, years=2.5),
                 dict(data, years=True), dict(data, current_price=True),
                 dict(data, current_price=0), dict(data, current_price=-1),
                 dict(data, current_price=float('nan')), dict(data, current_price=float('inf')),
                 dict(data, current_price='100'), dict(data, currency=''),
                 dict(data, as_of='2026-02-30'), dict(data, as_of=''),
                 dict(data, scenarios=[]), dict(data, scenarios=[{}]),
                 dict(data, target_cagr_range=[-.1, -1]),
                 dict(data, target_cagr_range=[-1, .1]),
                 dict(data, target_cagr_range=[.2, .1]),
                 dict(data, target_cagr_range=[.1]),
                 dict(data, target_cagr_range=[False, .1]),
                 dict(data, pessimistic_floor_rate=-1),
                 dict(data, pessimistic_floor_rate=True),
                 dict(data, pessimistic_floor_rate=float('inf')),
                 dict(data, pessimistic_floor_basis=1),
                 dict(data, annual_rf_after_tax=.03)]
        for field in ['buy_fee_rate', 'exit_fee_rate', 'dividend_tax_rate']:
            for value in [-.01, 1.01, True, float('nan'), None]:
                cases.append(dict(data, **{field: value}))
        for field, value in [('name', ''), ('name', 'other'), ('terminal_price', -1),
                             ('terminal_price', True), ('terminal_price', float('inf')),
                             ('dividends', [-1, 0]), ('dividends', [0]),
                             ('dividends', [True, 0]), ('dividends', [float('nan'), 0]),
                             ('terminal_bridge', []), ('terminal_bridge', {'x': float('nan')})]:
            scenario = dict(data['scenarios'][0], **{field: value})
            cases.append(dict(data, scenarios=[scenario] + data['scenarios'][1:]))
        cases.append(dict(data, scenarios=[data['scenarios'][0]]*3))
        extra = dict(data['scenarios'][0], name='no_rerating')
        cases.append(dict(data, scenarios=data['scenarios'] + [extra, extra]))
        cases.append(dict(data, scenarios=data['scenarios'][1:] + [extra]))
        for missing in ['years', 'current_price', 'currency', 'as_of', 'target_cagr_range', 'scenarios']:
            cases.append({k: v for k, v in data.items() if k != missing})
        for bad in cases:
            with self.subTest(input=bad), self.assertRaises(ValueError):
                mod.forecast(bad)

    def test_external_fx_financial_terminal_and_missing_rf_are_transparent(self):
        bridge = {'method': 'financial book value sensitivity, not PE',
                  'source': 'illustrative assumption, not market data',
                  'unit_conversion': 'external: 200 HKD per share / 8 HKD per USD = 25 USD'}
        data = {'years': 1, 'current_price': 20, 'currency': 'USD',
                'as_of': '2026-10-18', 'target_cagr_range': [.3, .4],
                'scenarios': [{'name': name, 'terminal_price': 25, 'dividends': [0],
                               'terminal_bridge': bridge}
                              for name in ['pessimistic', 'base', 'optimistic']]}
        original = json.dumps(data)
        result = mod.forecast(data)
        self.assertEqual(result['scenarios'][0]['terminal_bridge'], bridge)
        self.assertAlmostEqual(result['scenarios'][0]['annual_irr'], .25)
        self.assertEqual(result['scenarios'][0]['target_comparison'], 'below_range')
        self.assertIsNone(result['pessimistic_floor']['pass'])
        self.assertIsNone(result['pessimistic_floor']['max_buy_price'])
        self.assertEqual(result['fees_and_tax'], {'buy_fee_rate': 0, 'exit_fee_rate': 0, 'dividend_tax_rate': 0})
        self.assertIn('税费未核', ' '.join(result['notes']))
        self.assertEqual(result['currency'], 'USD')
        self.assertEqual(result['as_of'], data['as_of'])
        self.assertEqual(json.dumps(data), original)
        for scenario in data['scenarios']:
            scenario['terminal_price'] = 0
        loss = mod.forecast(data)['scenarios'][0]
        self.assertEqual(loss['annual_irr'], -1)
        self.assertEqual(loss['terminal_collected_cagr_non_irr'], -1)
        self.assertEqual(loss['max_buy_prices_for_target'], [0, 0])

    def test_cli_json_success_uses_example(self):
        run = subprocess.run([sys.executable, '-B', str(SCRIPT), '--input',
                              str(ROOT / 'templates' / 'example.json'), '--output', 'json'],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(run.stdout.strip(), 'CLI must emit a result')
        result = json.loads(run.stdout)
        self.assertEqual(len(result['scenarios']), 3)
        self.assertIsNone(result['pessimistic_floor']['pass'])
        self.assertLess(result['scenarios'][0]['annual_irr'], 0)
        self.assertEqual(result['scenarios'][2]['target_comparison'], 'above_range')

    def test_cli_text_explains_irr_non_irr_and_thresholds(self):
        run = subprocess.run([sys.executable, '-B', str(SCRIPT), '--input',
                              str(ROOT / 'templates' / 'example.json'), '--output', 'text'],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(run.stdout.startswith('inv-value-return'))
        for token in ['IRR', 'non-IRR', '税费未核', 'pessimistic', 'base', 'optimistic',
                      'max_buy_prices_for_target', 'not certified', 'terminal_bridge', 'pp']:
            self.assertIn(token, run.stdout)

    def test_cli_failure_is_clean_and_nonzero(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as temporary:
            path = Path(temporary) / 'bad.json'
            for payload in ['{}', '{bad', '{"current_price": NaN}', '{"current_price": Infinity}']:
                path.write_text(payload, encoding='utf-8')
                run = subprocess.run([sys.executable, '-B', str(SCRIPT), '--input', str(path)],
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(run.stdout, '')
                self.assertIn('error:', run.stderr)
                self.assertNotIn('Traceback', run.stderr)
            run = subprocess.run([sys.executable, '-B', str(SCRIPT), '--input', str(path)+'missing'],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn('Traceback', run.stderr)

    def test_irr_public_api_rejects_invalid_cash(self):
        for cost, cash in [(0, [1]), (True, [1]), (100, []), (100, [-1]),
                           (100, [True]), (100, [float('nan')]), (100, None)]:
            with self.subTest(cost=cost, cash=cash), self.assertRaises(ValueError):
                mod.annual_irr(cost, cash)

    def test_target_boundaries_are_inclusive_despite_root_rounding(self):
        data = {'years': 1, 'current_price': 100, 'currency': 'USD',
                'as_of': '2026-10-18', 'target_cagr_range': [.1, .2],
                'pessimistic_floor_rate': .21,
                'scenarios': [{'name': name, 'terminal_price': price, 'dividends': [0]}
                              for name, price in [('pessimistic', 110), ('base', 120), ('optimistic', 130)]]}
        result = mod.forecast(data)
        self.assertEqual([s['target_comparison'] for s in result['scenarios']],
                         ['within_range', 'within_range', 'above_range'])
        self.assertFalse(result['pessimistic_floor']['pass'])
        data['pessimistic_floor_rate'] = .1
        self.assertTrue(mod.forecast(data)['pessimistic_floor']['pass'])

    def test_optional_no_rerating_and_negative_floor(self):
        data = {'years': 1, 'current_price': 100, 'currency': 'USD',
                'as_of': '2026-10-18', 'target_cagr_range': [.15, .2],
                'pessimistic_floor_rate': -.05, 'pessimistic_floor_basis': 'user floor',
                'scenarios': [{'name': name, 'terminal_price': price, 'dividends': [0]}
                              for name, price in [('pessimistic', 96), ('base', 118),
                                                  ('optimistic', 130), ('no_rerating', 108)]]}
        result = mod.forecast(data)
        self.assertEqual([s['name'] for s in result['scenarios']],
                         ['pessimistic', 'base', 'optimistic', 'no_rerating'])
        self.assertEqual(result['scenarios'][3]['target_comparison'], 'below_range')
        floor = result['pessimistic_floor']
        self.assertTrue(floor['pass'])
        self.assertAlmostEqual(floor['irr_buffer'], .01)
        self.assertAlmostEqual(floor['max_buy_price'], 96 / .95)
        self.assertEqual(floor['basis'], 'user floor')


if __name__ == '__main__':
    unittest.main()
