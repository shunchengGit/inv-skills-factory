"""Synthetic read-only joint-risk and opportunity contract tests."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "portfolio_risk.py"
spec = importlib.util.spec_from_file_location("portfolio_risk", SCRIPT)
portfolio_risk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portfolio_risk)

SAMPLE = """## 当前持仓
- **估值生成时间**：2026-09-26 22:31（来源）
| 标的 | 代码 | 市场 | 板块 | 股数 | 价格 | 币种 | 市值(万CNY) | 仓位 | PE | 价格区间位 | 核心风险 | 备注 |
|------|------|------|------|------|------|------|------------|------|-----|-------|---------|------|
| 腾讯控股 | 00700 | HK | 互联网 | 1 | 1 | HKD | **35.10** | **35.1%** | — | — | — | — |
| 台积电 | TSM | US | 半导体 | 1 | 1 | USD | **12.80** | **12.8%** | — | — | — | — |
| 科创50ETF华夏 | 588000 | A | ETF | 1 | 1 | CNY | **4.10** | **4.1%** | — | — | — | — |
| 现金 | — | — | — | — | — | CNY | **48.00** | **48.0%** | — | — | — | — |
---
## 调仓记录
| 旧仓 | OLD | — | — | — | — | — | 1 | 99% | — | — | — | — |
"""


class PortfolioRiskTests(unittest.TestCase):
    def test_parses_only_current_weights_and_snapshot(self):
        parsed = portfolio_risk.parse_portfolio(SAMPLE)
        self.assertEqual(parsed["snapshot"], "2026-09-26 22:31")
        self.assertEqual(parsed["weights"], {"00700": 35.1, "TSM": 12.8, "588000": 4.1, "CASH": 48.0})
        self.assertEqual(parsed["total_weight"], 100.0)

    def test_joint_exposures_manual_weights_and_unknown_etf(self):
        parsed = portfolio_risk.parse_portfolio(SAMPLE)
        result = portfolio_risk.joint_exposure(parsed, {
            "00700": {"China demand": 0.6, "AI capex": 0.2},
            "TSM": {"AI capex": 0.7},
        })
        self.assertAlmostEqual(result["factors"]["China demand"], 21.06)
        self.assertAlmostEqual(result["factors"]["AI capex"], 15.98)
        self.assertAlmostEqual(result["pair_overlap"]["00700|TSM"], 7.02)
        self.assertAlmostEqual(result["unknown"]["588000"], 4.1)
        self.assertEqual(result["classification"], "manual scenario mapping; not proven beta/correlation")

    def test_etf_lookthrough_remains_unknown_even_with_manual_factor_mapping(self):
        parsed = portfolio_risk.parse_portfolio(SAMPLE)
        result = portfolio_risk.joint_exposure(parsed, {"588000": {"AI capex": 1.0}})
        self.assertEqual(result["factors"]["AI capex"], 4.1)
        self.assertEqual(result["etf_lookthrough_unknown"]["588000"], 4.1)

    def test_exposure_rejects_unbounded_or_unheld_allocations(self):
        parsed = portfolio_risk.parse_portfolio(SAMPLE)
        for mapping in ({"00700": {"AI": 1.1}}, {"OLD": {"AI": 1}}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                portfolio_risk.joint_exposure(parsed, mapping)

    def test_scenario_requires_all_shocks_and_evidence(self):
        parsed = portfolio_risk.parse_portfolio(SAMPLE)
        assumptions = {code: {"return_pct": -20 if code == "00700" else 0,
                              "evidence": "analyst-defined stress assumption"}
                       for code in parsed["weights"]}
        result = portfolio_risk.scenario_impact(parsed, "China stress", "12 months", assumptions)
        self.assertAlmostEqual(result["portfolio_impact_pct"], -7.02)
        self.assertEqual(result["contributions_pct"]["00700"], -7.02)
        del assumptions["588000"]
        self.assertIsNone(portfolio_risk.scenario_impact(parsed, "China stress", "12 months", assumptions)["portfolio_impact_pct"])
        self.assertIn("588000", portfolio_risk.scenario_impact(parsed, "China stress", "12 months", assumptions)["missing"])
        assumptions["588000"] = {"return_pct": 0, "evidence": ""}
        self.assertIsNone(portfolio_risk.scenario_impact(parsed, "China stress", "12 months", assumptions)["portfolio_impact_pct"])

    def test_same_horizon_comparison_only_ranks_complete_evidence(self):
        options = [
            {"name": "hold TSM", "horizon": "12 months", "expected_return_pct": 12,
             "downside_pct": -25, "cost_pct": 0, "evidence": "dated model A", "asof_date": "2026-09-25", "evidence_gate": "passed"},
            {"name": "buy alternative", "horizon": "12 months", "expected_return_pct": 18,
             "downside_pct": -30, "cost_pct": 1, "evidence": "dated model B", "asof_date": "2026-09-25", "evidence_gate": "passed"},
        ]
        ranked = portfolio_risk.compare_opportunities(options)
        self.assertEqual([item["name"] for item in ranked["ranking"]], ["buy alternative", "hold TSM"])
        self.assertEqual(ranked["ranking"][0]["net_return_pct"], 17)
        options[1]["horizon"] = "3 years"
        self.assertIsNone(portfolio_risk.compare_opportunities(options)["ranking"])
        options[1]["horizon"] = "12 months"
        options[1]["evidence"] = ""
        self.assertIsNone(portfolio_risk.compare_opportunities(options)["ranking"])
        options[1]["evidence"] = "dated model B"
        del options[1]["cost_pct"]
        self.assertIsNone(portfolio_risk.compare_opportunities(options)["ranking"])

    def test_comparison_requires_same_asof_date_and_explicit_evidence_gate(self):
        base = {'horizon': '3y', 'expected_return_pct': 12.0, 'downside_pct': -25.0,
                'cost_pct': 0.5, 'evidence': 'source link', 'asof_date': '2026-09-25',
                'evidence_gate': 'passed'}
        options = [{**base, 'name': 'hold'}, {**base, 'name': 'candidate', 'asof_date': '2026-09-24'}]
        result = portfolio_risk.compare_opportunities(options)
        self.assertIsNone(result['ranking'])
        self.assertIn('same asof_date', result['missing'])
        options[1]['asof_date'] = '2026-09-25'
        options[1]['evidence_gate'] = 'needs_review'
        result = portfolio_risk.compare_opportunities(options)
        self.assertIsNone(result['ranking'])
        self.assertIn('option[1] evidence_gate not passed', result['missing'])

    def test_cli_audit_is_read_only_and_never_ranks_without_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio.md"
            path.write_text(SAMPLE, encoding="utf-8")
            before = path.read_bytes()
            process = subprocess.run([sys.executable, "-B", str(SCRIPT), "--portfolio", str(path)],
                                     capture_output=True, text=True, check=True)
            result = json.loads(process.stdout)
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(result["portfolio"]["weights"]["00700"], 35.1)
            self.assertEqual(result["joint_exposure"]["unknown"]["588000"], 4.1)
            self.assertIsNone(result["scenario"]["portfolio_impact_pct"])
            self.assertIsNone(result["comparison"]["ranking"])


if __name__ == "__main__":
    unittest.main()
