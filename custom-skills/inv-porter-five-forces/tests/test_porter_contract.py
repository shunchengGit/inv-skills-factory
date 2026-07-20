import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
STOCK_FIXTURES = SKILL.parent / "inv-stock-data" / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import five_forces_snapshot as porter
from five_forces_snapshot import build_pre_scoring
from porter_data_adapter import UnsupportedSchemaError, adapt_snapshot_envelope

FORCES = ("supplier_power", "buyer_power", "entry_threat", "substitute_threat", "rivalry")


class PorterAdapterTest(unittest.TestCase):
    def fixture(self, name):
        return json.loads((STOCK_FIXTURES / name).read_text(encoding="utf-8"))

    def test_a_share_maps_standard_fields(self):
        payload = self.fixture("snapshot_a_ok.json")
        facts = adapt_snapshot_envelope(payload)
        self.assertEqual(facts.company_name, "示例银行")
        self.assertEqual(facts.market, "A-share")
        self.assertEqual(facts.currency, "CNY")
        self.assertEqual(facts.upstream["status"], "ok")
        self.assertEqual(facts.fundamentals["roe_pct"], 12.0)

    def test_hk_fallback_preserves_sources_and_gaps(self):
        facts = adapt_snapshot_envelope(self.fixture("snapshot_hk_fallback.json"))
        self.assertEqual(facts.price, 42.0)
        self.assertEqual(facts.upstream["status"], "partial")
        self.assertTrue(any(item["fallback"] for item in facts.upstream["sources"]))
        self.assertTrue(facts.upstream["gaps"])

    def test_unknown_schema_is_rejected_without_legacy_guessing(self):
        payload = self.fixture("snapshot_a_ok.json")
        payload["schema_version"] = "2.0"
        with self.assertRaises(UnsupportedSchemaError):
            adapt_snapshot_envelope(payload)


class EvidenceReadinessTest(unittest.TestCase):
    def score(self, facts, upstream="ok"):
        return build_pre_scoring(
            financial_metrics={},
            industry_benchmark={"matched": False},
            five_forces_facts=facts,
            event_titles=[],
            event_time_map=None,
            data_gaps=[],
            upstream_status=upstream,
        )

    def test_no_evidence_has_nullable_scores_and_total(self):
        result = self.score({key: [] for key in FORCES})
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["total_score"])
        for item in result["dimensions"].values():
            self.assertIsNone(item["score"])
            self.assertEqual(item["evidence_count"], 0)
            self.assertTrue(item["gaps"])

    def test_benchmark_alone_does_not_make_scores_ready(self):
        benchmark = {
            "matched": True,
            "benchmark": {key: 12 for key in FORCES} | {"total_score": 60},
        }
        result = build_pre_scoring({}, benchmark, {key: [] for key in FORCES}, [], None, [], "ok")
        self.assertIsNone(result["total_score"])

    def test_all_forces_require_six_evidence_items(self):
        facts = {key: [f"fact-{index}" for index in range(6)] for key in FORCES}
        result = self.score(facts)
        self.assertEqual(result["status"], "ok")
        self.assertIsNotNone(result["total_score"])
        self.assertTrue(all(item["score"] is not None for item in result["dimensions"].values()))

    def test_upstream_failed_blocks_scores_even_with_evidence(self):
        facts = {key: [f"fact-{index}" for index in range(6)] for key in FORCES}
        result = self.score(facts, upstream="failed")
        self.assertIsNone(result["total_score"])
        self.assertTrue(all(item["score"] is None for item in result["dimensions"].values()))

    def test_source_has_no_legacy_snapshot_paths(self):
        source = (SCRIPTS / "five_forces_snapshot.py").read_text(encoding="utf-8")
        for legacy in ('"quote"', '"yahoo_fundamentals"', '"stats_52w"', '"earnings"', '"news"'):
            self.assertNotIn(legacy, source)

    def test_fact_builder_can_reach_six_evidence_items(self):
        info = {
            "grossMargins": 45.0, "operatingMargins": 25.0, "profitMargins": 20.0,
            "revenueGrowth": 15.0, "returnOnEquity": 20.0,
            "marketCap": 1000000, "fullTimeEmployees": 10000, "industry": "software",
        }
        facts = porter.build_force_facts(
            "Example", "自研 品牌 渠道 平台 专利 认证 基础设施 核心", "US",
            info, {"ths_debt_asset_ratio_pct": 20},
            [porter.NewsItem("competition and price cut", None, None, None)],
            ["回购 提价 中标 订单 专利 认证 降价 价格战 扩产 替代 AI"],
            {"matched": True, "matched_industry": "软件 SaaS", "benchmark": {key: 12 for key in FORCES} | {"total_score": 60}},
        )
        self.assertTrue(any(len(items) >= 6 for items in facts.values()))

    def test_failed_subprocess_envelope_is_preserved(self):
        failed = json.loads((STOCK_FIXTURES / "snapshot_us_failed.json").read_text(encoding="utf-8"))
        completed = subprocess.CompletedProcess(["uv"], 1, stdout=json.dumps(failed), stderr="")
        with patch.object(porter.subprocess, "run", return_value=completed):
            self.assertEqual(porter._call_cs_stock("snapshot", "TEST"), failed)

    def test_failed_snapshot_builds_structured_fact_sheet(self):
        failed = json.loads((STOCK_FIXTURES / "snapshot_us_failed.json").read_text(encoding="utf-8"))
        with patch.object(porter, "_call_cs_stock", return_value=failed):
            snapshot = porter.build_snapshot("TEST", "us")
        self.assertEqual(snapshot.upstream["status"], "failed")
        self.assertEqual(snapshot.pre_scoring["status"], "insufficient_evidence")
        self.assertIsNone(snapshot.pre_scoring["total_score"])


if __name__ == "__main__":
    unittest.main()
