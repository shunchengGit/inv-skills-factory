import sys
import types
import unittest
import tempfile
from unittest.mock import patch
from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
sys.modules.setdefault("requests", types.SimpleNamespace())
import qq_update_portfolio as q


class QuoteDateContractTest(unittest.TestCase):
    def test_source_date_and_year_range_are_not_disguised_as_today_and_52w(self):
        holdings = [
            {"name": "宁波银行", "code": "002142", "market": "A"},
            {"name": "腾讯控股", "code": "00700", "market": "HK"},
            {"name": "微软", "code": "MSFT", "market": "US"},
        ]
        def row(code, count, values):
            fields = [""] * count
            for key, val in values.items():
                fields[key] = str(val)
            return 'v_' + code + '="' + '~'.join(fields) + '";'
        response = '\n'.join([
            row('sz002142', 90, {3: 34.91, 4: 34.72, 32: .55, 30: '20260924161415', 47: 38.19, 48: 31.25}),
            row('hk00700', 80, {3: 435.0, 4: 440.0, 32: -1.0, 30: '2026/09/25 14:20:00', 39: 16, 48: 677.7, 49: 411}),
            row('usMSFT', 73, {3: 497.93, 4: 500.0, 32: -.53, 30: '2026-09-24 16:00:01', 39: 27.7, 48: 549.14, 49: 348.54}),
        ])
        old = q.requests
        q.requests = types.SimpleNamespace(get=lambda *args, **kwargs: types.SimpleNamespace(text=response, encoding=None))
        try:
            md = q.fetch_qq_data(holdings)
        finally:
            q.requests = old
        self.assertEqual(md['宁波银行']['quote_date'], '2026-09-24')
        self.assertEqual(md['宁波银行']['source_note'], '年内高/低')
        self.assertEqual(md['腾讯控股']['quote_date'], '2026-09-25')
        self.assertEqual(md['微软']['quote_date'], '2026-09-24')
        self.assertEqual(md['微软']['quote_session'], '美东收盘')
        self.assertEqual(md['腾讯控股']['quote_session'], '盘中/延迟')

    def test_us_quote_date_required_to_be_source_date_in_render(self):
        from test_report_format import _fixture
        portfolio, calc, constraints = _fixture()
        for holding in calc['holdings']:
            holding['risk'] = '测试'
        calc['holdings'][0].update(quote_date='2026-08-30', quote_session='盘中/延迟', source_note='52周', low_52w=300, high_52w=600)
        calc['holdings'][1].update(quote_date='2026-08-29', quote_session='美东收盘', source_note='52周', low_52w=300, high_52w=600)
        rendered = q.generate_portfolio_md(calc, portfolio, constraints)
        self.assertIn('2026-08-29 美东收盘', rendered)
        self.assertNotIn('2026-08-30 盘中+0.27%', rendered)

    def test_a_share_year_position_is_not_labeled_52_week(self):
        from test_report_format import _fixture
        portfolio, calc, constraints = _fixture()
        for holding in calc['holdings']:
            holding['risk'] = '测试'
        calc['holdings'][0].update(market='A', code='002142', quote_date='2026-08-29', quote_session='收盘', source_note='年内高/低', low_52w=20, high_52w=40)
        calc['holdings'][1].update(quote_date='2026-08-29', quote_session='美东收盘', source_note='52周', low_52w=300, high_52w=600)
        rendered = q.generate_portfolio_md(calc, portfolio, constraints)
        self.assertIn('价格区间位', rendered)
        self.assertIn('18%(年内)', rendered)
        self.assertIn('年内高/低', rendered)
        report = q.build_report(calc, portfolio, constraints)
        self.assertIn('年内', report)

    def test_write_mode_preserves_exchange_dates_in_data_gap(self):
        from test_report_format import _fixture
        portfolio, calc, constraints = _fixture()
        portfolio['holdings'] = calc['holdings']
        for holding in calc['holdings']:
            holding['risk'] = '测试'
            holding.update(quote_date='2026-08-29', quote_session='美东收盘', source_note='52周', low_52w=300, high_52w=600)
        portfolio_source = '''## 当前持仓
旧内容
---
## 纪律检查
旧内容
---
## 数据缺口说明
旧内容
---
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'PORTFOLIO.md'
            path.write_text(portfolio_source, encoding='utf-8')
            with (patch.object(sys, 'argv', ['qq_update_portfolio.py', '--write', '--portfolio', str(path)]),
                  patch.object(q, 'parse_portfolio', return_value=portfolio),
                  patch.object(q, 'fetch_qq_data', return_value={h['name']: h for h in calc['holdings']}),
                  patch.object(q, 'calculate', return_value=calc),
                  patch.object(q, 'load_constraints', return_value=constraints),
                  redirect_stderr(StringIO()), redirect_stdout(StringIO())):
                q.main()
            result = path.read_text(encoding='utf-8')
            self.assertIn('2026-08-29 美东收盘', result)
            self.assertNotIn('2026-08-30 盘中', result)
            self.assertIn('价格位置非估值分位', result)


if __name__ == '__main__':
    unittest.main()
