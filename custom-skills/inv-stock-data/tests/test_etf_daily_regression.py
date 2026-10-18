"""Regression: ETF bars must not depend on A-share capital history."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fetch_etf


class EtfDailyRegression(unittest.TestCase):
    def test_etf_specific_endpoint_returns_sorted_bars(self):
        bars = pd.DataFrame([
            {'date': '2026-10-08', 'close': 1.537, 'open': 1.6, 'high': 1.61, 'low': 1.53, 'volume': 100},
            {'date': '2026-09-30', 'close': 1.616, 'open': 1.6, 'high': 1.62, 'low': 1.59, 'volume': 90},
        ])
        api = SimpleNamespace(fund_etf_hist_sina=Mock(return_value=bars),
                              stock_zh_a_daily=Mock(side_effect=ValueError('No value to decode')))
        with patch.dict(sys.modules, {'akshare': api}):
            result = fetch_etf.fetch_etf_daily('588000', n=1)
        self.assertIsNotNone(result, 'ETF price history must not require stock share-capital data')
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[-1]['close'], 1.537)
        api.fund_etf_hist_sina.assert_called_once_with(symbol='sh588000')
        api.stock_zh_a_daily.assert_not_called()

    def test_upstream_exception_reaches_daily_envelope(self):
        import commands
        api = SimpleNamespace(fund_etf_hist_sina=Mock(side_effect=ValueError('invalid ETF payload')),
                              stock_zh_a_daily=Mock(side_effect=ValueError('invalid ETF payload')))
        with patch.dict(sys.modules, {'akshare': api}):
            result = commands.cmd_daily('588000', 'etf')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('ValueError: invalid ETF payload', result['sources'][0]['reason'])

    def test_snapshot_preserves_daily_failure(self):
        import commands
        bars = pd.DataFrame()
        bars.attrs['fetch_error'] = 'ValueError: invalid ETF payload'
        with patch.object(commands, 'fetch_etf_daily', return_value=bars), patch.object(commands, 'fetch_etf_name', return_value={'name': 'ETF'}), patch.object(commands, 'fetch_etf_nav', return_value=None):
            result = commands.cmd_snapshot_etf('588000')
        self.assertIn('ValueError: invalid ETF payload', result['sources'][0]['reason'])
        self.assertTrue(any('不复权' in note for note in result['notes']))

    def test_shenzhen_etf_routes_to_etf_not_stock(self):
        from market import parse_symbol
        self.assertEqual(parse_symbol('159915'), ('159915', 'etf'))
        self.assertEqual(parse_symbol('588000'), ('588000', 'etf'))
        self.assertEqual(parse_symbol('002142'), ('002142', 'a'))

    def test_price_basis_is_explicit(self):
        import commands
        bars = pd.DataFrame([{'date': '2026-09-30', 'close': 1.616}])
        with patch.object(commands, 'fetch_etf_daily', return_value=bars):
            result = commands.cmd_daily('588000', 'etf')
        self.assertTrue(any('不复权' in note for note in result['notes']))


if __name__ == '__main__':
    unittest.main()
