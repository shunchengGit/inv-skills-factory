import sys
import types
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

sys.modules.setdefault("requests", types.SimpleNamespace())
import qq_update_portfolio as q


def _fixture():
    portfolio = {
        "usd_cny": 6.77,
        "hkd_cny": 0.863,
        "cash_hkd": 45300,
        "cash_cny": 20000,
        "cash_usd": 100,
        "holdings": [],
    }
    calc = {
        "holdings": [
            {
                "name": "腾讯控股", "code": "00700", "market": "HK",
                "sector": "互联网平台", "shares": 900,
                "price": 460.2, "change_pct": -2.0,
                "pos_52w": 18, "pe_static": None, "pe_ttm": 16.81,
                "value_wan": 35.74, "position_pct": 35.8,
            },
            {
                "name": "微软", "code": "MSFT", "market": "US",
                "sector": "软件与服务", "shares": 70,
                "price": 384.36, "change_pct": 0.27,
                "pos_52w": 17, "pe_static": None, "pe_ttm": 22.89,
                "value_wan": 18.21, "position_pct": 18.2,
            },
        ],
        "total_assets": 99.85,
        "total_stock": 98.2,
        "cash_value": 1.65,
        "cash_hkd_wan": 3.91,
        "cash_pct": 1.6,
        "sectors": {"半导体/电子制造": 0.0, "软件/互联网平台": 54.0},
        "timestamp": "2026-08-30 19:00",
    }
    constraints = {
        "max_single_pct": 40,
        "max_sector_pct": 55,
        "min_cash_pct": 2,
        "cash_target_low": 5,
        "cash_target_high": 10,
    }
    return portfolio, calc, constraints


class ReportFormatContractTest(unittest.TestCase):
    """锁定用户侧持仓报告的输出格式契约。"""

    def setUp(self):
        self.portfolio, self.calc, self.constraints = _fixture()
        self.report = q.build_report(self.calc, self.portfolio, self.constraints)
        self.lines = self.report.split("\n")

    def test_structure_sections_in_order(self):
        joined = "\n".join(self.lines)
        i_overview = joined.index("[ 组合概览 ]")
        i_discipline = joined.index("[ 纪律检查 ]")
        i_watch = joined.index("[ 关键关注 ]")
        self.assertLess(i_overview, i_discipline)
        self.assertLess(i_discipline, i_watch)

    def test_fixed_column_order(self):
        header = next(l for l in self.lines if l.startswith("| 标的"))
        cols = [c.strip() for c in header.strip("|").split("|")]
        self.assertEqual(cols, q.REPORT_COLUMNS)

    def test_column_count_consistent(self):
        table_lines = [l for l in self.lines if l.startswith("|")]
        for line in table_lines:
            # 9 列 => 10 个管道符
            self.assertEqual(line.count("|"), 10, line)

    def test_no_markdown_markup(self):
        for line in self.lines:
            self.assertNotIn("**", line)
            self.assertNotIn("###", line)
            self.assertNotIn("](", line)

    def test_terminal_equal_width_alignment(self):
        table_lines = [l for l in self.lines if l.startswith("|")]
        self.assertGreater(len(table_lines), 2)
        widths = {q.char_width(l) for l in table_lines}
        self.assertEqual(len(widths), 1, f"表格各行终端宽度不一致: {widths}")

    def test_wide_char_width(self):
        self.assertEqual(q.char_width("腾讯"), 4)
        self.assertEqual(q.char_width("MSFT"), 4)
        self.assertEqual(q.char_width("腾讯控股 | MSFT"), 15)

    def test_cash_warning_when_below_min(self):
        joined = "\n".join(self.lines)
        # cash_pct=1.6 低于 2% 下限，现金行应带水位警示
        self.assertIn("⚠️ 现金水位不足", joined)
        # 纪律检查应标未达标
        self.assertIn("未达标", joined)

    def test_cash_warning_between_min_and_target(self):
        portfolio, calc, constraints = _fixture()
        calc = {**calc, "cash_pct": 3.3}
        report = q.build_report(calc, portfolio, constraints)
        self.assertIn("⚠️ 低于建议区间", report)
        self.assertIn("(达标)", report)

    def test_no_watch_when_all_compliant(self):
        portfolio, calc, constraints = _fixture()
        calc = {**calc, "cash_pct": 6.0}
        for h in calc["holdings"]:
            h["pos_52w"] = 30
        report = q.build_report(calc, portfolio, constraints)
        self.assertIn("暂无触发项", report)


if __name__ == "__main__":
    unittest.main()
