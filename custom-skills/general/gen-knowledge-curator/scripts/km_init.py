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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
from dotenv import load as _load_dotenv
_load_dotenv()
from git import is_repo, same_remote, clone, pull
from knowledge import parse_index

REPO_URL = os.environ.get("KNOWLEDGE_REPO_URL", "git@github.com:shunchengGit/knowledge.git")
REPO_BRANCH = "master"
KNOWLEDGE_DIR = Path.home() / ".knowledge"
INDEX_DIR = "index"


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


def main():
    result = init_repo()
    if not result["success"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    categories, _indexed_paths = parse_index(KNOWLEDGE_DIR, INDEX_DIR)
    total = sum(len(e) for e in categories.values())
    print(json.dumps({
        **result,
        "index": {"categories": categories, "total_entries": total},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
