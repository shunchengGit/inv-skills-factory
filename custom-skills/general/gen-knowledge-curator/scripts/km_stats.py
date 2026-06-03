#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""知识库统计工具：输出知识库整体统计信息。

用法:
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_stats.py
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_stats.py --json
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import parse_index

KNOWLEDGE_DIR = Path.home() / ".knowledge"
INDEX_DIR = "index"


def cmd_stats() -> dict:
    """统计知识库信息。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    categories, _ = parse_index(KNOWLEDGE_DIR, INDEX_DIR)

    stats = {
        "success": True,
        "total_entries": 0,
        "total_categories": 0,
        "categories": {},
        "recent_imports": [],
    }

    all_entries = []
    for cat, entries in categories.items():
        stats["categories"][cat] = {
            "count": len(entries),
            "entries": [{"title": e["title"], "path": e["path"]} for e in entries],
        }
        stats["total_entries"] += len(entries)
        stats["total_categories"] += 1

        for entry in entries:
            all_entries.append({
                "title": entry["title"],
                "path": entry["path"],
                "category": cat,
            })

    # 按导入时间排序（基于文件修改时间）
    for entry in all_entries:
        file_path = KNOWLEDGE_DIR / entry["path"]
        if file_path.exists():
            entry["mtime"] = file_path.stat().st_mtime
        else:
            entry["mtime"] = 0

    all_entries.sort(key=lambda x: x["mtime"], reverse=True)
    stats["recent_imports"] = all_entries[:10]

    return stats


def main():
    parser = argparse.ArgumentParser(description="知识库统计工具")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    result = cmd_stats()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 人类可读格式
        if not result.get("success"):
            print(f"错误: {result['error']}")
            sys.exit(1)

        print(f"知识库统计")
        print(f"{'=' * 40}")
        print(f"总条目数: {result['total_entries']}")
        print(f"总分类数: {result['total_categories']}")
        print(f"\n分类分布:")
        for cat, info in result["categories"].items():
            print(f"  {cat}: {info['count']} 条")

        print(f"\n最近导入:")
        for entry in result["recent_imports"]:
            print(f"  {entry['title']} ({entry['category']})")

    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
