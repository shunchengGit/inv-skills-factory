"""知识库共享工具：Index 解析、迁移、条目格式。

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
  from knowledge import parse_index, migrate_index, build_entry, slugify
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

ENTRY_LINE_RE = re.compile(r"^-\s+\[(.+?)\]\((.+?)\)\s*[—–-]\s*(.+)")
SECTION_RE = re.compile(r"^##\s+(.+)")


def migrate_index(knowledge_dir: Path, index_dir_name: str = "index") -> None:
    """旧 Index.md → index/*.md 自动迁移。"""
    old_index = knowledge_dir / "Index.md"
    index_dir = knowledge_dir / index_dir_name
    if not old_index.exists() or index_dir.exists():
        return

    index_dir.mkdir(parents=True, exist_ok=True)
    current_file = None

    for line in old_index.read_text(encoding="utf-8").splitlines():
        m = SECTION_RE.match(line)
        if m:
            current_file = index_dir / f"{m.group(1).strip()}.md"
            continue
        if current_file and line.startswith("- "):
            with open(current_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    old_index.rename(old_index.with_suffix(".md.bak"))


def parse_index(knowledge_dir: Path, index_dir_name: str = "index") -> tuple[dict[str, list[dict]], set[str]]:
    """解析 index/*.md → (categories, indexed_paths)。

    categories: {category: [{title, path, url}, ...]}
    indexed_paths: 所有被引用的相对路径集合
    """
    migrate_index(knowledge_dir, index_dir_name)
    index_dir = knowledge_dir / index_dir_name
    if not index_dir.exists():
        return {}, set()

    categories: dict[str, list[dict]] = {}
    indexed_paths: set[str] = set()

    for f in sorted(index_dir.glob("*.md")):
        category = f.stem
        entries: list[dict] = []
        for line in f.read_text(encoding="utf-8").splitlines():
            m = ENTRY_LINE_RE.match(line)
            if m:
                entry = {
                    "title": m.group(1).strip(),
                    "path": m.group(2).strip(),
                    "url": m.group(3).strip(),
                }
                entries.append(entry)
                indexed_paths.add(entry["path"])
        if entries:
            categories[category] = entries

    return categories, indexed_paths


def slugify(title: str, max_len: int = 80) -> str:
    """标题 → kebab-case slug。"""
    s = re.sub(r"[^\w一-鿿]+", "-", title.strip())
    s = s.strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "untitled"


def build_entry(title: str, url: str, category: str, content: str) -> str:
    """构建知识条目 markdown 内容。"""
    today = date.today().isoformat()
    return (
        f"---\n"
        f"url: {url}\n"
        f"imported: {today}\n"
        f"category: {category}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{content}\n"
    )
