import argparse
import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch as mock_patch
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
SHARED = SKILL.parent / "_shared"
sys.path[:0] = [str(SCRIPTS), str(SHARED)]


class TempKnowledgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["INV_KNOWLEDGE_ROOT"] = self.tmp.name
        self.root = Path(self.tmp.name)
        (self.root / "entries").mkdir()
        (self.root / "res" / "Acme").mkdir(parents=True)
        for name in ("knowledge", "km_lint", "km_import"):
            sys.modules.pop(name, None)
        self.knowledge = importlib.import_module("knowledge")
        self.lint = importlib.import_module("km_lint")
        self.imp = importlib.import_module("km_import")
        # unittest keeps imported modules between methods; pin globals to this fixture.
        setattr(self.lint, "KNOWLEDGE_DIR", self.root)
        setattr(self.imp, "KNOWLEDGE_DIR", self.root)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("INV_KNOWLEDGE_ROOT", None)

    def write_entry(self, name="entry.md", resource="res/Acme/report.pdf", body="## 摘要\n足够长的摘要内容，用于验证知识库条目。\n\n## 关键要点\n- 要点一\n- 要点二\n\n## 关联\n- [坏链](entries/missing.md)\n"):
        text = self.knowledge.build_entry(
            title='Acme: "Q1" #review',
            description='收入 $10m: 增长 20%',
            resource=resource,
            content="# 标题\n\n" + body,
            entry_type="Analysis",
            source_type="pdf",
            tags=["acme", "2026-Q1"],
        )
        p = self.root / "entries" / name
        p.write_text(text, encoding="utf-8")
        self.knowledge.regenerate_index(self.root)
        return p

    def test_pdf_file_resource_is_not_reported_missing(self):
        (self.root / "res" / "Acme" / "report.pdf").write_bytes(b"pdf")
        self.write_entry()
        issues = self.lint.check_pdf_entry_pairing()
        self.assertFalse([x for x in issues if x.get("issue") == "pdf_resource_missing"], issues)

    def test_multiple_pdf_resources_are_checked_individually(self):
        for n in ("a.pdf", "b.pdf"):
            (self.root / "res" / "Acme" / n).write_bytes(b"pdf")
        self.write_entry(resource="res/Acme/a.pdf, res/Acme/b.pdf")
        issues = self.lint.check_pdf_entry_pairing()
        self.assertFalse([x for x in issues if x.get("issue") == "pdf_resource_missing"], issues)

    def test_fix_dead_links_edits_source_not_index(self):
        p = self.write_entry()
        before_index = (self.root / "entries" / "index.md").read_text(encoding="utf-8")
        dead = [{"source": "entries/entry.md", "target": "entries/missing.md", "title": "Acme"}]
        actions = self.lint.fix_dead_links(dead)
        self.assertNotIn("entries/missing.md", p.read_text(encoding="utf-8"))
        self.assertEqual(before_index, (self.root / "entries" / "index.md").read_text(encoding="utf-8"))
        self.assertEqual(actions[0]["action"], "removed_dead_link")

    def test_frontmatter_special_characters_round_trip(self):
        p = self.write_entry()
        fm = self.knowledge._read_frontmatter(p)
        self.assertEqual(fm["title"], 'Acme: "Q1" #review')
        self.assertEqual(fm["description"], "收入 $10m: 增长 20%")
        self.assertEqual(fm["tags"], ["acme", "2026-Q1"])
        self.assertTrue(self.knowledge.validate_okf(p)["valid"])

    def test_archive_duplicate_keeps_source_by_default(self):
        src = self.root / "download.pdf"
        src.write_bytes(b"same")
        dst = self.root / "res" / "Acme" / "download.pdf"
        dst.write_bytes(b"same")
        result = self.imp._archive_file(src, "Acme")
        self.assertEqual(result.resolve(), dst.resolve())
        self.assertTrue(src.exists())

    def test_store_updates_log_before_git_sync(self):
        seen = {}
        def fake_sync(root, message, branch=None):
            seen["log_exists"] = (Path(root) / "log.md").exists()
            seen["log_text"] = (Path(root) / "log.md").read_text(encoding="utf-8")
            return {"success": True, "files_changed": "ok"}
        with mock_patch.object(self.imp, "_git_sync", side_effect=fake_sync):
            result = self.imp.cmd_store(
                "季度: 复盘", "manual", "# 季度复盘\n\n## 摘要\n这是三句完整摘要。第二句包含数据10%。第三句给出结论。\n\n## 关键要点\n- 数据10%\n- 结论明确",
                source_type="note", entry_type="Note", description="收入增长10%: 结论明确", min_content_length=1,
            )
        self.assertTrue(result["success"], result)
        self.assertTrue(seen["log_exists"])
        self.assertIn("季度: 复盘", seen["log_text"])

    def test_res_returns_failure_when_no_valid_input(self):
        args = argparse.Namespace(file=[str(self.root / "missing.pdf")], target="Acme", pages="edges", first_n=3, max_chars=1000, max_pages=10)
        self.assertNotEqual(self.imp.cmd_res(args), 0)

    def test_target_path_traversal_is_rejected(self):
        src = self.root / "report.pdf"
        src.write_bytes(b"pdf")
        with self.assertRaises(ValueError):
            self.imp._archive_file(src, "../../escaped")
        self.assertTrue(src.exists())

    def test_tag_path_traversal_is_rejected(self):
        self.write_entry()
        p = self.root / "entries" / "entry.md"
        text = p.read_text(encoding="utf-8").replace("- acme", "- ../../escaped")
        p.write_text(text, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.knowledge.regenerate_tag_indexes(self.root)
        self.assertFalse((self.root / "escaped.md").exists())

    def test_graph_template_uses_dom_text_for_tags_and_legend(self):
        viz = importlib.import_module("km_visualize")
        template = viz._TEMPLATE
        self.assertNotIn("legend.innerHTML+=", template)
        self.assertNotIn("tagsEl.innerHTML=d.tags", template)

    def test_graph_has_no_cdn_runtime_dependency(self):
        viz = importlib.import_module("km_visualize")
        self.assertNotIn("cdn.jsdelivr.net", viz._TEMPLATE)
        self.assertIn("__CYTOSCAPE_JS__", viz._TEMPLATE)


if __name__ == "__main__":
    unittest.main()
