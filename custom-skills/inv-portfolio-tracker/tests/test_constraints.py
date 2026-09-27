import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from test_report_format import _fixture

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

sys.modules.setdefault("requests", types.SimpleNamespace())
import qq_update_portfolio as q


class ConstraintLoadingTest(unittest.TestCase):
    def test_load_constraints_from_user_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            user_path = Path(tmp) / "USER.md"
            user_path.write_text(
                "组合约束: 单只股票仓位上限：`<= 35%`\n"
                "组合约束: 单一行业集中度：`<= 50%`\n"
                "现金规则：现金 >= 3%，理想 4-8%\n",
                encoding="utf-8",
            )
            old = q.USER_PATH
            q.USER_PATH = user_path
            try:
                constraints = q.load_constraints()
            finally:
                q.USER_PATH = old
        self.assertEqual(constraints["max_single_pct"], 35)
        self.assertEqual(constraints["max_sector_pct"], 50)
        self.assertEqual(constraints["min_cash_pct"], 3)
        self.assertEqual(constraints["cash_target_low"], 4)
        self.assertEqual(constraints["cash_target_high"], 8)

    def test_missing_user_md_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(q, "USER_PATH", Path(tmp) / "USER.md"):
                with self.assertRaisesRegex(FileNotFoundError, "USER.md"):
                    q.load_constraints()

    def test_unparseable_single_stock_cap_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "USER.md"
            path.write_text("组合约束: 单只股票仓位上限：待定\n组合约束: 单一行业集中度：`<= 50%`", encoding="utf-8")
            with patch.object(q, "USER_PATH", path):
                with self.assertRaisesRegex(ValueError, "单只股票仓位上限"):
                    q.load_constraints()

    def test_historical_caps_do_not_substitute_for_current_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "USER.md"
            path.write_text("历史旧规则：单只股票仓位上限：`<= 40%`\n单一行业集中度：`<= 50%`", encoding="utf-8")
            with patch.object(q, "USER_PATH", path):
                with self.assertRaisesRegex(ValueError, "单只股票仓位上限"):
                    q.load_constraints()

    def test_missing_or_invalid_sector_cap_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "USER.md"
            with patch.object(q, "USER_PATH", path):
                for sector_line in ("", "组合约束: 单一行业集中度：待定", "组合约束: 单一行业集中度：`<= 550%`"):
                    with self.subTest(sector_line=sector_line):
                        path.write_text("组合约束: 单只股票仓位上限：`<= 35%`\n" + sector_line, encoding="utf-8")
                        with self.assertRaisesRegex(ValueError, "单一行业集中度"):
                            q.load_constraints()

    def test_cash_record_only_ignores_historical_thresholds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "USER.md"
            path.write_text(
                "组合约束: 单只股票仓位上限：`<= 35%`\n"
                "组合约束: 单一行业集中度：`<= 50%`\n"
                "资金与换汇：现金只记账，不作否决。\n"
                "历史旧规则：现金 >= 2%，建议现金 5-10%；已废止。\n",
                encoding="utf-8",
            )
            with patch.object(q, "USER_PATH", path):
                constraints = q.load_constraints()
        self.assertEqual(constraints["min_cash_pct"], 0)
        self.assertEqual((constraints["cash_target_low"], constraints["cash_target_high"]), (0, 100))
        portfolio, calc, _ = _fixture()
        report = q.build_report(calc, portfolio, constraints)
        self.assertIn("现金：仅记账", report)
        self.assertNotIn("现金水位不足", report)
        self.assertNotIn("低于 2% 下限", report)
        for holding in calc["holdings"]:
            holding.update(low_52w=300, high_52w=600, source_note="52周", risk="测试")
        generated = q.generate_portfolio_md(calc, portfolio, constraints)
        self.assertIn("现金只记账", generated)
        self.assertNotIn("⚠️需调整", generated)

    def test_write_mode_uses_record_only_cash_discipline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PORTFOLIO.md"
            path.write_text("## 当前持仓\n旧内容\n---\n## 纪律检查\n旧内容\n---\n## 数据缺口说明\n旧内容\n---\n", encoding="utf-8")
            portfolio, calc, _ = _fixture()
            portfolio["holdings"] = calc["holdings"]
            for holding in calc["holdings"]:
                holding.update(low_52w=300, high_52w=600, source_note="52周", risk="测试",
                               quote_date="2026-09-25", quote_session="收盘")
            rules = {"max_single_pct": 35, "max_sector_pct": 50, "min_cash_pct": 0,
                     "cash_target_low": 0, "cash_target_high": 100, "cash_record_only": True}
            with (patch.object(sys, "argv", ["qq_update_portfolio.py", "--write", "--portfolio", str(path)]),
                  patch.object(q, "parse_portfolio", return_value=portfolio),
                  patch.object(q, "fetch_qq_data", return_value={}),
                  patch.object(q, "calculate", return_value=calc),
                  patch.object(q, "load_constraints", return_value=rules),
                  redirect_stdout(StringIO()), redirect_stderr(StringIO())):
                q.main()
            result = path.read_text(encoding="utf-8")
            self.assertIn("- 现金：仅记账", result)
            self.assertNotIn("- 现金 `>= 0%`", result)

    def test_default_output_does_not_invent_cash_minimum(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PORTFOLIO.md"
            path.write_text("占位", encoding="utf-8")
            portfolio, calc, _ = _fixture()
            portfolio["holdings"] = calc["holdings"]
            for holding in calc["holdings"]:
                holding.update(low_52w=300, high_52w=600, source_note="52周", risk="测试")
            rules = {"max_single_pct": 35, "max_sector_pct": 50, "min_cash_pct": 0,
                     "cash_target_low": 0, "cash_target_high": 100, "cash_record_only": True}
            stdout = StringIO()
            with (patch.object(sys, "argv", ["qq_update_portfolio.py", "--portfolio", str(path)]),
                  patch.object(q, "parse_portfolio", return_value=portfolio),
                  patch.object(q, "fetch_qq_data", return_value={}),
                  patch.object(q, "calculate", return_value=calc),
                  patch.object(q, "load_constraints", return_value=rules),
                  redirect_stdout(stdout), redirect_stderr(StringIO())):
                q.main()
            self.assertIn("现金：仅记账", stdout.getvalue())
            self.assertNotIn("现金 >=0%", stdout.getvalue())

    def test_write_aborts_before_mutating_portfolio_when_caps_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PORTFOLIO.md"
            original = "## 当前持仓\n原样保持\n"
            path.write_text(original, encoding="utf-8")
            portfolio, calc, _ = _fixture()
            portfolio["holdings"] = calc["holdings"]
            with (patch.object(q, "USER_PATH", Path(tmp) / "USER.md"),
                  patch.object(sys, "argv", ["qq_update_portfolio.py", "--write", "--portfolio", str(path)]),
                  patch.object(q, "parse_portfolio", return_value=portfolio),
                  patch.object(q, "fetch_qq_data", return_value={}),
                  patch.object(q, "calculate", return_value=calc),
                  redirect_stdout(StringIO()), redirect_stderr(StringIO())):
                with self.assertRaisesRegex(FileNotFoundError, "USER.md"):
                    q.main()
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
