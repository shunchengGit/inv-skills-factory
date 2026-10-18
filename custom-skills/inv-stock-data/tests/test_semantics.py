import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import commands
import fetch_ashare
import fetch_etf


class DataSemanticsTest(unittest.TestCase):
    def test_relations_identifies_industry_members_not_research(self):
        provider = types.SimpleNamespace(
            stock_board_industry_name_em=lambda: pd.DataFrame({'板块名称': ['银行']}),
            stock_board_industry_cons_em=lambda **kw: pd.DataFrame({'代码': ['600000', '600001'], '名称': ['甲', '乙']}),
        )
        with patch.dict(sys.modules, {'akshare': provider}):
            payload = commands.cmd_relations('600000')
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['data']['relation_type'], 'industry_constituents')
        self.assertEqual(payload['data']['industry_members'], payload['data']['relations'])
        self.assertEqual(payload['sources'][0]['name'], 'eastmoney-industry')
        self.assertIsNone(payload['data_as_of'])
        self.assertTrue(any('不是调研' in note for note in payload['notes']))

    def test_yahoo_leverage_has_ratio_unit_and_legacy_percent_alias(self):
        with patch.object(commands, 'fetch_yahoo_info', return_value={'debtToEquity': 125.0}), patch.object(commands, 'fetch_yahoo_history', return_value=pd.DataFrame({'close': [10.0]})):
            financial = commands.cmd_financial('AAPL', 'us')['data']['fundamentals']
            snapshot = commands.cmd_snapshot_yahoo('AAPL', 'us')['data']['fundamentals']
        for fund in (financial, snapshot):
            self.assertEqual(fund['debt_to_equity_ratio'], 1.25)
            self.assertIsNone(fund['debt_to_asset_pct'])
        self.assertEqual(financial['debt_to_equity'], 125.0)

    def test_a_share_financial_does_not_label_assets_as_equity(self):
        with patch.object(commands, 'fetch_ths_financial', return_value={'资产负债率': '38.5%'}), patch.object(commands, 'fetch_sina_financial_indicator', return_value=None):
            fund = commands.cmd_financial('600000', 'a')['data']['fundamentals']
        self.assertEqual(fund['debt_to_asset_pct'], 38.5)
        self.assertIsNone(fund['debt_to_equity_ratio'])
        self.assertNotIn('debt_to_equity', fund)
        with patch.object(commands, '_raw_snapshot_a', return_value={'name': '甲', 'financial': {'资产负债率': '38.5%'}, 'daily': [], 'valuation': {}, 'description': None}):
            snapshot = commands.cmd_snapshot_a('600000')['data']['fundamentals']
        self.assertEqual(snapshot['debt_to_asset_pct'], 38.5)
        self.assertIsNone(snapshot['debt_to_equity_ratio'])

    def test_etf_ohlc_is_never_a_nav_source_even_with_nav_like_columns(self):
        calls = []
        def history(**kw):
            calls.append(kw)
            return pd.DataFrame({'日期': ['2026-01-05'], '收盘': [1.2], '单位净值': [1.1]})
        with patch.dict(sys.modules, {'akshare': types.SimpleNamespace(fund_etf_hist_em=history)}):
            self.assertIsNone(fetch_etf.fetch_etf_nav('510000'))
        self.assertEqual(calls, [])
        with patch.object(commands, 'fetch_etf_name', return_value={'name': 'ETF'}), patch.object(commands, 'fetch_etf_daily', return_value=pd.DataFrame({'close': [1.2]})), patch.dict(sys.modules, {'akshare': types.SimpleNamespace(fund_etf_hist_em=history)}):
            payload = commands.cmd_snapshot_etf('510000')
        self.assertEqual(payload['status'], 'partial')
        self.assertIsNone(payload['data']['nav'])
        self.assertTrue(any(gap['field'] == 'data.nav' for gap in payload['gaps']))

    def test_industry_member_fetch_has_explicit_name_and_legacy_alias(self):
        provider = types.SimpleNamespace(
            stock_board_industry_name_em=lambda: pd.DataFrame({'板块名称': ['银行']}),
            stock_board_industry_cons_em=lambda **kw: pd.DataFrame({'代码': ['600000'], '名称': ['甲']}),
        )
        with patch.dict(sys.modules, {'akshare': provider}):
            self.assertEqual(fetch_ashare.fetch_industry_members('600000'), fetch_ashare.fetch_relations('600000'))


if __name__ == '__main__':
    unittest.main()
