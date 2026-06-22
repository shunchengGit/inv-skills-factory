#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""知识库搜索工具：支持标题、内容、标签多维度搜索。

用法:
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_search.py <query>
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_search.py "python async" --category programming
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_search.py "python async" --limit 10
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import parse_index, search_entries

KNOWLEDGE_DIR = Path.home() / ".knowledge"


def cmd_search(query: str, category: str | None = None, limit: int = 20) -> dict:
    """搜索知识库条目。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    results = search_entries(KNOWLEDGE_DIR, query)

    # 按分类过滤
    if category:
        results = [r for r in results if r["category"] == category]

    total = len(results)
    results = results[:limit]

    return {
        "success": True,
        "query": query,
        "total": total,
        "returned": len(results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="知识库搜索工具")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--category", help="限制搜索分类")
    parser.add_argument("--limit", type=int, default=20, help="返回结果数量限制（默认 20）")
    args = parser.parse_args()

    result = cmd_search(args.query, category=args.category, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
