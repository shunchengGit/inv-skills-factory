"""Legacy text rendering must not mislabel industry members."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render import print_text


class RenderSemanticsTest(unittest.TestCase):
    def test_legacy_relations_labels_industry_constituents(self):
        text = print_text({"_command": "relations", "code": "600519", "relations": [{"code": "000858", "name": "五粮液"}]})
        self.assertIn("同行业板块成分股", text)
        self.assertIn("000858 五粮液", text)
        self.assertNotIn("调研", text)

    def test_legacy_empty_relations_does_not_claim_no_research_events(self):
        text = print_text({"_command": "relations", "code": "600519", "relations": []})
        self.assertIn("暂无同行业成分股数据", text)
