import sys
import tempfile
import types
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
