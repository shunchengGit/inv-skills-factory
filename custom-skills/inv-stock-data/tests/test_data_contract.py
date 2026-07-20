import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from data_contract import (
    aggregate_status,
    historical_eligibility,
    historical_gaps,
    make_component,
    make_envelope,
    make_gap,
    make_source,
    make_symbol,
    make_window,
    sanitize_json,
    validate_envelope,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class DataContractTest(unittest.TestCase):
    def test_market_fixtures_validate(self):
        names = (
            "snapshot_a_ok.json",
            "snapshot_hk_fallback.json",
            "snapshot_us_failed.json",
            "snapshot_etf_partial.json",
        )
        for name in names:
            with self.subTest(name=name):
                payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
                validate_envelope(payload)

    def test_non_finite_numbers_are_sanitized(self):
        self.assertEqual(sanitize_json({"value": float("nan"), "items": [float("inf")]}), {"value": None, "items": [None]})

    def test_unknown_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid status"):
            make_envelope(
                "snapshot",
                "unknown",
                make_symbol("TEST", "TEST", "us"),
                {},
            )

    def test_partial_requires_structured_gap(self):
        with self.assertRaisesRegex(ValueError, "require at least one gap"):
            make_envelope(
                "snapshot",
                "partial",
                make_symbol("TEST", "TEST", "us"),
                {"price": 1.0},
                sources=[make_source("fallback", "ok", fallback=True)],
            )

    def test_invalid_gap_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid gap entry"):
            make_envelope(
                "snapshot",
                "partial",
                make_symbol("TEST", "TEST", "us"),
                {"price": 1.0},
                gaps=[{"field": "data.fundamentals"}],
            )

    def test_failed_cannot_contain_domain_data(self):
        with self.assertRaisesRegex(ValueError, "must not contain domain data"):
            make_envelope(
                "snapshot",
                "failed",
                make_symbol("TEST", "TEST", "us"),
                {"name": "fabricated"},
                gaps=[make_gap("all_sources_failed", "data", "unavailable", retryable=True)],
            )

    def test_component_projection_and_aggregation(self):
        snapshot = make_envelope(
            "snapshot",
            "ok",
            make_symbol("600000", "600000", "a"),
            {"name": "示例"},
            sources=[make_source("sina", "ok")],
        )
        component = make_component(snapshot)
        self.assertEqual(component["status"], "ok")
        self.assertEqual(component["data"]["name"], "示例")
        self.assertEqual(aggregate_status(["ok", "failed", "ok"]), "partial")
        self.assertEqual(aggregate_status(["failed", "failed"]), "failed")
        self.assertEqual(aggregate_status(["ok", "ok"]), "ok")

    def test_twenty_observations_block_long_horizon_metrics(self):
        window = make_window("5y", 20, "2026-01-01", "2026-01-28")
        self.assertEqual(
            historical_eligibility(window),
            {"52w": False, "250d_return": False, "5y_percentile": False},
        )
        self.assertEqual(len(historical_gaps(window)), 3)

    def test_complete_five_year_window_allows_long_horizon_metrics(self):
        window = make_window("5y", 1250, "2021-01-04", "2026-01-05")
        self.assertEqual(
            historical_eligibility(window),
            {"52w": True, "250d_return": True, "5y_percentile": True},
        )
        self.assertEqual(historical_gaps(window), [])


if __name__ == "__main__":
    unittest.main()
