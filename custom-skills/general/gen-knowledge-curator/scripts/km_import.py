#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31.0",
#   "html2text>=2024.2.26",
# ]
# ///
"""知识导入：URL 抓取 + 知识条目存储。

两个子命令：
  fetch  - 抓取 URL 内容（Firecrawl → pwright 兜底）
  store  - 存储知识条目到 ~/.knowledge + 更新 Index.md + git 同步

用法:
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_import.py fetch <url>
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_import.py store --title "标题" --category investing --url https://... --content <md>
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_import.py store --title "标题" --url https://... --content <md>  # 无 category → _unsorted
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from pwright import scrape_url as pwright_scrape_url

KNOWLEDGE_DIR = Path.home() / ".knowledge"
REPO_BRANCH = "master"
INDEX_FILE = "Index.md"
FIRECRAWL_URL = "http://localhost:3672/v1/scrape"


# ─── fetch 子命令 ─────────────────────────────────────────


def _firecrawl_scrape(url: str) -> dict | None:
    """Firecrawl adapter 抓取，返回 {title, content} 或 None。"""
    import requests

    try:
        r = requests.post(
            FIRECRAWL_URL,
            json={"url": url},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        data = r.json().get("data", {})
        content = data.get("markdown") or data.get("content", "")
        title = data.get("metadata", {}).get("title", "")
        if not content or len(content) < 500:
            return None
        # 检测 Cloudflare/反爬拦截页
        if "请稍候" in content or "Just a moment" in content or "Checking your browser" in content:
            return None
        return {"title": title, "content": content}
    except Exception:
        return None


def _pwright_scrape(url: str) -> dict | None:
    """Playwright 抓取兜底，返回 {title, content} 或 None。"""
    try:
        result = pwright_scrape_url(url)
    except RuntimeError:
        return None

    if result["success"] and result["markdown"] and len(result["markdown"].strip()) >= 100:
        return {"title": result["title"], "content": result["markdown"].strip()}
    return None


def cmd_fetch(url: str) -> dict:
    """抓取 URL 内容，Firecrawl 优先，pwright 兜底。"""
    # 1. Firecrawl
    result = _firecrawl_scrape(url)
    if result:
        return {
            "success": True,
            "source": "firecrawl",
            "title": result["title"],
            "content": result["content"],
            "url": url,
        }

    # 2. pwright 兜底
    result = _pwright_scrape(url)
    if result:
        return {
            "success": True,
            "source": "pwright",
            "title": result["title"],
            "content": result["content"],
            "url": url,
        }

    return {
        "success": False,
        "error": "Firecrawl 和 pwright_scrape 均失败",
        "url": url,
    }


# ─── store 子命令 ─────────────────────────────────────────


def _slugify(title: str) -> str:
    """标题 → kebab-case slug。"""
    # 保留中文、字母、数字；其他替换为 -
    s = re.sub(r"[^\w一-鿿]+", "-", title.strip())
    s = s.strip("-")
    # 中文不做转换，直接保留；过长截断
    if len(s) > 80:
        s = s[:80].rstrip("-")
    return s or "untitled"


def _build_entry_md(title: str, url: str, category: str, content: str) -> str:
    """构建知识条目 md 内容。"""
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


def _update_index(category: str, title: str, rel_path: str, url: str) -> None:
    """更新 Index.md：在对应 category 下追加条目。"""
    index_path = KNOWLEDGE_DIR / INDEX_FILE

    if not index_path.exists():
        index_path.write_text("# Knowledge Index\n", encoding="utf-8")

    lines = index_path.read_text(encoding="utf-8").splitlines()

    # 找到 ## <category> 的位置
    cat_header = f"## {category}"
    cat_line_idx = None
    for i, line in enumerate(lines):
        if line.strip() == cat_header:
            cat_line_idx = i
            break

    entry_line = f"- [{title}]({rel_path}) — {url}"

    if cat_line_idx is not None:
        # 在该 category 最后一个条目后插入
        insert_idx = cat_line_idx + 1
        while insert_idx < len(lines) and lines[insert_idx].startswith("- "):
            insert_idx += 1
        lines.insert(insert_idx, entry_line)
    else:
        # 新建 category section
        # 找到最后一个 ## 行的位置
        last_section_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("## "):
                last_section_idx = i
        # 找到该 section 结束位置（下一个 ## 或文件末尾）
        insert_idx = last_section_idx + 1
        while insert_idx < len(lines) and not lines[insert_idx].startswith("## "):
            insert_idx += 1
        # 如果文件末尾没有空行，加一个
        if insert_idx < len(lines) and lines[insert_idx - 1] != "":
            lines.insert(insert_idx, "")
            insert_idx += 1
        lines.insert(insert_idx, cat_header)
        lines.insert(insert_idx + 1, entry_line)

    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _git_sync(title: str, category: str) -> dict:
    """在 ~/.knowledge 中执行 git add + commit + push。"""
    r_add = subprocess.run(
        ["git", "add", "-A"],
        cwd=KNOWLEDGE_DIR,
        capture_output=True,
        text=True,
    )
    if r_add.returncode != 0:
        return {"success": False, "step": "add", "error": r_add.stderr.strip()[:300]}

    commit_msg = f"import: {title} → {category}/"
    r_commit = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=KNOWLEDGE_DIR,
        capture_output=True,
        text=True,
    )
    # nothing to commit 是正常情况
    if r_commit.returncode != 0 and "nothing to commit" not in r_commit.stdout:
        return {"success": False, "step": "commit", "error": r_commit.stderr.strip()[:300]}

    r_push = subprocess.run(
        ["git", "push", "origin", REPO_BRANCH],
        cwd=KNOWLEDGE_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r_push.returncode != 0:
        return {
            "success": True,
            "push_failed": True,
            "hint": "push 失败，本地已保存。请稍后手动执行: git -C ~/.knowledge push",
            "push_error": r_push.stderr.strip()[:300],
        }

    return {"success": True, "push_failed": False}


def cmd_store(title: str, category: str, url: str, content: str) -> dict:
    """存储知识条目到 ~/.knowledge，更新 Index.md，git 同步。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    category = category or "_unsorted"
    slug = _slugify(title)
    rel_path = f"{category}/{slug}.md"
    file_path = KNOWLEDGE_DIR / rel_path

    # 创建目录
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入 md 文件
    entry_md = _build_entry_md(title, url, category, content)
    file_path.write_text(entry_md, encoding="utf-8")

    # 更新 Index.md
    _update_index(category, title, rel_path, url)

    # git 同步
    git_result = _git_sync(title, category)

    return {
        "success": True,
        "path": rel_path,
        "category": category,
        **git_result,
    }


# ─── main ─────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="知识导入工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="抓取 URL 内容")
    p_fetch.add_argument("url")

    p_store = sub.add_parser("store", help="存储知识条目")
    p_store.add_argument("--title", required=True)
    p_store.add_argument("--category", default="")
    p_store.add_argument("--url", required=True)
    p_store.add_argument("--content", required=True, help="Markdown 正文内容")

    args = parser.parse_args()

    if args.command == "fetch":
        result = cmd_fetch(args.url)
    elif args.command == "store":
        result = cmd_store(args.title, args.category, args.url, args.content)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
