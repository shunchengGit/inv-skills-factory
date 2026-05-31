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
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_lint.py
  uv run custom-skills/general/gen-knowledge-curator/scripts/km_lint.py --skip-url-check  # 跳过 URL 可达性检查
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
from proxy import detect_proxy
from knowledge import parse_index

KNOWLEDGE_DIR = Path.home() / ".knowledge"
INDEX_DIR = "index"


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
        if md_file.parent.name == INDEX_DIR:
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

    categories, indexed_paths = parse_index(KNOWLEDGE_DIR, INDEX_DIR)
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


def fix_dead_links(dead_links: list[dict]) -> list[dict]:
    """自动修复死链：从 Index 中移除引用但文件不存在的条目。"""
    fixed = []
    index_dir = KNOWLEDGE_DIR / INDEX_DIR
    if not index_dir.exists():
        return fixed

    for item in dead_links:
        path = item["path"]
        title = item["title"]
        for idx_file in index_dir.glob("*.md"):
            content = idx_file.read_text(encoding="utf-8")
            new_lines = []
            removed = False
            for line in content.splitlines():
                if path in line and f"[{title}]" in line:
                    removed = True
                    continue
                new_lines.append(line)
            if removed:
                idx_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                fixed.append({"path": path, "title": title, "action": "removed_from_index"})
    return fixed


def fix_orphans(orphans: list[dict]) -> list[dict]:
    """自动修复孤立文件：将未被 Index 引用的文件自动加入对应分类的 Index。"""
    fixed = []
    index_dir = KNOWLEDGE_DIR / INDEX_DIR
    if not index_dir.exists():
        return fixed

    for item in orphans:
        path = item["path"]
        title = item["title"]
        # 从路径推断分类（如 investing/xxx.md → investing）
        category = path.split("/")[0] if "/" in path else "_unsorted"
        idx_file = index_dir / f"{category}.md"
        if not idx_file.exists():
            idx_file.write_text(f"## {category}\n", encoding="utf-8")

        # 读取现有内容，避免重复添加
        content = idx_file.read_text(encoding="utf-8")
        if path in content:
            continue

        # 追加到 Index
        with open(idx_file, "a", encoding="utf-8") as f:
            f.write(f"- [{title}]({path}) — local\n")
        fixed.append({"path": path, "title": title, "action": "added_to_index", "category": category})
    return fixed


def fix_missing_urls(missing_urls: list[dict]) -> list[dict]:
    """自动修复缺失 URL：在 frontmatter 中添加 url: null 标记。"""
    fixed = []
    for item in missing_urls:
        path = item["path"]
        file_path = KNOWLEDGE_DIR / path
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        if "url:" in content:
            continue
        # 在 frontmatter 中插入 url: null
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm = parts[1].strip()
                body = parts[2]
                new_fm = fm + "\nurl: null"
                new_content = f"---\n{new_fm}\n---{body}"
                file_path.write_text(new_content, encoding="utf-8")
                fixed.append({"path": path, "action": "added_url_null"})
    return fixed


def main():
    parser = argparse.ArgumentParser(description="知识库完整性检查")
    parser.add_argument("--skip-url-check", action="store_true", help="跳过 URL 可达性检查")
    parser.add_argument("--fix", action="store_true", help="自动修复发现的问题（死链、孤立文件、缺失 URL）")
    args = parser.parse_args()

    result = cmd_lint(skip_url_check=args.skip_url_check)

    if args.fix:
        fix_actions = {}
        if result["dead_links"]:
            fix_actions["dead_links_fixed"] = fix_dead_links(result["dead_links"])
        if result["orphans"]:
            fix_actions["orphans_fixed"] = fix_orphans(result["orphans"])
        if result["missing_urls"]:
            fix_actions["missing_urls_fixed"] = fix_missing_urls(result["missing_urls"])

        # 重新 lint 确认修复结果
        if fix_actions:
            result = cmd_lint(skip_url_check=args.skip_url_check)
            result["fix_actions"] = fix_actions

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()