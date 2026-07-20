import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

import commands
from data_contract import validate_envelope


def daily_frame(observations: int, start: date = date(2021, 1, 1)) -> pd.DataFrame:
    return pd.DataFrame({
        "date": [start + timedelta(days=index * 2) for index in range(observations)],
        "close": [float(index + 1) for index in range(observations)],
    })


class CommandsContractTest(unittest.TestCase):
    def test_daily_five_year_is_not_truncated_to_twenty(self):
        frame = daily_frame(1001)
        with patch.object(commands, "fetch_a_daily", return_value=frame) as fetch:
            payload = commands.cmd_daily("600000", "a", period="5y")
        validate_envelope(payload)
        fetch.assert_called_once_with("600000", n=None)
        self.assertGreater(len(payload["data"]["daily"]), 900)
        self.assertEqual(payload["window"]["observations"], len(payload["data"]["daily"]))
        self.assertGreater(len(payload["data"]["daily"]), 20)

    def test_daily_limit_is_explicit(self):
        frame = daily_frame(100)
        with patch.object(commands, "fetch_a_daily", return_value=frame):
            payload = commands.cmd_daily("600000", "a", period="1y", limit=20)
        self.assertEqual(len(payload["data"]["daily"]), 20)
        self.assertEqual(payload["window"]["observations"], 20)

    def test_a_share_period_filters_actual_date_range(self):
        frame = daily_frame(400, date(2024, 1, 1))
        with patch.object(commands, "fetch_a_daily", return_value=frame):
            one_month = commands.cmd_daily("600000", "a", period="1mo")
            one_year = commands.cmd_daily("600000", "a", period="1y")
        self.assertLess(one_month["window"]["observations"], one_year["window"]["observations"])
        self.assertLessEqual(
            (pd.Timestamp(one_month["window"]["last_date"]) - pd.Timestamp(one_month["window"]["first_date"])).days,
            32,
        )

    def test_a_share_snapshot_provides_standard_fundamentals(self):
        raw = {
            "_command": "snapshot_a", "code": "600000", "name": "示例银行", "industry": "银行",
            "daily": [{"date": "2026-01-05", "close": 10.0}],
            "financial": {"销售毛利率": "45%", "销售净利率": "20%", "净资产收益率": "12%"},
            "valuation": {"pe_ttm": 6.5, "pb": 0.7}, "sina": {}, "description": "示例",
        }
        with patch.object(commands, "_raw_snapshot_a", return_value=raw):
            payload = commands.cmd_snapshot_a("600000")
        fund = payload["data"]["fundamentals"]
        self.assertEqual(fund["pe_trailing"], 6.5)
        self.assertEqual(fund["gross_margin_pct"], 45.0)
        self.assertEqual(fund["roe_pct"], 12.0)

    def test_hk_daily_uses_sina_dataframe_without_boolean_evaluation(self):
        frame = daily_frame(30)
        with (
            patch.object(commands, "fetch_yahoo_history", return_value=None),
            patch.object(commands, "fetch_hk_sina_daily", return_value=frame),
            patch.object(commands, "fetch_hk_daily_akshare") as akshare,
        ):
            payload = commands.cmd_daily("0001", "hk", period="1y")
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(len(payload["data"]["daily"]), 30)
        self.assertTrue(payload["sources"][1]["fallback"])
        akshare.assert_not_called()

    def test_etf_snapshot_preserves_nav_contract(self):
        with (
            patch.object(commands, "fetch_etf_name", return_value={"name": "示例 ETF", "category": "宽基"}),
            patch.object(commands, "fetch_etf_daily", return_value=daily_frame(5)),
            patch.object(commands, "fetch_etf_nav", return_value={
                "latest": 1.02,
                "date": "2026-01-05",
                "acc_nav": 1.3,
                "premium_pct": -0.01,
                "premium_label": "平价",
            }),
        ):
            payload = commands.cmd_snapshot_etf("510000")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["nav"]["latest"], 1.02)
        self.assertEqual(payload["data"]["nav"]["date"], "2026-01-05")

    def test_all_has_only_three_components_and_partial_status(self):
        snapshot = commands.make_envelope(
            "snapshot", "ok", commands.make_symbol("600000", "600000", "a"), {"name": "示例"}
        )
        failed = commands.make_envelope(
            "financial", "failed", commands.make_symbol("600000", "600000", "a"), {},
            gaps=[commands.make_gap("provider_unavailable", "data", "unavailable")],
        )
        financials = commands.make_envelope(
            "financials", "ok", commands.make_symbol("600000", "600000", "a"), {"income_stmt": []}
        )
        with (
            patch.object(commands, "cmd_snapshot_a", return_value=snapshot),
            patch.object(commands, "cmd_financial", return_value=failed),
            patch.object(commands, "cmd_financials", return_value=financials),
        ):
            payload = commands.cmd_all("600000", "a")
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(
            set(payload["data"]["components"]),
            {"snapshot", "financial", "financials"},
        )
        self.assertNotIn("daily", payload["data"]["components"])
        self.assertNotIn("announcements", payload["data"]["components"])
        self.assertNotIn("relations", payload["data"]["components"])


if __name__ == "__main__":
    unittest.main()
