#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""将旧格式文章（assist/article.py 产出）迁移为 knowledge-mgr 标准格式。

用法:
  uv run custom-skills/general/knowledge-mgr/scripts/km_migrate_articles.py <目录>
  uv run custom-skills/general/knowledge-mgr/scripts/km_migrate_articles.py ~/.knowledge/ai-engineering
"""

import re
import sys
from datetime import date
from pathlib import Path


KNOWLEDGE_DIR = Path.home() / ".knowledge"
INDEX_FILE = "Index.md"


def parse_old_format(content: str) -> dict:
    """从旧格式提取元数据。"""
    meta = {}
    for line in content.splitlines():
        m = re.match(r"> \*\*(\w+)\*\*:\s*(.+)", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if key == "URL":
                meta["url"] = val
            elif key == "抓取时间":
                meta["imported"] = val[:10]
            elif key == "标签":
                meta["tags"] = [t.strip() for t in val.split(",") if t.strip()]
        if line.startswith("# ") and "title" not in meta:
            meta["title"] = line[2:].strip()
    return meta


def build_new_format(old_content: str, category: str, meta: dict) -> str:
    """构建 knowledge-mgr 标准格式。"""
    url = meta.get("url", "")
    imported = meta.get("imported", date.today().isoformat())
    title = meta.get("title", "")

    # 提取原文内容（"## 原文内容" 之后的部分）
    body = ""
    m = re.search(r"^## 原文内容\s*\n(.*)", old_content, re.DOTALL | re.MULTILINE)
    if m:
        body = m.group(1).strip()
    else:
        # 没有原文内容标记，取备注之后的所有非元数据内容
        parts = re.split(r"^## ", old_content, flags=re.MULTILINE)
        if len(parts) > 1:
            body = parts[-1].strip()

    frontmatter = f"---\nurl: {url}\nimported: {imported}\ncategory: {category}\n---"

    return f"""{frontmatter}

# {title}

## 摘要
<!-- AI 待填充 -->

## 关键要点
<!-- AI 待填充 -->

## 原文内容

{body}
"""


def update_index(category: str, title: str, rel_path: str, url: str) -> None:
    """更新 Index.md：在对应 category 下追加条目。"""
    index_path = KNOWLEDGE_DIR / INDEX_FILE

    if not index_path.exists():
        index_path.write_text("# Knowledge Index\n", encoding="utf-8")

    lines = index_path.read_text(encoding="utf-8").splitlines()

    cat_header = f"## {category}"
    entry_line = f"- [{title}]({rel_path}) — {url}"

    # 检查是否已存在
    for line in lines:
        if rel_path in line and url in line:
            return  # 已注册，跳过

    cat_line_idx = None
    for i, line in enumerate(lines):
        if line.strip() == cat_header:
            cat_line_idx = i
            break

    if cat_line_idx is not None:
        insert_idx = cat_line_idx + 1
        while insert_idx < len(lines) and lines[insert_idx].startswith("- "):
            insert_idx += 1
        lines.insert(insert_idx, entry_line)
    else:
        # 新建 category section
        last_section_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("## "):
                last_section_idx = i
        insert_idx = last_section_idx + 1
        while insert_idx < len(lines) and not lines[insert_idx].startswith("## "):
            insert_idx += 1
        if insert_idx < len(lines) and lines[insert_idx - 1] != "":
            lines.insert(insert_idx, "")
            insert_idx += 1
        lines.insert(insert_idx, cat_header)
        lines.insert(insert_idx + 1, entry_line)

    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def migrate_dir(target_dir: Path, category: str | None = None) -> dict:
    """扫描目录，逐个迁移旧格式文章。"""
    if not target_dir.exists():
        return {"success": False, "error": f"目录不存在: {target_dir}"}

    cat = category or target_dir.name
    converted = 0
    skipped = 0

    for md_file in sorted(target_dir.glob("*.md")):
        if md_file.name == INDEX_FILE:
            continue

        content = md_file.read_text(encoding="utf-8")

        # 已有 YAML frontmatter → 跳过
        if content.startswith("---"):
            skipped += 1
            continue

        meta = parse_old_format(content)
        new_content = build_new_format(content, cat, meta)
        md_file.write_text(new_content, encoding="utf-8")

        # 注册到 Index.md
        title = meta.get("title", md_file.stem)
        url = meta.get("url", "")
        rel_path = f"{cat}/{md_file.name}"
        update_index(cat, title, rel_path, url)

        converted += 1
        print(f"  ✓ {md_file.name}")

    return {"success": True, "converted": converted, "skipped": skipped}


def main():
    if len(sys.argv) < 2:
        print("用法: python3 km_migrate_articles.py <目录>")
        sys.exit(1)

    target = Path(sys.argv[1])
    result = migrate_dir(target)
    print(f"\n转换: {result.get('converted', 0)}, 跳过: {result.get('skipped', 0)}")
    if not result["success"]:
        print(f"错误: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
