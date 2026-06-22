#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31.0",
#   "html2text>=2024.2.26",
# ]
# ///
"""知识导入：URL 抓取 + 知识条目存储 + 分类管理。

输出的知识条目符合 OKF v0.1 格式：
  - 必需 frontmatter: type, title, description, timestamp
  - 推荐: resource (=url), tags

子命令：
  fetch  - 抓取 URL 内容（Firecrawl → pwright 兜底）
  store  - 存储知识条目到 ~/.knowledge + 更新 index/{category}.md + git 同步
  categories - 列出所有可用分类

用法:
  uv run km_import.py fetch <url>
  uv run km_import.py store --title "标题" --category investing --url https://... --content <md>
  uv run km_import.py store --title "标题" --category investing --url https://... --content-file /tmp/article.md
  uv run km_import.py store --title "标题" --url https://... --content <md>  # 无 category → _unsorted
  uv run km_import.py categories
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from pwright import scrape_url as pwright_scrape_url
from git import sync as _git_sync

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import slugify, build_entry, parse_index, now_iso

KNOWLEDGE_DIR = Path.home() / ".knowledge"
REPO_BRANCH = "master"
FIRECRAWL_URL = "http://localhost:3672/v1/scrape"

# 预定义分类体系
DEFAULT_CATEGORIES = {
    "investing": "投资分析与估值",
    "programming": "编程与工程",
    "ai-ml": "AI 与机器学习",
    "product": "产品与运营",
    "career": "职业与成长",
    "reading": "阅读与笔记",
    "tools": "工具与效率",
    "life": "生活与其他",
}


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


# ─── categories 子命令 ────────────────────────────────────


def cmd_categories() -> dict:
    """列出所有可用分类，包括预定义和已存在的。"""
    existing = set()
    if KNOWLEDGE_DIR.exists():
        for idx_file in KNOWLEDGE_DIR.rglob("index.md"):
            cat = idx_file.parent.name
            if cat and not cat.startswith(".") and not cat.startswith("_"):
                existing.add(cat)

    all_categories = {**DEFAULT_CATEGORIES}
    for cat in existing:
        if cat not in all_categories:
            all_categories[cat] = cat

    return {
        "success": True,
        "categories": all_categories,
        "total": len(all_categories),
    }


# ─── store 子命令 ─────────────────────────────────────────


def _update_index(category: str, title: str, rel_path: str, url: str, description: str = "") -> None:
    """按 OKF bundle 结构追加条目到 {category}/index.md。"""
    cat_dir = KNOWLEDGE_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    index_file = cat_dir / "index.md"
    desc_segment = f" — {description}" if description else ""
    entry_line = f"- [{title}]({rel_path}) — {url}{desc_segment}\n"
    with open(index_file, "a", encoding="utf-8") as f:
        f.write(entry_line)


def _auto_description(content: str, title: str, max_len: int = 120) -> str:
    """从内容自动提取一句话描述。取第一个非标题非空段落。"""
    lines = content.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 跳过链接和列表
        if stripped.startswith(("- ", "* ", "[", "|", ">")):
            continue
        # 取第一段非标记文本
        desc = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)  # 去链接
        desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)  # 去粗体
        if len(desc) > 20:
            if len(desc) > max_len:
                desc = desc[:max_len].rsplit("。", 1)[0] + "。"
            return desc
    # fallback: 用标题
    return f"{title}相关知识的整理与摘要。"


def cmd_store(
    title: str,
    category: str,
    url: str,
    content: str,
    *,
    min_content_length: int = 100,
    tags: list[str] | None = None,
    entry_type: str = "Article",
    description: str = "",
) -> dict:
    """存储知识条目到 ~/.knowledge，更新 index，git 同步。
    输出符合 OKF v0.1 格式。"""
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

    # 自动生成 description（如果未提供）
    if not description:
        description = _auto_description(content, title)

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
    entry_md = build_entry(
        title=title,
        description=description,
        url=url,
        content=content,
        entry_type=entry_type,
        tags=tags,
    )
    file_path.write_text(entry_md, encoding="utf-8")

    _update_index(category, title, rel_path, url, description)

    commit_msg = f"import: {title} → {category}/"
    git_result = _git_sync(KNOWLEDGE_DIR, commit_msg, branch=REPO_BRANCH)

    # 追加 log.md
    try:
        log_file = KNOWLEDGE_DIR / "log.md"
        today_str = date.today().isoformat()
        log_entry = f"- [{title}]({rel_path}) — {entry_type} → {category}\n"
        existing = log_file.read_text(encoding="utf-8") if log_file.exists() else "# 变更日志\n\n"
        if f"## {today_str}" not in existing:
            existing = existing.rstrip() + f"\n\n## {today_str}\n"
        log_file.write_text(existing.rstrip() + "\n" + log_entry + "\n", encoding="utf-8")
    except Exception:
        pass

    # 自动更新知识图谱
    graph_result = {"graph": "skipped"}
    try:
        from km_visualize import cmd_visualize
        graph_result = cmd_visualize()
    except Exception:
        pass  # 图谱生成失败不阻塞导入

    return {
        "success": True,
        "path": rel_path,
        "category": category,
        "type": entry_type,
        "description": description,
        "graph": graph_result,
        **git_result,
    }


# ─── main ─────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="知识导入工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="抓取 URL 内容")
    p_fetch.add_argument("url")

    p_store = sub.add_parser("store", help="存储知识条目（OKF v0.1 格式）")
    p_store.add_argument("--title", required=True)
    p_store.add_argument("--category", default="")
    p_store.add_argument("--url", required=True)
    p_store.add_argument("--content", default="", help="Markdown 正文内容。直接传入内容，或使用 '-' 从 stdin 读取")
    p_store.add_argument("--content-file", help="从文件读取 Markdown 内容（与 --content 互斥）")
    p_store.add_argument("--description", default="", help="一句话描述（OKF 必需）。不提供则自动从正文第一段提取")
    p_store.add_argument("--type", default="Article", help="知识类型（OKF 必需）。默认 Article")
    p_store.add_argument("--min-content-length", type=int, default=100, help="内容最小长度校验（默认 100 字符）")
    p_store.add_argument("--tags", default="", help="标签列表，逗号分隔。示例: python,async,performance")

    sub.add_parser("categories", help="列出所有可用分类")

    args = parser.parse_args()

    if args.command == "fetch":
        result = cmd_fetch(args.url)
    elif args.command == "store":
        # 优先从文件读取内容
        content = args.content
        if hasattr(args, 'content_file') and args.content_file:
            content = Path(args.content_file).read_text(encoding="utf-8")
        elif content == "-":
            content = sys.stdin.read()

        min_length = getattr(args, 'min_content_length', 100)
        tags = None
        if hasattr(args, 'tags') and args.tags:
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]

        result = cmd_store(
            title=args.title,
            category=args.category,
            url=args.url,
            content=content,
            min_content_length=min_length,
            tags=tags,
            entry_type=getattr(args, 'type', 'Article'),
            description=getattr(args, 'description', ''),
        )
    elif args.command == "categories":
        result = cmd_categories()
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
