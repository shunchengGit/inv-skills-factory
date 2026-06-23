#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""知识库统计工具：输出知识库整体统计信息，含 OKF v0.2 type/source_type 分布。

用法:
  uv run km_stats.py
  uv run km_stats.py --json
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import parse_index, _read_frontmatter, ENTRIES_DIR

_DEFAULT_KNOWLEDGE_DIR = Path.home() / ".inv-knowledge"


def _get_knowledge_dir() -> Path:
    import os
    env = os.environ.get("INV_KNOWLEDGE_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_KNOWLEDGE_DIR


KNOWLEDGE_DIR = _get_knowledge_dir()


def cmd_stats() -> dict:
    """统计知识库信息。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    entries, _ = parse_index(KNOWLEDGE_DIR)

    type_counts: Counter = Counter()
    source_type_counts: Counter = Counter()
    tag_counts: Counter = Counter()
    timestamps: list[str] = []
    with_resource = 0
    without_resource = 0

    for entry in entries:
        file_path = KNOWLEDGE_DIR / entry["path"]
        fm = _read_frontmatter(file_path) if file_path.exists() else {}

        etype = entry.get("type") or "Unknown"
        type_counts[etype] += 1

        stype = entry.get("source_type") or fm.get("source_type") or "unknown"
        source_type_counts[stype] += 1

        for t in entry.get("tags", []):
            tag_counts[t] += 1

        ts = entry.get("timestamp") or fm.get("timestamp", "")
        if ts:
            timestamps.append(ts[:10])

        if entry.get("resource") or fm.get("resource"):
            with_resource += 1
        else:
            without_resource += 1

    # 按 mtime 排序
    sorted_entries = sorted(entries, key=lambda e: (
        (KNOWLEDGE_DIR / e["path"]).stat().st_mtime
        if (KNOWLEDGE_DIR / e["path"]).exists() else 0
    ), reverse=True)

    # 时间范围
    earliest = min(ts for ts in timestamps) if timestamps else None
    latest = max(ts for ts in timestamps) if timestamps else None

    return {
        "success": True,
        "total_entries": len(entries),
        "type_distribution": dict(type_counts),
        "source_type_distribution": dict(source_type_counts),
        "top_tags": dict(tag_counts.most_common(15)),
        "resource_coverage": {
            "with_resource": with_resource,
            "without_resource": without_resource,
            "coverage_pct": round(with_resource / max(1, with_resource + without_resource) * 100, 1),
        },
        "time_range": {"earliest": earliest, "latest": latest},
        "recent_imports": [
            {"title": e["title"], "type": e["type"], "source_type": e["source_type"], "timestamp": e["timestamp"]}
            for e in sorted_entries[:10]
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="知识库统计工具 (OKF v0.2)")
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
        print(f"总条目: {result['total_entries']}")

        print(f"\n类型分布:")
        for t, c in result.get("type_distribution", {}).items():
            bar = "█" * min(30, c * 2)
            print(f"  {t:<14s} {c:>3d}  {bar}")

        print(f"\n来源分布:")
        for t, c in result.get("source_type_distribution", {}).items():
            icon = {"url": "🔗", "pdf": "📄", "note": "📝"}.get(t, "")
            bar = "█" * min(30, c * 2)
            print(f"  {icon} {t:<12s} {c:>3d}  {bar}")

        tr = result.get("time_range", {})
        if tr["earliest"]:
            print(f"\n时间范围: {tr['earliest']} ~ {tr['latest']}")

        rc = result.get("resource_coverage", {})
        print(f"来源覆盖: {rc['with_resource']}/{result['total_entries']} 有 resource ({rc['coverage_pct']}%)")

        top_tags = result.get("top_tags", {})
        if top_tags:
            print(f"\n热门标签:")
            for tag, count in list(top_tags.items())[:10]:
                print(f"  #{tag}: {count}")

        print(f"\n最近导入:")
        for e in result["recent_imports"]:
            print(f"  [{e['type']}] {e['title']} ({e['source_type']})")

    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
