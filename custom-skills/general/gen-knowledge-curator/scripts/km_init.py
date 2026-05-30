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
import re
import subprocess
import sys
from pathlib import Path

REPO_URL = "git@github.com:shunchengGit/knowledge.git"
REPO_BRANCH = "master"
KNOWLEDGE_DIR = Path.home() / ".knowledge"
INDEX_FILE = "Index.md"


def _run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _same_remote(path: Path) -> bool:
    r = _run_git(["remote", "get-url", "origin"], cwd=path)
    if r.returncode != 0:
        return False
    return r.stdout.strip() == REPO_URL


def init_repo() -> dict:
    """拉取或克隆知识库，返回操作结果。"""
    if not KNOWLEDGE_DIR.exists():
        # 首次：clone
        r = _run_git(["clone", "-b", REPO_BRANCH, REPO_URL, str(KNOWLEDGE_DIR)])
        if r.returncode != 0:
            err = r.stderr.strip()
            if "Could not read from remote" in err or "Permission denied" in err:
                hint = "请检查 SSH key 配置：ssh -T git@github.com"
            elif "Repository not found" in err or "not found" in err.lower():
                hint = f"远程仓库不存在，请确认 {REPO_URL} 是否已创建"
            else:
                hint = "网络连接失败，请检查网络或代理设置"
            return {
                "success": False,
                "action": "clone",
                "error": err[:500],
                "hint": hint,
            }
        return {"success": True, "action": "clone"}

    if not _is_git_repo(KNOWLEDGE_DIR):
        return {
            "success": False,
            "action": "none",
            "error": f"{KNOWLEDGE_DIR} 已存在但不是 git 仓库，请手动处理",
            "hint": f"备份后删除 {KNOWLEDGE_DIR}，或将其初始化为 git 仓库",
        }

    if not _same_remote(KNOWLEDGE_DIR):
        return {
            "success": False,
            "action": "none",
            "error": f"{KNOWLEDGE_DIR} 的 remote origin 不是 {REPO_URL}",
            "hint": "请手动调整 git remote 或备份后重新 init",
        }

    # 已有仓库：pull
    r = _run_git(["pull", "origin", REPO_BRANCH], cwd=KNOWLEDGE_DIR)
    if r.returncode != 0:
        return {
            "success": False,
            "action": "pull",
            "error": r.stderr.strip()[:500],
            "hint": "git pull 失败，可能需要手动解决冲突",
        }

    files_changed = r.stdout.strip() if r.stdout.strip() else ""
    return {"success": True, "action": "pull", "files_changed": files_changed}


def parse_index() -> dict:
    """解析 Index.md，返回结构化索引数据。"""
    index_path = KNOWLEDGE_DIR / INDEX_FILE

    if not index_path.exists():
        # 创建空模板
        index_path.write_text("# Knowledge Index\n", encoding="utf-8")
        return {"categories": {}, "total_entries": 0}

    content = index_path.read_text(encoding="utf-8")
    categories: dict[str, list[dict]] = {}
    current_category = None

    for line in content.splitlines():
        # 匹配 ## category 标题
        m = re.match(r"^##\s+(.+)", line)
        if m:
            current_category = m.group(1).strip()
            if current_category not in categories:
                categories[current_category] = []
            continue

        # 匹配条目行: - [标题](path) — url
        m = re.match(r"^-\s+\[(.+?)\]\((.+?)\)\s*[—–-]\s*(.+)", line)
        if m and current_category is not None:
            categories[current_category].append({
                "title": m.group(1).strip(),
                "path": m.group(2).strip(),
                "url": m.group(3).strip(),
            })

    total = sum(len(entries) for entries in categories.values())
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
