import argparse
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
SHARED = SKILL.parent / "_shared"
sys.path[:0] = [str(SCRIPTS), str(SHARED)]


class BatchStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["INV_KNOWLEDGE_ROOT"] = self.tmp.name
        self.root = Path(self.tmp.name)
        (self.root / "entries").mkdir(parents=True)
        (self.root / "res").mkdir(parents=True)
        sys.modules.pop("km_import", None)
        self.imp = importlib.import_module("km_import")
        self.imp.KNOWLEDGE_DIR = self.root

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("INV_KNOWLEDGE_ROOT", None)

    def test_batch_store_uses_store_pipeline(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps([
            {
                "title": "批量条目A",
                "resource": "res/Acme/a.pdf",
                "content": "## 摘要\n这是内容A。\n\n## 关键要点\n- 要点",
                "source_type": "pdf",
                "type": "Analysis",
                "description": "内容A描述",
                "tags": ["a"],
                "min_content_length": 1,
            }
        ]), encoding="utf-8")

        with patch.object(self.imp, "_git_sync", return_value={"success": True}):
            result = self.imp.cmd_batch_store(argparse.Namespace(
                manifest=str(manifest),
                dir=None,
                resource="res/Acme/a.pdf",
                source_type="pdf",
                type="Analysis",
                description="",
                tags="",
                min_content_length=1,
            ))

        self.assertTrue(result["success"])
        self.assertTrue(list((self.root / "entries").glob("*.md")))


if __name__ == "__main__":
    unittest.main()
