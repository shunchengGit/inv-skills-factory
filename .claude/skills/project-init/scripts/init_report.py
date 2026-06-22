#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""初始化研报库：从远程仓库拉取并输出 Index 统计。

用法:
  uv run .claude/skills/project-init/scripts/init_report.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "custom-skills" / "_shared"))
from dotenv import load as _load_dotenv
_load_dotenv()
from git import is_repo, same_remote, clone, pull

REPO_URL = os.environ.get("INV_REPORT_REPO_URL", "git@github.com:shunchengGit/inv-report.git")
REPO_BRANCH = "master"
_DEFAULT_REPORT_DIR = Path.home() / ".inv-report"


def _get_report_dir() -> Path:
    env = os.environ.get("RESEARCH_PDF_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_REPORT_DIR


REPORT_DIR = _get_report_dir()


def init_repo() -> dict:
    """拉取或克隆研报库，返回操作结果。"""
    if not REPORT_DIR.exists():
        return clone(REPO_URL, REPORT_DIR, branch=REPO_BRANCH)

    if not is_repo(REPORT_DIR):
        return {
            "success": False,
            "action": "none",
            "error": f"{REPORT_DIR} 已存在但不是 git 仓库，请手动处理",
            "hint": f"备份后删除 {REPORT_DIR}，或将其初始化为 git 仓库",
        }

    if not same_remote(REPORT_DIR, REPO_URL):
        return {
            "success": False,
            "action": "none",
            "error": f"{REPORT_DIR} 的 remote origin 不是 {REPO_URL}",
            "hint": "请手动调整 git remote 或备份后重新 init",
        }

    return pull(REPORT_DIR, branch=REPO_BRANCH)


def read_index_stats(report_dir: Path) -> dict:
    """读取 Index.md 并统计子文件夹数。"""
    index_path = report_dir / "Index.md"
    if not index_path.exists():
        return {"folders": 0, "has_index": False}

    # 简单统计：按 ## 开头的标题算子文件夹
    folders: list[str] = []
    for line in index_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            name = stripped[3:].strip()
            if name and name not in ("目录", "索引", "Index", "Table of Contents"):
                folders.append(name)

    return {"folders": len(folders), "folder_names": folders, "has_index": True}


def main():
    result = init_repo()
    if not result["success"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    stats = read_index_stats(REPORT_DIR)
    print(json.dumps({
        **result,
        "index": stats,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
