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
  store  - 存储知识条目到 ~/.knowledge + 更新 index/{category}.md + git 同步

用法:
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_import.py fetch <url>
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_import.py store --title "标题" --category investing --url https://... --content <md>
  # 从文件导入（推荐，避免管道截断问题）：
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_import.py store --title "标题" --category investing --url https://... --content-file /tmp/article.md
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_import.py store --title "标题" --url https://... --content <md>  # 无 category → _unsorted
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
from pwright import scrape_url as pwright_scrape_url
from git import sync as _git_sync

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import slugify, build_entry

KNOWLEDGE_DIR = Path.home() / ".knowledge"
REPO_BRANCH = "master"
INDEX_DIR = "index"
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
    result = _firecrawl_scrape(url)
    if result:
        return {
            "success": True,
            "source": "firecrawl",
            "title": result["title"],
            "content": result["content"],
            "url": url,
        }

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


def _update_index(category: str, title: str, rel_path: str, url: str) -> None:
    """追加条目到 index/{category}.md。"""
    index_dir = KNOWLEDGE_DIR / INDEX_DIR
    index_dir.mkdir(parents=True, exist_ok=True)
    index_file = index_dir / f"{category}.md"
    entry_line = f"- [{title}]({rel_path}) — {url}\n"
    with open(index_file, "a", encoding="utf-8") as f:
        f.write(entry_line)


def cmd_store(title: str, category: str, url: str, content: str, min_content_length: int = 100) -> dict:
    """存储知识条目到 ~/.knowledge，更新 index，git 同步。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    # 内容验证
    content = content.strip()
    if not content:
        return {
            "success": False,
            "error": "content 为空，请检查输入内容",
        }
    
    if len(content) < min_content_length:
        return {
            "success": False,
            "error": f"content 过短（{len(content)} 字符，最低要求 {min_content_length} 字符），疑似内容被截断，请检查输入",
        }

    category = category or "_unsorted"
    slug = slugify(title)
    today = date.today().isoformat()
    rel_path = f"{category}/{slug}.md"
    file_path = KNOWLEDGE_DIR / rel_path

    # 同名文件加日期后缀避免覆盖
    if file_path.exists():
        slug = f"{slug}-{today}"
        rel_path = f"{category}/{slug}.md"
        file_path = KNOWLEDGE_DIR / rel_path

    file_path.parent.mkdir(parents=True, exist_ok=True)
    entry_md = build_entry(title, url, category, content)
    file_path.write_text(entry_md, encoding="utf-8")

    _update_index(category, title, rel_path, url)

    commit_msg = f"import: {title} → {category}/"
    git_result = _git_sync(KNOWLEDGE_DIR, commit_msg, branch=REPO_BRANCH)

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
    p_store.add_argument("--content", default="", help="Markdown 正文内容。直接传入内容，或使用 '-' 从 stdin 读取")
    p_store.add_argument("--content-file", help="从文件读取 Markdown 内容（与 --content 互斥）。示例: --content-file /tmp/article.md")
    p_store.add_argument("--min-content-length", type=int, default=100, help="内容最小长度校验（默认 100 字符）")

    args = parser.parse_args()

    if args.command == "fetch":
        result = cmd_fetch(args.url)
    elif args.command == "store":
        # 优先从文件读取内容
        content = args.content
        if hasattr(args, 'content_file') and args.content_file:
            content = Path(args.content_file).read_text(encoding="utf-8")
        elif content == "-":
            # 从 stdin 读取
            import sys
            content = sys.stdin.read()
        
        # 获取最小长度校验值
        min_length = getattr(args, 'min_content_length', 100)
        
        result = cmd_store(args.title, args.category, args.url, content, min_content_length=min_length)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
