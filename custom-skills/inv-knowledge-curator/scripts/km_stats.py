#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""知识库统计工具：输出知识库整体统计信息，含 OKF type 分布。

用法:
  uv run km_stats.py
  uv run km_stats.py --json
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import parse_index, _read_frontmatter

KNOWLEDGE_DIR = Path.home() / ".knowledge"


def cmd_stats() -> dict:
    """统计知识库信息。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    categories, _ = parse_index(KNOWLEDGE_DIR)

    all_entries: list[dict] = []
    type_counts: Counter = Counter()
    tag_counts: Counter = Counter()
    timestamps: list[str] = []
    with_resource = 0
    without_resource = 0

    for cat, entries in categories.items():
        for entry in entries:
            file_path = KNOWLEDGE_DIR / entry["path"]
            fm = _read_frontmatter(file_path) if file_path.exists() else {}

            entry_type = fm.get("type") or "Unknown"
            type_counts[entry_type] += 1

            entry_tags = fm.get("tags", "")
            if isinstance(entry_tags, str):
                entry_tags = [t.strip().strip("\"'") for t in entry_tags.strip("[]").split(",") if t.strip()]
            for t in entry_tags:
                tag_counts[t] += 1

            ts = fm.get("timestamp", "")
            if ts:
                timestamps.append(ts[:10])  # date part

            if fm.get("resource"):
                with_resource += 1
            else:
                without_resource += 1

            all_entries.append({
                "title": entry["title"],
                "path": entry["path"],
                "category": cat,
                "type": entry_type,
                "description": fm.get("description", ""),
                "timestamp": ts,
                "mtime": file_path.stat().st_mtime if file_path.exists() else 0,
            })

    # 按 mtime 排序
    all_entries.sort(key=lambda x: x["mtime"], reverse=True)

    # 分类统计
    cat_stats = {}
    for cat, entries in categories.items():
        cat_types = Counter()
        for e in entries:
            file_path = KNOWLEDGE_DIR / e["path"]
            fm = _read_frontmatter(file_path) if file_path.exists() else {}
            cat_types[fm.get("type") or "Unknown"] += 1
        cat_stats[cat] = {
            "count": len(entries),
            "types": dict(cat_types),
        }

    # 时间范围
    earliest = min(ts for ts in timestamps) if timestamps else None
    latest = max(ts for ts in timestamps) if timestamps else None

    return {
        "success": True,
        "total_entries": len(all_entries),
        "total_categories": len(categories),
        "categories": cat_stats,
        "type_distribution": dict(type_counts),
        "top_tags": dict(tag_counts.most_common(15)),
        "resource_coverage": {
            "with_resource": with_resource,
            "without_resource": without_resource,
            "coverage_pct": round(with_resource / max(1, with_resource + without_resource) * 100, 1),
        },
        "time_range": {"earliest": earliest, "latest": latest},
        "recent_imports": [
            {"title": e["title"], "category": e["category"], "type": e["type"], "timestamp": e["timestamp"]}
            for e in all_entries[:10]
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="知识库统计工具")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = cmd_stats()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if not result.get("success"):
            print(f"错误: {result['error']}")
            sys.exit(1)

        print("知识库统计")
        print("=" * 40)
        print(f"总条目: {result['total_entries']} | 分类: {result['total_categories']}")

        print(f"\n类型分布:")
        for t, c in result.get("type_distribution", {}).items():
            bar = "█" * min(30, c * 2)
            print(f"  {t:<12s} {c:>3d}  {bar}")

        print(f"\n分类分布:")
        for cat, info in result.get("categories", {}).items():
            types_str = " ".join(f"{t}:{c}" for t, c in info["types"].items())
            print(f"  {cat:<16s} {info['count']:>3d} 条  ({types_str})")

        tr = result.get("time_range", {})
        if tr["earliest"]:
            print(f"\n时间范围: {tr['earliest']} ~ {tr['latest']}")

        rc = result.get("resource_coverage", {})
        print(f"来源覆盖: {rc['with_resource']}/{result['total_entries']} 有链接 ({rc['coverage_pct']}%)")

        top_tags = result.get("top_tags", {})
        if top_tags:
            print(f"\n热门标签:")
            for tag, count in list(top_tags.items())[:10]:
                print(f"  #{tag}: {count}")

        print(f"\n最近导入:")
        for e in result["recent_imports"]:
            print(f"  [{e['type']}] {e['title']} ({e['category']})")

    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
