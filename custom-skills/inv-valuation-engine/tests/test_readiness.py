import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from investment_data_adapter import UnsupportedSchemaError, parse_all_components, parse_v1_envelope
from valuation_report import generate_report_from_snapshot, render_markdown, render_text
from valuation_snapshot import Snapshot


def gap(code="field_unavailable", field="metrics.pb", reason="missing"):
    return {"code": code, "field": field, "reason": reason, "retryable": False}


def snapshot(metrics, *, upstream="ok", gaps=None, fallback=False):
    return Snapshot(
        symbol="TEST",
        normalized_symbol="TEST",
        company_name="Example",
        currency="USD",
        market="US",
        data_time="2026-01-05",
        data_sources=[{"name": "fixture", "status": "ok", "fallback": fallback}],
        metrics=metrics,
        data_gaps=list(gaps or []),
        notes=[],
        upstream_status=upstream,
        history_window={"requested": "5y", "observations": 1001, "first_date": "2021-01-01", "last_date": "2026-01-05"},
        used_fallback=fallback,
    )


class AdapterTest(unittest.TestCase):
    def test_unknown_major_schema_is_rejected(self):
        with self.assertRaises(UnsupportedSchemaError):
            parse_v1_envelope({"schema_version": "2.0"})

    def test_all_components_are_required(self):
        payload = {
            "schema_version": "1.0", "command": "all", "status": "partial",
            "symbol": {"input": "TEST", "code": "TEST", "market": "us"},
            "data_as_of": None, "sources": [], "gaps": [gap()], "notes": [],
            "data": {"components": {"snapshot": {"status": "ok", "data": {}}}},
        }
        with self.assertRaisesRegex(ValueError, "missing all components"):
            parse_all_components(payload)


class ReadinessTest(unittest.TestCase):
    def test_upstream_failed_has_no_conclusion_or_action(self):
        report = generate_report_from_snapshot(snapshot({}, upstream="failed", gaps=[gap()]), "auto")
        self.assertEqual(report.valuation_status, "upstream_failed")
        self.assertIsNone(report.conclusion)
        self.assertIsNone(report.action_reference)

    def test_price_only_is_insufficient(self):
        report = generate_report_from_snapshot(snapshot({"current_price": 10.0}), "auto")
        self.assertEqual(report.valuation_status, "insufficient_for_valuation")
        self.assertIsNone(report.conclusion)
        self.assertIsNone(report.action_reference)
        self.assertTrue(any(item["code"] == "valuation_missing_core_anchor" for item in report.data_gaps))

    def test_partial_can_conclude_but_cannot_recommend_action(self):
        metrics = {
            "trailing_pe": 12.0,
            "forward_pe": 11.0,
            "pb": 1.2,
            "earnings_yield_pct": 8.33,
            "price_percentile_5y_proxy": 25.0,
        }
        report = generate_report_from_snapshot(snapshot(metrics, upstream="partial", gaps=[gap()]), "auto")
        self.assertEqual(report.valuation_status, "partial")
        self.assertIsNotNone(report.conclusion)
        self.assertIsNone(report.action_reference)

    def test_complete_data_can_produce_action(self):
        metrics = {
            "trailing_pe": 12.0,
            "forward_pe": 11.0,
            "pb": 1.2,
            "earnings_yield_pct": 8.33,
            "price_percentile_5y_proxy": 25.0,
        }
        report = generate_report_from_snapshot(snapshot(metrics), "auto")
        self.assertEqual(report.valuation_status, "ok")
        self.assertIsNotNone(report.conclusion)
        self.assertIsNotNone(report.action_reference)

    def test_unrateable_rendering_discloses_gaps_without_trade_action(self):
        report = generate_report_from_snapshot(snapshot({"current_price": 10.0}), "auto")
        for rendered in (render_text(report), render_markdown(report)):
            self.assertIn("数据不足，无法评级", rendered)
            self.assertIn("估值闸门未通过", rendered)
            for forbidden in ("逢低加仓", "分批减仓", "持有 / 观望"):
                self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()
