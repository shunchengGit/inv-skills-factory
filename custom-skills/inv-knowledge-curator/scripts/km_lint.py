#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31.0",
#   "PyYAML>=6.0",
# ]
# ///
"""知识库完整性检查：死链、孤立文件、URL 可达性、重复检测、OKF合规、路径校验、交叉关联。

用法:
  uv run km_lint.py                           # 全量检查（含交叉关联建议）
  uv run km_lint.py --skip-url-check          # 跳过 URL 可达性
  uv run km_lint.py --fix                     # 修复死链/孤立 + 重建索引 + 自动建立交叉关联
  uv run km_lint.py --check-duplicates        # 含重复检测
"""

import argparse
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from proxy import detect_proxy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import parse_index, validate_okf, validate_bundle_paths, regenerate_indexes, find_cross_references

_DEFAULT_KNOWLEDGE_DIR = Path.home() / ".inv-knowledge"


def _get_knowledge_dir() -> Path:
    env = os.environ.get("INV_KNOWLEDGE_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_KNOWLEDGE_DIR


KNOWLEDGE_DIR = _get_knowledge_dir()


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


def check_urls(categories: dict[str, list[dict]], skip: bool = False) -> tuple[list[dict], list[dict]]:
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
    """从 md 文件的 YAML frontmatter 读取 url/resource 字段（兼容新旧格式）。"""
    from knowledge import _read_frontmatter
    fm = _read_frontmatter(file_path)
    return fm.get("resource") or fm.get("url") or None


def check_orphans(indexed_paths: set[str]) -> list[dict]:
    """检查存在但未被 Index.md 引用的 md 文件。"""
    orphans = []
    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if md_file.name in ("index.md", "log.md"):
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


def check_duplicates(categories: dict[str, list[dict]]) -> list[dict]:
    """检查重复条目（基于 URL 或标题相似度）。"""
    seen_urls: dict[str, list[dict]] = {}
    seen_titles: dict[str, list[dict]] = {}
    duplicates = []

    for cat, entries in categories.items():
        for entry in entries:
            url = entry.get("url", "")
            title = entry.get("title", "").lower()

            # URL 重复
            if url and url != "local":
                if url in seen_urls:
                    duplicates.append({
                        "type": "url_duplicate",
                        "url": url,
                        "entries": seen_urls[url] + [entry],
                    })
                else:
                    seen_urls[url] = [entry]

            # 标题相似（简单包含关系）
            if title:
                for existing_title, existing_entries in seen_titles.items():
                    if title in existing_title or existing_title in title:
                        if title != existing_title:  # 避免完全相同的
                            duplicates.append({
                                "type": "title_similar",
                                "title1": title,
                                "title2": existing_title,
                                "entries": existing_entries + [entry],
                            })
                if title not in seen_titles:
                    seen_titles[title] = [entry]

    return duplicates


def check_old_format() -> list[dict]:
    """检查是否还有旧格式条目（url/imported/category frontmatter）。"""
    issues = []
    if not KNOWLEDGE_DIR.exists():
        return issues

    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if md_file.name in ("index.md", "log.md"):
            continue
        if md_file.name in ("index.md", "log.md", "knowledge-graph.html"):
            continue

        try:
            fm = _read_frontmatter(md_file)
            rel = str(md_file.relative_to(KNOWLEDGE_DIR))

            # 旧格式标志：有 imported 或 category 字段，且没有 type 字段
            has_old = ("imported" in fm or "category" in fm)
            has_type = "type" in fm
            if has_old and not has_type:
                issues.append({
                    "path": rel,
                    "issue": "old_format",
                    "hint": "运行 km_migrate_to_okf.py --apply 迁移",
                })
        except Exception:
            pass

    return issues


def check_graph_staleness() -> list[dict]:
    """检查知识图谱是否过期（比最新条目旧）。"""
    graph_file = KNOWLEDGE_DIR / "knowledge-graph.html"
    if not graph_file.exists():
        return [{"path": "knowledge-graph.html", "issue": "graph_missing", "hint": "运行 km_visualize.py"}]

    graph_mtime = graph_file.stat().st_mtime
    stale = []
    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if md_file.name in ("index.md", "log.md"):
            continue
        if md_file.name in ("index.md", "log.md"):
            continue
        if md_file.stat().st_mtime > graph_mtime:
            stale.append(str(md_file.relative_to(KNOWLEDGE_DIR)))

    if stale:
        return [{
            "path": "knowledge-graph.html",
            "issue": "graph_stale",
            "newer_entries": len(stale),
            "hint": "运行 km_visualize.py 或 km_import store 自动更新",
        }]
    return []


def check_content_quality() -> list[dict]:
    """检查内容质量问题（空文件、过短内容、OKF 合规性等）。"""
    issues = []
    if not KNOWLEDGE_DIR.exists():
        return issues

    # 旧格式检测
    issues.extend(check_old_format())

    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if md_file.name in ("index.md", "log.md"):
            continue
        if md_file.name in ("index.md", "log.md"):
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
            rel = str(md_file.relative_to(KNOWLEDGE_DIR))

            # OKF 合规检查
            okf_result = validate_okf(md_file)
            if not okf_result["valid"]:
                for e in okf_result["errors"]:
                    issues.append({"path": rel, "issue": f"okf:{e}"})
            for w in okf_result.get("warnings", []):
                issues.append({"path": rel, "issue": f"okf_warn:{w}"})

            # 检查空内容
            if len(content.strip()) < 200:
                issues.append({"path": rel, "issue": "content_too_short", "chars": len(content.strip())})
                continue

            # 检查缺少关键章节
            if "## 摘要" not in content and "## Summary" not in content:
                issues.append({"path": rel, "issue": "missing_summary"})

            if "## 关键要点" not in content and "## Key Points" not in content:
                issues.append({"path": rel, "issue": "missing_key_points"})

        except Exception:
            pass

    return issues


def cmd_lint(skip_url_check: bool = False, check_duplicates_flag: bool = False) -> dict:
    """执行完整 lint 检查。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "dead_links": [],
            "dead_urls": [],
            "missing_urls": [],
            "orphans": [],
            "duplicates": [],
            "quality_issues": [],
            "total_entries": 0,
            "total_issues": 1,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    categories, indexed_paths = parse_index(KNOWLEDGE_DIR)
    total = sum(len(e) for e in categories.values())

    dead_links = check_dead_links(categories)
    dead_urls, missing_urls = check_urls(categories, skip=skip_url_check)
    orphans = check_orphans(indexed_paths)

    duplicates = []
    if check_duplicates_flag:
        duplicates = check_duplicates(categories)

    quality_issues = check_content_quality()
    path_issues = validate_bundle_paths(KNOWLEDGE_DIR)
    graph_issues = check_graph_staleness()
    cross_refs = find_cross_references(KNOWLEDGE_DIR)

    total_issues = (
        len(dead_links) + len(dead_urls) + len(missing_urls) +
        len(orphans) + len(duplicates) + len(quality_issues) +
        len(path_issues) + len(graph_issues)
    )

    return {
        "dead_links": dead_links,
        "dead_urls": dead_urls,
        "missing_urls": missing_urls,
        "orphans": orphans,
        "duplicates": duplicates,
        "quality_issues": quality_issues,
        "path_issues": path_issues,
        "graph_issues": graph_issues,
        "cross_references": cross_refs,
        "total_entries": total,
        "total_issues": total_issues,
    }


def fix_dead_links(dead_links: list[dict]) -> list[dict]:
    """自动修复死链：从各分类的 index.md 中移除引用不存在的条目。"""
    fixed = []
    for item in dead_links:
        path = item["path"]
        title = item["title"]
        for idx_file in KNOWLEDGE_DIR.rglob("index.md"):
            content = idx_file.read_text(encoding="utf-8")
            if path not in content:
                continue
            new_lines = []
            for line in content.splitlines():
                if path in line and f"[{title}]" in line:
                    continue
                new_lines.append(line)
            idx_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            fixed.append({"path": path, "title": title, "action": "removed_from_index"})
    return fixed


def fix_orphans(orphans: list[dict]) -> list[dict]:
    """自动修复孤立文件：将未被索引引用的文件加入对应分类的 index.md。"""
    fixed = []
    for item in orphans:
        path = item["path"]
        title = item["title"]
        category = path.split("/")[0] if "/" in path else "_unsorted"
        cat_dir = KNOWLEDGE_DIR / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        idx_file = cat_dir / "index.md"

        if idx_file.exists():
            content = idx_file.read_text(encoding="utf-8")
            if path in content:
                continue

        try:
            with open(idx_file, "a", encoding="utf-8") as f:
                f.write(f"- [{title}]({path}) — local\n")
        except (OSError, PermissionError) as e:
            print(f"Warning: cannot write to index {idx_file}: {e}", file=sys.stderr)
            continue
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


def _write_cross_references(refs: list[dict], top_n: int = 5) -> list[dict]:
    """将 Top-N 交叉关联写入 markdown 文件。

    在正文末尾添加或更新「## 关联」节，避免重复写入已存在的关联。
    返回 [{source, target, score, action}, ...]
    """
    applied = []
    for ref in refs[:top_n]:
        src_path = KNOWLEDGE_DIR / ref["source"]
        tgt_path = KNOWLEDGE_DIR / ref["target"]
        if not src_path.exists() or not tgt_path.exists():
            continue

        try:
            text = src_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # 检查是否已有该关联
        link_md = f"[{ref['target_title']}]({ref['target']})"
        if link_md in text:
            continue

        # 在正文末尾追加关联
        if "## 关联" not in text:
            text = text.rstrip() + f"\n\n## 关联\n- {link_md}\n"
        else:
            # 追加到已有关联节
            text = text.rstrip() + f"\n- {link_md}\n"

        src_path.write_text(text, encoding="utf-8")
        applied.append({
            "source": ref["source"],
            "target": ref["target"],
            "score": ref["score"],
            "action": "linked",
        })

    return applied


def main():
    parser = argparse.ArgumentParser(description="知识库完整性检查（含交叉关联发现）")
    parser.add_argument("--skip-url-check", action="store_true", help="跳过 URL 可达性检查")
    parser.add_argument("--fix", action="store_true", help="自动修复发现的问题（死链、孤立文件、缺失 URL）")
    parser.add_argument("--check-duplicates", action="store_true", help="检查重复条目")
    args = parser.parse_args()

    result = cmd_lint(skip_url_check=args.skip_url_check, check_duplicates_flag=args.check_duplicates)

    if args.fix:
        fix_actions = {}
        if result["dead_links"]:
            fix_actions["dead_links_fixed"] = fix_dead_links(result["dead_links"])
        if result["orphans"]:
            fix_actions["orphans_fixed"] = fix_orphans(result["orphans"])
        if result["missing_urls"]:
            fix_actions["missing_urls_fixed"] = fix_missing_urls(result["missing_urls"])

        # 重建所有 index.md（修死链+孤立后）
        index_result = regenerate_indexes(KNOWLEDGE_DIR)
        fix_actions["indexes_rebuilt"] = index_result

        # 自动建立交叉关联
        cross_refs = find_cross_references(KNOWLEDGE_DIR)
        linked = _write_cross_references(cross_refs)
        if linked:
            fix_actions["cross_references_added"] = linked

        # 重新 lint 确认修复结果
        if fix_actions:
            result = cmd_lint(skip_url_check=args.skip_url_check, check_duplicates_flag=args.check_duplicates)
            result["fix_actions"] = fix_actions

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
