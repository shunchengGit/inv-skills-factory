#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31.0",
#   "PyYAML>=6.0",
# ]
# ///
"""知识库完整性检查：死链、孤立文件、URL 可达性。

用法:
  uv run custom-skills/knowledge-mgr/scripts/km_lint.py
  uv run custom-skills/knowledge-mgr/scripts/km_lint.py --skip-url-check  # 跳过 URL 可达性检查
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from proxy import detect_proxy

KNOWLEDGE_DIR = Path.home() / ".knowledge"
INDEX_FILE = "Index.md"


def parse_index() -> tuple[dict[str, list[dict]], set[str]]:
    """解析 Index.md，返回 (categories, indexed_paths)。

    categories: {category: [{title, path, url}, ...]}
    indexed_paths: Index.md 中引用的所有相对路径集合
    """
    index_path = KNOWLEDGE_DIR / INDEX_FILE
    if not index_path.exists():
        return {}, set()

    content = index_path.read_text(encoding="utf-8")
    categories: dict[str, list[dict]] = {}
    indexed_paths: set[str] = set()
    current_category = None

    for line in content.splitlines():
        m = re.match(r"^##\s+(.+)", line)
        if m:
            current_category = m.group(1).strip()
            if current_category not in categories:
                categories[current_category] = []
            continue

        m = re.match(r"^-\s+\[(.+?)\]\((.+?)\)\s*[—–-]\s*(.+)", line)
        if m and current_category is not None:
            entry = {
                "title": m.group(1).strip(),
                "path": m.group(2).strip(),
                "url": m.group(3).strip(),
            }
            categories[current_category].append(entry)
            indexed_paths.add(entry["path"])

    return categories, indexed_paths


def check_dead_links(categories: dict[str, list[dict]]) -> list[dict]:
    """检查 Index.md 引用的文件是否存在。"""
    dead = []
    for _cat, entries in categories.items():
        for entry in entries:
            file_path = KNOWLEDGE_DIR / entry["path"]
            if not file_path.exists():
                dead.append({"title": entry["title"], "path": entry["path"]})
    return dead


def check_url_reachable(url: str, proxies: dict | None) -> dict | None:
    """对单个 URL 发 HEAD 请求，返回问题或 None。"""
    import requests

    try:
        r = requests.head(url, timeout=10, allow_redirects=True, proxies=proxies)
        if r.status_code >= 400:
            return {"url": url, "status": r.status_code}
    except requests.Timeout:
        return {"url": url, "status": "timeout"}
    except requests.RequestException:
        return {"url": url, "status": "error"}
    return None


def check_urls(categories: dict[str, list[dict]], skip: bool = False) -> list[dict]:
    """检查所有知识条目 frontmatter 中的 URL 可达性。"""
    if skip:
        return [], []

    proxy_url = detect_proxy()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    # 收集所有 md 文件和对应 URL
    tasks = []
    for _cat, entries in categories.items():
        for entry in entries:
            file_path = KNOWLEDGE_DIR / entry["path"]
            if file_path.exists():
                fm_url = _read_frontmatter_url(file_path)
                if fm_url:
                    tasks.append((entry["path"], fm_url))

    dead_urls = []
    missing_urls = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for path, url in tasks:
            futures[executor.submit(check_url_reachable, url, proxies)] = (path, url)

        for future in as_completed(futures):
            path, url = futures[future]
            result = future.result()
            if result:
                dead_urls.append({"path": path, **result})

    # 检查缺少 url 的 frontmatter
    for _cat, entries in categories.items():
        for entry in entries:
            file_path = KNOWLEDGE_DIR / entry["path"]
            if file_path.exists() and not _read_frontmatter_url(file_path):
                missing_urls.append({"path": entry["path"]})

    return dead_urls, missing_urls


def _read_frontmatter_url(file_path: Path) -> str | None:
    """从 md 文件的 YAML frontmatter 读取 url 字段。"""
    try:
        content = file_path.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if m:
            for line in m.group(1).splitlines():
                if line.startswith("url:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def check_orphans(indexed_paths: set[str]) -> list[dict]:
    """检查存在但未被 Index.md 引用的 md 文件。"""
    orphans = []
    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if md_file.name == INDEX_FILE:
            continue
        rel = str(md_file.relative_to(KNOWLEDGE_DIR))
        if rel not in indexed_paths:
            # 尝试读标题
            title = ""
            try:
                first_lines = md_file.read_text(encoding="utf-8").splitlines()
                for line in first_lines:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
            except Exception:
                pass
            orphans.append({"path": rel, "title": title})
    return orphans


def cmd_lint(skip_url_check: bool = False) -> dict:
    """执行完整 lint 检查。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "dead_links": [],
            "dead_urls": [],
            "missing_urls": [],
            "orphans": [],
            "total_entries": 0,
            "total_issues": 1,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    categories, indexed_paths = parse_index()
    total = sum(len(e) for e in categories.values())

    dead_links = check_dead_links(categories)
    dead_urls, missing_urls = check_urls(categories, skip=skip_url_check)
    orphans = check_orphans(indexed_paths)

    total_issues = len(dead_links) + len(dead_urls) + len(missing_urls) + len(orphans)

    return {
        "dead_links": dead_links,
        "dead_urls": dead_urls,
        "missing_urls": missing_urls,
        "orphans": orphans,
        "total_entries": total,
        "total_issues": total_issues,
    }


def main():
    parser = argparse.ArgumentParser(description="知识库完整性检查")
    parser.add_argument("--skip-url-check", action="store_true", help="跳过 URL 可达性检查")
    args = parser.parse_args()

    result = cmd_lint(skip_url_check=args.skip_url_check)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()