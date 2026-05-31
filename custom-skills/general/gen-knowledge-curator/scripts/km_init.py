#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""初始化知识库：从远程仓库拉取并输出 Index 结构化数据。

用法:
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_init.py
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
from dotenv import load as _load_dotenv
_load_dotenv()
from git import is_repo, same_remote, clone, pull

REPO_URL = os.environ.get("KNOWLEDGE_REPO_URL", "git@github.com:shunchengGit/knowledge.git")
REPO_BRANCH = "master"
KNOWLEDGE_DIR = Path.home() / ".knowledge"
INDEX_DIR = "index"


def _migrate_if_needed() -> None:
    """旧 Index.md → index/*.md 自动迁移。"""
    old_index = KNOWLEDGE_DIR / "Index.md"
    index_dir = KNOWLEDGE_DIR / INDEX_DIR
    if not old_index.exists() or index_dir.exists():
        return

    index_dir.mkdir(parents=True, exist_ok=True)
    current_category = None
    current_file = None

    for line in old_index.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(.+)", line)
        if m:
            current_category = m.group(1).strip()
            current_file = index_dir / f"{current_category}.md"
            continue
        if current_file and line.startswith("- "):
            with open(current_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    old_index.rename(old_index.with_suffix(".md.bak"))


def init_repo() -> dict:
    """拉取或克隆知识库，返回操作结果。"""
    if not KNOWLEDGE_DIR.exists():
        return clone(REPO_URL, KNOWLEDGE_DIR, branch=REPO_BRANCH)

    if not is_repo(KNOWLEDGE_DIR):
        return {
            "success": False,
            "action": "none",
            "error": f"{KNOWLEDGE_DIR} 已存在但不是 git 仓库，请手动处理",
            "hint": f"备份后删除 {KNOWLEDGE_DIR}，或将其初始化为 git 仓库",
        }

    if not same_remote(KNOWLEDGE_DIR, REPO_URL):
        return {
            "success": False,
            "action": "none",
            "error": f"{KNOWLEDGE_DIR} 的 remote origin 不是 {REPO_URL}",
            "hint": "请手动调整 git remote 或备份后重新 init",
        }

    return pull(KNOWLEDGE_DIR, branch=REPO_BRANCH)


def parse_index() -> dict:
    """解析 index/*.md，返回结构化索引数据。"""
    _migrate_if_needed()
    index_dir = KNOWLEDGE_DIR / INDEX_DIR
    if not index_dir.exists():
        return {"categories": {}, "total_entries": 0}

    categories: dict[str, list[dict]] = {}
    for f in sorted(index_dir.glob("*.md")):
        category = f.stem
        entries: list[dict] = []
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^-\s+\[(.+?)\]\((.+?)\)\s*[—–-]\s*(.+)", line)
            if m:
                entries.append({
                    "title": m.group(1).strip(),
                    "path": m.group(2).strip(),
                    "url": m.group(3).strip(),
                })
        if entries:
            categories[category] = entries

    total = sum(len(e) for e in categories.values())
    return {"categories": categories, "total_entries": total}


def main():
    result = init_repo()

    if not result["success"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    # 拉取成功后输出 Index 数据
    index_data = parse_index()
    output = {
        **result,
        "index": index_data,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
