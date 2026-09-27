"""Read-only cash/position reconciliation and performance completeness tests."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "performance_audit.py"


class PerformanceAuditTests(unittest.TestCase):
    def run_audit(self, rows, portfolio_text=None):
        with tempfile.TemporaryDirectory() as d:
            statement = Path(d) / "synthetic_statement.csv"
            statement.write_text(rows, encoding="utf-8")
            args = [sys.executable, str(SCRIPT), "--statement", str(statement)]
            if portfolio_text is not None:
                portfolio = Path(d) / "PORTFOLIO.md"
                portfolio.write_text(portfolio_text, encoding="utf-8")
                args += ["--portfolio", str(portfolio)]
            return subprocess.run(args, capture_output=True, text=True)

    def test_rejects_missing_required_fee_fx_and_cash_fields(self):
        header = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,nav_cny,external_flow_cny,reference\n"
        for missing in ("fee", "fx_rate", "cash_delta", "external_flow_cny"):
            rows = header.replace(missing + ",", "") if missing != "fx_rate" else header
            run = self.run_audit(rows)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn(missing, run.stderr)

    def test_rejects_trade_with_blank_fee_or_fx(self):
        header = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n"
        row = "2026-01-01,BUY,AAA,2,10,USD,,USD,-20,USD,7,0,0,t1\n"
        for corrupted in (row, row.replace(",USD,7,", ",USD,,")):
            run = self.run_audit(header + corrupted)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("row 2", run.stderr)

    def test_rejects_trade_net_cash_not_matching_gross_and_fee(self):
        rows = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n2026-01-01,BUY,AAA,2,10,USD,1,USD,-20,USD,7,0,0,t1\n"
        run = self.run_audit(rows)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("cash_delta", run.stderr)

    def test_synthetic_reconciles_positions_cash_and_attribution(self):
        rows = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n" + "\n".join([
            "2026-01-01,OPEN_POSITION,AAA,2,10,USD,0,USD,0,USD,7,0,0,opening",
            "2026-01-01,OPEN_CASH,,0,0,USD,0,USD,100,USD,7,0,0,opening",
            "2026-01-02,BUY,AAA,1,12,USD,1,USD,-13,USD,7,0,0,t1",
            "2026-01-03,DIVIDEND,AAA,0,0,USD,0,USD,2,USD,7,0,0,d1",
            "2026-01-04,CLOSE_POSITION,AAA,3,15,USD,0,USD,0,USD,7,0,0,closing",
            "2026-01-04,CLOSE_CASH,,0,0,USD,0,USD,89,USD,7,0,0,closing",
        ]) + "\n"
        run = self.run_audit(rows)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["reconciliation"]["positions"], {"AAA": "matched"})
        self.assertEqual(result["reconciliation"]["cash"], {"USD": "matched"})
        self.assertEqual(result["attribution_cny"]["price_and_fx_change"], "91")
        self.assertEqual(result["attribution_cny"]["fees"], "-7")
        self.assertEqual(result["attribution_cny"]["dividends"], "14")
        self.assertNotIn("twr", result)

    def test_flags_position_mismatch_and_missing_opening_basis(self):
        rows = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n2026-01-02,BUY,AAA,1,12,USD,0,USD,-12,USD,7,0,0,t1\n2026-01-04,CLOSE_POSITION,AAA,3,15,USD,0,USD,0,USD,7,0,0,closing\n"
        run = self.run_audit(rows)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("opening_position_basis:AAA", result["gaps"])
        self.assertEqual(result["reconciliation"]["positions"]["AAA"], "mismatch: expected 3, reconstructed 1")
        self.assertNotIn("attribution_cny", result)

    def test_rejects_cash_flow_without_matching_external_flow(self):
        header = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n"
        row = "2026-01-02,DEPOSIT,,0,0,CNY,0,CNY,100,CNY,1,0,0,deposit1\n"
        run = self.run_audit(header + row)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("external_flow_cny", run.stderr)

    def test_rejects_unpaired_fx_and_unsupported_cash_flow(self):
        header = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n"
        for kind in ("FX", "FEE", "OTHER"):
            row = f"2026-01-02,{kind},,0,0,USD,0,USD,100,USD,7,0,0,event1\n"
            run = self.run_audit(header + row)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("row 2", run.stderr)

    def test_rejects_closing_cash_without_opening_or_transactions(self):
        header = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n"
        row = "2026-01-04,CLOSE_CASH,,0,0,CNY,0,CNY,10,CNY,1,10,0,end\n"
        run = self.run_audit(header + row)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertIn("opening_cash:CNY", result["gaps"])
        self.assertNotIn("attribution_cny", result)

    def test_rejects_ambiguous_duplicate_close_and_inconsistent_cash_event(self):
        header = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n"
        opening = "2026-01-01,OPEN_CASH,,0,0,CNY,0,CNY,100,CNY,1,0,0,open\n"
        duplicate = "2026-01-02,CLOSE_CASH,,0,0,CNY,0,CNY,100,CNY,1,0,0,end1\n2026-01-03,CLOSE_CASH,,0,0,CNY,0,CNY,100,CNY,1,0,0,end2\n"
        run = self.run_audit(header + opening + duplicate)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("duplicate closing cash", run.stderr)
        run = self.run_audit(header + "2026-01-02,DIVIDEND,AAA,0,0,CNY,1,CNY,2,CNY,1,0,0,d1\n")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("fee", run.stderr)

    def test_statement_positions_absent_from_portfolio_are_flagged(self):
        fixture = Path(__file__).resolve().parent / "fixtures" / "synthetic_performance.csv"
        portfolio = "## 当前持仓\n| 标的 | 代码 | 市场 | 板块 | 股数 |\n|---|---|---|---|---|\n## 调仓记录\n"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "PORTFOLIO.md"
            path.write_text(portfolio, encoding="utf-8")
            run = subprocess.run([sys.executable, str(SCRIPT), "--statement", str(fixture),
                                  "--portfolio", str(path)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertIn("portfolio_unexpected_position:AAA", result["gaps"])
            self.assertNotIn("attribution_cny", result)

    def test_portfolio_cash_mismatch_suppresses_attribution(self):
        header = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n"
        rows = header + "2026-01-01,OPEN_CASH,,0,0,CNY,0,CNY,100,CNY,1,100,0,open\n2026-01-02,CLOSE_CASH,,0,0,CNY,0,CNY,100,CNY,1,100,0,end\n"
        portfolio = "## 当前持仓\n  - 人民币现金：**200 CNY**\n## 调仓记录\n"
        run = self.run_audit(rows, portfolio)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertIn("portfolio_cash_mismatch:CNY", result["gaps"])
        self.assertNotIn("attribution_cny", result)

    def test_unverified_provenance_never_claims_actual_performance(self):
        rows = "date,type,symbol,quantity,price,currency,fee,fee_currency,cash_delta,cash_currency,fx_rate,nav_cny,external_flow_cny,reference\n2026-01-01,OPEN_CASH,,0,0,CNY,0,CNY,100,CNY,1,100,0,open\n2026-01-02,CLOSE_CASH,,0,0,CNY,0,CNY,110,CNY,1,110,0,end\n"
        run = self.run_audit(rows)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "incomplete")
        self.assertNotIn("twr", result)

    def test_portfolio_notes_with_estimated_fills_flag_historical_basis(self):
        with tempfile.TemporaryDirectory() as d:
            portfolio = Path(d) / "PORTFOLIO.md"
            portfolio.write_text("## 当前持仓\n| 标的 | 代码 | 市场 | 板块 | 股数 |\n|---|---|---|---|---|\n| 腾讯 | 00700 | HK | X | **1,000** |\n## 调仓记录\n成交价暂不记录。估算回款未计佣金，现金余额校准。\n", encoding="utf-8")
            run = subprocess.run([sys.executable, str(SCRIPT), "--portfolio", str(portfolio)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertIn("historical_transaction_basis_missing", result["gaps"])
            self.assertIn("historical_cash_flows_unverified", result["gaps"])

    def test_checked_in_synthetic_fixture_is_explicitly_labeled(self):
        fixture = Path(__file__).resolve().parent / "fixtures" / "synthetic_performance.csv"
        run = subprocess.run([sys.executable, str(SCRIPT), "--statement", str(fixture)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["source"], "synthetic_fixture")
        self.assertEqual(result["reconciliation"]["cash"]["USD"], "matched")
        self.assertEqual(result["attribution_cny"]["price_and_fx_change"], "91")
        self.assertNotIn("twr", result)

    def test_portfolio_only_reports_incomplete_without_returns(self):
        with tempfile.TemporaryDirectory() as d:
            portfolio = Path(d) / "PORTFOLIO.md"
            portfolio.write_text("## 当前持仓\n| 标的 | 代码 | 市场 | 板块 | 股数 | 价格 | 币种 | 市值(万CNY) |\n|---|---|---|---|---|---|---|---|\n| 腾讯 | 00700 | HK | X | **1,000** | HK$1 | HKD | 1 |\n| 现金 | — | — | — | — | — | CNY | 1 |\n## 调仓记录\n估算回款，成交价暂不记录\n", encoding="utf-8")
            run = subprocess.run([sys.executable, str(SCRIPT), "--portfolio", str(portfolio)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["holdings"], {"00700": "1000"})
            self.assertEqual(result["cash"], {})
            self.assertNotIn("twr", result)
            self.assertNotIn("xirr", result)
            self.assertIn("broker_statement_required", result["gaps"])
