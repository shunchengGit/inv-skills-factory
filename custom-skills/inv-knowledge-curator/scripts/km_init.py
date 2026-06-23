#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""初始化知识库：从远程仓库拉取并输出条目列表。

用法:
  uv run km_init.py
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from dotenv import load as _load_dotenv
_load_dotenv()
from git import is_repo, same_remote, clone, pull

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import parse_index, ENTRIES_DIR

REPO_URL = os.environ.get("INV_KNOWLEDGE_REPO_URL", "git@github.com:shunchengGit/inv-knowledge.git")
REPO_BRANCH = "master"
_DEFAULT_KNOWLEDGE_DIR = Path.home() / ".inv-knowledge"


def _get_knowledge_dir() -> Path:
    env = os.environ.get("INV_KNOWLEDGE_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_KNOWLEDGE_DIR


KNOWLEDGE_DIR = _get_knowledge_dir()


def regenerate_res_index() -> dict:
    """扫描 res/ 目录，生成 res/index.md。"""
    res_dir = KNOWLEDGE_DIR / "res"
    if not res_dir.is_dir():
        return {"entries": 0}

    # 收集每个文件夹下的 PDF
    folders: dict[str, list[str]] = {}
    for f in sorted(res_dir.rglob("*.pdf")):
        if f.name.startswith("."):
            continue
        folder = f.parent.name if f.parent != res_dir else "_root"
        folders.setdefault(folder, []).append(f.name)

    if not folders:
        return {"entries": 0}

    lines = ["# res 资源索引\n"]
    for folder in sorted(folders.keys()):
        lines.append(f"## {folder}")
        for pdf_name in sorted(folders[folder]):
            lines.append(f"- [{pdf_name}]({folder}/{pdf_name})")
        lines.append("")

    idx_file = res_dir / "index.md"
    idx_file.write_text("\n".join(lines), encoding="utf-8")
    return {"entries": sum(len(v) for v in folders.values()), "folders": len(folders)}


def ensure_dirs() -> dict:
    """确保必要的目录结构存在。"""
    created = []
    for d in [
        KNOWLEDGE_DIR / ENTRIES_DIR,
        KNOWLEDGE_DIR / "res",
    ]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d.relative_to(KNOWLEDGE_DIR)))
    idx = regenerate_res_index()
    return {"created": created, "res_index": idx}


def init_repo() -> dict:
    """拉取或克隆知识库，返回操作结果。"""
    if not KNOWLEDGE_DIR.exists():
        result = clone(REPO_URL, KNOWLEDGE_DIR, branch=REPO_BRANCH)
        if result["success"]:
            dirs = ensure_dirs()
            result["dirs"] = dirs
        return result

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

    result = pull(KNOWLEDGE_DIR, branch=REPO_BRANCH)
    if result["success"]:
        dirs = ensure_dirs()
        result["dirs"] = dirs
    return result


def main():
    parser = argparse.ArgumentParser(description="初始化知识库：git clone/pull + 创建目录骨架")
    parser.parse_args()

    result = init_repo()
    if not result["success"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    entries, _indexed_paths = parse_index(KNOWLEDGE_DIR)
    print(json.dumps({
        **result,
        "entries": entries,
        "total_entries": len(entries),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
