#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""知识库搜索工具：支持标题、内容、标签多维度搜索。

用法:
  uv run km_search.py <query>
  uv run km_search.py "python async" --type Article
  uv run km_search.py "宁德时代" --tag fuyao-glass
  uv run km_search.py "估值" --source_type pdf
  uv run km_search.py "光伏" --limit 10
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import search_entries, get_all_tags, _search_res_files

_DEFAULT_KNOWLEDGE_DIR = Path.home() / ".inv-knowledge"


def _get_knowledge_dir() -> Path:
    env = os.environ.get("INV_KNOWLEDGE_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_KNOWLEDGE_DIR


KNOWLEDGE_DIR = _get_knowledge_dir()


def cmd_search(query: str, *,
               entry_type: str | None = None,
               tag: str | None = None,
               source_type: str | None = None,
               date_after: str | None = None,
               date_before: str | None = None,
               limit: int = 20) -> dict:
    """搜索知识库条目。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    results = search_entries(
        KNOWLEDGE_DIR, query,
        entry_type=entry_type,
        tag=tag,
        source_type=source_type,
        date_after=date_after,
        date_before=date_before,
    )

    total = len(results)
    top_results = results[:limit]

    # 类型分布
    type_dist: dict[str, int] = {}
    source_dist: dict[str, int] = {}
    for r in results:
        type_dist[r.get("type", "?")] = type_dist.get(r.get("type", "?"), 0) + 1
        source_dist[r.get("source_type", "?")] = source_dist.get(r.get("source_type", "?"), 0) + 1

    # 标签建议
    suggested_tags: list[str] = []
    if results:
        all_tags = get_all_tags(KNOWLEDGE_DIR)
        result_tags: set[str] = set()
        for r in results:
            result_tags.update(r.get("tags", []))
        for t, count in all_tags.most_common(30):
            if t not in result_tags and t not in (tag or ""):
                suggested_tags.append(t)
            if len(suggested_tags) >= 10:
                break

    # 最高分条目
    top_hit = top_results[0] if top_results else None

    # 搜索 res/ 下匹配的 PDF
    res_matches = _search_res_files(KNOWLEDGE_DIR, query)

    return {
        "success": True,
        "query": query,
        "total": total,
        "returned": len(top_results),
        "res_matches": len(res_matches) if res_matches else 0,
        "res_files": res_matches[:10],
        "summary": {
            "type_distribution": type_dist,
            "source_distribution": source_dist,
            "top_score": top_hit["score"] if top_hit else 0,
        } if top_hit else {},
        "filters": {"type": entry_type, "tag": tag, "source_type": source_type},
        "results": top_results,
        "suggested_tags": suggested_tags,
    }


def main():
    parser = argparse.ArgumentParser(description="知识库搜索工具 (OKF v0.2)")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--type", dest="entry_type", help="按 OKF type 过滤 (Article/Analysis/Synthesis/Reference/Note)")
    parser.add_argument("--tag", help="按标签过滤")
    parser.add_argument("--source_type", choices=("url", "pdf", "note"), help="按来源类型过滤")
    parser.add_argument("--after", help="过滤此日期之后的条目 (YYYY-MM-DD)")
    parser.add_argument("--before", help="过滤此日期之前的条目 (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=20, help="返回结果数量限制（默认 20）")
    args = parser.parse_args()

    result = cmd_search(
        args.query,
        entry_type=args.entry_type,
        tag=args.tag,
        source_type=args.source_type,
        date_after=args.after,
        date_before=args.before,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
