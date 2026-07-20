import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from investment_data_adapter import Envelope
from valuation_snapshot import _history_metrics


def envelope(observations, first, last):
    start = date.fromisoformat(first)
    bars = [
        {"date": (start + timedelta(days=index * ((date.fromisoformat(last) - start).days / max(observations - 1, 1)))).isoformat(), "close": index + 1}
        for index in range(observations)
    ]
    return Envelope(
        command="daily", status="ok", symbol={"input": "TEST", "code": "TEST", "market": "us"},
        data_as_of=last, sources=[], gaps=[], notes=[], data={"daily": bars},
        window={"requested": "5y", "observations": observations, "first_date": first, "last_date": last},
    )


class SnapshotHistoryTest(unittest.TestCase):
    def test_twenty_observations_do_not_create_long_metrics(self):
        metrics, gaps = _history_metrics(envelope(20, "2026-01-01", "2026-01-28"))
        self.assertIsNone(metrics["position_in_52w_range_pct"])
        self.assertIsNone(metrics["return_250d_pct"])
        self.assertIsNone(metrics["price_percentile_5y_proxy"])
        self.assertEqual(len(gaps), 3)

    def test_complete_five_year_history_creates_long_metrics(self):
        metrics, gaps = _history_metrics(envelope(1001, "2021-01-01", "2026-01-05"))
        self.assertIsNotNone(metrics["position_in_52w_range_pct"])
        self.assertIsNotNone(metrics["return_250d_pct"])
        self.assertIsNotNone(metrics["price_percentile_5y_proxy"])
        self.assertEqual(gaps, [])


if __name__ == "__main__":
    unittest.main()
