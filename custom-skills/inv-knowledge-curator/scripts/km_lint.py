#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31.0",
#   "pyyaml>=6.0",
# ]
# ///
"""知识库完整性检查：OKF v0.2 合规、死链、孤立文件、URL 可达性、重复检测、
PDF 配对、标签治理、时效预警、交叉关联、图谱过期。

用法:
  uv run km_lint.py                           # 全量检查
  uv run km_lint.py --skip-url-check          # 跳过 URL 可达性
  uv run km_lint.py --fix                     # 安全修复死链/孤立 + 重建索引和图谱
  uv run km_lint.py --check-duplicates        # 含重复检测
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from proxy import detect_proxy
from git import sync as _git_sync, is_repo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import (
    parse_index, validate_okf, regenerate_index,
    regenerate_tag_indexes,
    _read_frontmatter, ENTRIES_DIR, RES_DIR_NAME,
)

_DEFAULT_KNOWLEDGE_DIR = Path.home() / ".inv-knowledge"


def _get_knowledge_dir() -> Path:
    env = os.environ.get("INV_KNOWLEDGE_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_KNOWLEDGE_DIR


KNOWLEDGE_DIR = _get_knowledge_dir()

# ─── 死链检查 ──────────────────────────────────────────────


def check_dead_links(entries: list[dict]) -> list[dict]:
    """检查交叉引用链接指向的文件是否存在。"""
    dead = []
    LINK_RE = re.compile(r"\]\(([^)]+)\)")
    for entry in entries:
        file_path = KNOWLEDGE_DIR / entry["path"]
        if not file_path.exists():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if "://" in target or target.startswith("#"):
                continue
            target = target.split("#")[0]
            if not target or not target.endswith(".md"):
                continue
            # 解析相对路径
            # 如果target以entries/开头，直接从KNOWLEDGE_DIR解析，避免entries/entries/双路径
            if target.startswith("entries/"):
                resolved = (KNOWLEDGE_DIR / target).resolve()
            else:
                resolved = (file_path.parent / target).resolve()
            try:
                resolved.relative_to(KNOWLEDGE_DIR)
            except ValueError:
                continue
            if not resolved.exists():
                dead.append({
                    "source": entry["path"],
                    "target": target,
                    "title": entry.get("title", ""),
                })
    return dead


# ─── URL 可达性 ────────────────────────────────────────────


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


def check_urls(entries: list[dict], skip: bool = False) -> tuple[list[dict], list[dict]]:
    """检查 source_type=url 条目中 resource URL 的可达性。"""
    if skip:
        return [], []

    proxy_url = detect_proxy()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    tasks = []
    for entry in entries:
        if entry.get("source_type") != "url":
            continue
        url = entry.get("resource", "")
        if url and url.startswith("http"):
            tasks.append((entry["path"], url))

    dead_urls = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for path, url in tasks:
            futures[executor.submit(check_url_reachable, url, proxies)] = (path, url)

        for future in as_completed(futures):
            path, url = futures[future]
            result = future.result()
            if result:
                dead_urls.append({"path": path, **result})

    # 检查缺少 resource 的条目（OKF v0.2 不允许）
    missing_urls = []
    for entry in entries:
        if not entry.get("resource"):
            missing_urls.append({"path": entry["path"], "title": entry.get("title", "")})

    return dead_urls, missing_urls


# ─── 孤立文件 ──────────────────────────────────────────────


def check_orphans(indexed_paths: set[str]) -> list[dict]:
    """检查 entries/ 下存在但未被索引引用的文件。"""
    entries_dir = KNOWLEDGE_DIR / ENTRIES_DIR
    if not entries_dir.is_dir():
        return []

    orphans = []
    for md_file in entries_dir.glob("*.md"):
        if md_file.name == "index.md":
            continue
        if md_file.name.startswith("."):
            continue
        rel = str(md_file.relative_to(KNOWLEDGE_DIR))
        if rel not in indexed_paths:
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


# ─── 重复检测 ──────────────────────────────────────────────


def check_duplicates(entries: list[dict]) -> list[dict]:
    """检查重复条目（基于 resource 或标题相似度）。"""
    from difflib import SequenceMatcher

    seen_resources: dict[str, list[dict]] = {}
    duplicates = []

    for entry in entries:
        resource = entry.get("resource", "")
        title = entry.get("title", "").lower()

        # resource 重复
        if resource and resource != "manual":
            if resource in seen_resources:
                duplicates.append({
                    "type": "resource_duplicate",
                    "resource": resource,
                    "entries": [{"title": e["title"], "path": e["path"]} for e in seen_resources[resource]] + [{"title": entry["title"], "path": entry["path"]}],
                })
            else:
                seen_resources[resource] = [entry]

    # 标题相似检测
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i], entries[j]
            if not a.get("title") or not b.get("title"):
                continue
            sim = SequenceMatcher(None, a["title"].lower(), b["title"].lower()).ratio()
            if sim > 0.85:
                duplicates.append({
                    "type": "title_similar",
                    "similarity": round(sim, 2),
                    "entry1": {"title": a["title"], "path": a["path"]},
                    "entry2": {"title": b["title"], "path": b["path"]},
                })

    return duplicates


# ─── OKF 合规 + 内容质量 ───────────────────────────────────


def check_okf_compliance() -> list[dict]:
    """检查所有条目是否符合 OKF v0.2。"""
    entries_dir = KNOWLEDGE_DIR / ENTRIES_DIR
    if not entries_dir.is_dir():
        return []

    issues = []
    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md" or md_file.name.startswith("."):
            continue
        rel = str(md_file.relative_to(KNOWLEDGE_DIR))

        okf_result = validate_okf(md_file)
        if not okf_result["valid"]:
            for e in okf_result["errors"]:
                issues.append({"path": rel, "issue": f"okf:{e}"})
        for w in okf_result.get("warnings", []):
            issues.append({"path": rel, "issue": f"okf_warn:{w}"})

        # 内容质量
        try:
            content = md_file.read_text(encoding="utf-8")
            if len(content.strip()) < 200:
                issues.append({"path": rel, "issue": "content_too_short", "chars": len(content.strip())})
                continue
            if "## 摘要" not in content and "## Summary" not in content:
                issues.append({"path": rel, "issue": "missing_summary"})
            else:
                # 检查摘要是否为空（只有标题没有内容）
                for tag_name in ("摘要", "Summary"):
                    m = re.search(rf"## {tag_name}\s*\n(.*?)(?:\n##|\Z)", content, re.DOTALL)
                    if m and len(m.group(1).strip()) < 30:
                        issues.append({"path": rel, "issue": "empty_summary"})
                        break
            if "## 关键要点" not in content and "## Key Points" not in content:
                issues.append({"path": rel, "issue": "missing_key_points"})
            else:
                for tag_name in ("关键要点", "Key Points"):
                    m = re.search(rf"## {tag_name}\s*\n(.*?)(?:\n## |\Z)", content, re.DOTALL)
                    if m:
                        section_content = m.group(1).strip()
                        # 关键要点必须有列表项：编号列表（1. **标题**：内容）或 bullet 列表（- **标题**：内容 或 - 纯文本内容）
                        numbered_items = re.findall(r'^\d+\.\s+\*\*', section_content, re.MULTILINE)
                        bullet_bold_items = re.findall(r'^-\s+\*\*', section_content, re.MULTILINE)
                        bullet_plain_items = re.findall(r'^-\s+\S', section_content, re.MULTILINE)
                        if len(numbered_items) < 2 and len(bullet_bold_items) < 2 and len(bullet_plain_items) < 2:
                            issues.append({"path": rel, "issue": "empty_key_points"})
                        break
        except Exception:
            pass

    return issues


# ─── PDF 配对检查 ──────────────────────────────────────────


def check_pdf_entry_pairing() -> list[dict]:
    """检查 PDF 与知识条目的配对关系。

    1. res/ 下 PDF 缺少对应 entries/ 条目 → 警告
    2. entries/ 中 source_type=pdf 但 resource 指向的 PDF 不存在 → 警告
    """
    issues = []

    res_dir = KNOWLEDGE_DIR / RES_DIR_NAME
    entries_dir = KNOWLEDGE_DIR / ENTRIES_DIR

    # 收集所有 source_type=pdf 的条目及其 resource 引用
    pdf_resources: set[str] = set()
    if entries_dir.is_dir():
        for md_file in entries_dir.glob("*.md"):
            if md_file.name == "index.md" or md_file.name.startswith("."):
                continue
            fm = _read_frontmatter(md_file)
            if fm.get("source_type") == "pdf":
                resource = fm.get("resource", "")
                values = resource if isinstance(resource, list) else re.split(r"\s*,\s*", str(resource))
                pdf_resources.update(str(v).strip() for v in values if str(v).strip())

    # 检查 res/ 下的 PDF 是否都有对应条目
    if res_dir.is_dir():
        for pdf_file in sorted(res_dir.rglob("*.pdf")):
            if pdf_file.name.startswith("."):
                continue
            rel = str(pdf_file.relative_to(KNOWLEDGE_DIR))
            # 检查是否有 entry 引用了此 PDF 或其所在目录
            parent_dir = str(pdf_file.parent.relative_to(KNOWLEDGE_DIR)) + "/"
            found = any(
                rel in r or parent_dir in r
                for r in pdf_resources
            )
            if not found:
                issues.append({
                    "path": rel,
                    "issue": "pdf_no_entry",
                    "hint": f"PDF 缺少对应的知识条目，运行 /km_import --pdf --target --folder {pdf_file.parent.name}",
                })

    # 检查 source_type=pdf 的条目 resource 是否指向存在的 PDF
    if entries_dir.is_dir():
        for md_file in entries_dir.glob("*.md"):
            if md_file.name == "index.md" or md_file.name.startswith("."):
                continue
            fm = _read_frontmatter(md_file)
            if fm.get("source_type") != "pdf":
                continue
            resource = fm.get("resource", "")
            rel = str(md_file.relative_to(KNOWLEDGE_DIR))
            values = resource if isinstance(resource, list) else re.split(r"\s*,\s*", str(resource))
            for value in values:
                resource_clean = str(value).strip().rstrip("/")
                if not resource_clean.startswith("res/"):
                    continue
                target = KNOWLEDGE_DIR / resource_clean
                exists = target.is_file() or (target.is_dir() and any(target.rglob("*.pdf")))
                if not exists:
                    issues.append({
                        "path": rel,
                        "issue": "pdf_resource_missing",
                        "resource": resource_clean,
                        "hint": "resource 指向的 PDF 文件/目录不存在或为空",
                    })

    return issues


# ─── 标签治理 ──────────────────────────────────────────────


def check_tag_governance() -> list[dict]:
    """检测标签质量问题：相似标签、低频标签、格式不规范。"""
    from difflib import SequenceMatcher
    from knowledge import get_all_tags

    tag_counts = get_all_tags(KNOWLEDGE_DIR)
    if not tag_counts:
        return []

    issues = []
    tags = list(tag_counts.keys())

    # 相似标签检测
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            sim = SequenceMatcher(None, tags[i].lower(), tags[j].lower()).ratio()
            if sim > 0.8 and sim < 1.0:
                issues.append({
                    "issue": "similar_tags",
                    "tag1": tags[i],
                    "tag2": tags[j],
                    "similarity": round(sim, 2),
                    "count1": tag_counts[tags[i]],
                    "count2": tag_counts[tags[j]],
                    "hint": "考虑合并或区分这两个标签",
                })

    # 低频标签（仅使用1次）
    for tag, count in tag_counts.items():
        if count == 1:
            issues.append({
                "issue": "low_frequency_tag",
                "tag": tag,
                "hint": "该标签仅使用1次，考虑合并到更通用的标签",
            })

    return issues


# ─── 时效预警 ──────────────────────────────────────────────


def check_stale_entries() -> list[dict]:
    """标记超过 183 天的 stale 条目。"""
    entries_dir = KNOWLEDGE_DIR / ENTRIES_DIR
    if not entries_dir.is_dir():
        return []

    today = date.today()
    cutoff = today - timedelta(days=183)
    stale = []

    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md" or md_file.name.startswith("."):
            continue
        fm = _read_frontmatter(md_file)
        ts = fm.get("timestamp", "")
        if not ts:
            continue
        ts_text = str(ts)
        try:
            ts_date = date.fromisoformat(ts_text[:10])
        except ValueError:
            continue
        if ts_date < cutoff:
            rel = str(md_file.relative_to(KNOWLEDGE_DIR))
            days_ago = (today - ts_date).days
            stale.append({
                "path": rel,
                "title": fm.get("title", ""),
                "timestamp": ts_text[:10],
                "days_ago": days_ago,
                "issue": "stale_entry",
                "hint": f"该条目已 {days_ago} 天未更新，可能已过时",
            })

    return stale


# ─── 交叉引用密度 ──────────────────────────────────────────


def check_cross_reference_density() -> list[dict]:
    """检测孤立节点（0 交叉引用）。"""
    entries_dir = KNOWLEDGE_DIR / ENTRIES_DIR
    if not entries_dir.is_dir():
        return []

    LINK_RE = re.compile(r"\]\(([^)]+)\)")
    isolated = []

    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md" or md_file.name.startswith("."):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # 统计出链
        out_links = 0
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if "://" in target or target.startswith("#"):
                continue
            if target.endswith(".md"):
                out_links += 1

        fm = _read_frontmatter(md_file)
        rel = str(md_file.relative_to(KNOWLEDGE_DIR))

        if out_links == 0:
            isolated.append({
                "path": rel,
                "title": fm.get("title", ""),
                "issue": "no_cross_references",
                "hint": "该条目没有任何交叉引用，搜索召回率可能偏低",
            })

    return isolated


# ─── 图谱过期 ──────────────────────────────────────────────


def check_graph_staleness() -> list[dict]:
    """检查知识图谱是否过期。"""
    graph_file = KNOWLEDGE_DIR / "knowledge-graph.html"
    if not graph_file.exists():
        return [{"path": "knowledge-graph.html", "issue": "graph_missing", "hint": "运行 km_visualize.py"}]

    graph_mtime = graph_file.stat().st_mtime
    stale = []
    entries_dir = KNOWLEDGE_DIR / ENTRIES_DIR
    if entries_dir.is_dir():
        for md_file in entries_dir.glob("*.md"):
            if md_file.name == "index.md":
                continue
            if md_file.name.startswith("."):
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


# ─── 主检查函数 ────────────────────────────────────────────


def cmd_lint(skip_url_check: bool = False, check_duplicates_flag: bool = False) -> dict:
    """执行完整 lint 检查。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "total_entries": 0,
            "total_issues": 1,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    entries, indexed_paths = parse_index(KNOWLEDGE_DIR)

    dead_links = check_dead_links(entries)
    dead_urls, missing_urls = check_urls(entries, skip=skip_url_check)
    orphans = check_orphans(indexed_paths)

    duplicates = []
    if check_duplicates_flag:
        duplicates = check_duplicates(entries)

    okf_issues = check_okf_compliance()
    pdf_pairing = check_pdf_entry_pairing()
    tag_issues = check_tag_governance()
    stale_entries = check_stale_entries()
    isolated_entries = check_cross_reference_density()
    graph_issues = check_graph_staleness()

    total_issues = (
        len(dead_links) + len(dead_urls) + len(missing_urls) +
        len(orphans) + len(duplicates) + len(okf_issues) +
        len(pdf_pairing) + len(tag_issues) + len(stale_entries) +
        len(isolated_entries) + len(graph_issues)
    )

    error_count = len(dead_links) + len(missing_urls) + len(orphans) + sum(
        1 for i in okf_issues if not str(i.get("issue", "")).startswith("okf_warn:")
    ) + sum(1 for i in pdf_pairing if i.get("issue") == "pdf_resource_missing")
    warning_count = len(dead_urls) + len(stale_entries) + len(isolated_entries) + len(graph_issues) + sum(
        1 for i in pdf_pairing if i.get("issue") == "pdf_no_entry"
    ) + sum(1 for i in okf_issues if str(i.get("issue", "")).startswith("okf_warn:"))
    advisory_count = len(duplicates) + len(tag_issues)

    return {
        "total_entries": len(entries),
        "total_issues": total_issues,
        "severity": {"errors": error_count, "warnings": warning_count, "advisories": advisory_count},
        "summary": {
            "okf_errors": len(okf_issues),
            "dead_links": len(dead_links),
            "orphans": len(orphans),
            "empty_summary": sum(1 for i in okf_issues if i.get("issue") == "empty_summary"),
            "empty_key_points": sum(1 for i in okf_issues if i.get("issue") == "empty_key_points"),
            "missing_summary": sum(1 for i in okf_issues if i.get("issue") == "missing_summary"),
            "missing_key_points": sum(1 for i in okf_issues if i.get("issue") == "missing_key_points"),
            "content_too_short": sum(1 for i in okf_issues if i.get("issue") == "content_too_short"),
            "no_cross_refs": len(isolated_entries),
            "stale": len(stale_entries),
            "pdf_no_entry": len([i for i in pdf_pairing if i.get("issue") == "pdf_no_entry"]),
            "pdf_resource_missing": len([i for i in pdf_pairing if i.get("issue") == "pdf_resource_missing"]),
            "similar_tags": len([i for i in tag_issues if i.get("issue") == "similar_tags"]),
            "low_frequency_tags": len([i for i in tag_issues if i.get("issue") == "low_frequency_tag"]),
        },
        "dead_links": dead_links,
        "dead_urls": dead_urls,
        "missing_urls": missing_urls,
        "orphans": orphans,
        "duplicates": duplicates,
        "okf_compliance": okf_issues,
        "pdf_pairing": pdf_pairing,
        "tag_governance": tag_issues,
        "stale_entries": stale_entries,
        "isolated_entries": isolated_entries,
        "graph_issues": graph_issues,
    }


# ─── 修复函数 ──────────────────────────────────────────────


def build_pdf_pending_plan(knowledge_dir: Path, pdf_pairing: list[dict]) -> list[dict]:
    """构建待导入 PDF 清单，供 LLM 驱动批量 /km_import res。

    输出格式包含足够信息，LLM 可直接按 target 分组后逐个调用
    km_import.py res --file <path> --target <folder> 完成导入。
    """
    pending = []
    for item in pdf_pairing:
        if item.get("issue") != "pdf_no_entry":
            continue
        path = item["path"]  # e.g., res/ASML/xxx.pdf
        pdf_path = knowledge_dir / path
        if not pdf_path.exists():
            continue
        pending.append({
            "path": path,
            "target": pdf_path.parent.name,
            "filename": pdf_path.name,
            "size_bytes": pdf_path.stat().st_size,
        })
    # 按 target 分组
    grouped = {}
    for p in pending:
        grouped.setdefault(p["target"], []).append(p)
    # 返回分组后的清单，每组含该 target 的全部待导入 PDF
    result = []
    for target, items in sorted(grouped.items()):
        result.append({
            "target": target,
            "count": len(items),
            "files": [{"path": i["path"], "filename": i["filename"]} for i in items],
        })
    return result


def fix_dead_links(dead_links: list[dict]) -> list[dict]:
    """安全修复死链：从源条目中仅移除对应 Markdown 链接。"""
    fixed = []
    for item in dead_links:
        path = item.get("source", item.get("path", ""))
        target = item.get("target", "")
        source_file = KNOWLEDGE_DIR / path
        if not source_file.exists() or not target:
            continue
        content = source_file.read_text(encoding="utf-8")
        pattern = re.compile(rf"\[[^\]]*\]\({re.escape(target)}(?:#[^)]*)?\)")
        new_content, count = pattern.subn("", content)
        if not count:
            continue
        new_content = re.sub(r"(?m)^-\s*(?:—|——|-)?\s*$\n?", "", new_content)
        source_file.write_text(new_content, encoding="utf-8")
        fixed.append({"path": path, "target": target, "action": "removed_dead_link"})
    return fixed


def fix_orphans(orphans: list[dict]) -> list[dict]:
    """自动修复孤立文件：将未被索引引用的文件加入 entries/index.md。"""
    fixed = []
    idx_file = KNOWLEDGE_DIR / ENTRIES_DIR / "index.md"
    idx_file.parent.mkdir(parents=True, exist_ok=True)

    existing_content = idx_file.read_text(encoding="utf-8") if idx_file.exists() else ""

    for item in orphans:
        path = item["path"]
        title = item["title"]
        if path in existing_content:
            continue

        try:
            with open(idx_file, "a", encoding="utf-8") as f:
                f.write(f"- [{title}]({path}) — \n")
        except (OSError, PermissionError) as e:
            print(f"Warning: cannot write to index {idx_file}: {e}", file=sys.stderr)
            continue
        fixed.append({"path": path, "title": title, "action": "added_to_index"})
    return fixed


def fix_missing_urls(missing_urls: list[dict]) -> list[dict]:
    """自动修复缺失 resource：标记 source_type=note, resource=manual。"""
    fixed = []
    for item in missing_urls:
        path = item["path"]
        file_path = KNOWLEDGE_DIR / path
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        if "resource:" in content:
            continue
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm = parts[1].strip()
                body = parts[2]
                new_fm = fm + "\nresource: manual\nsource_type: note"
                new_content = f"---\n{new_fm}\n---{body}"
                file_path.write_text(new_content, encoding="utf-8")
                fixed.append({"path": path, "action": "added_resource_and_source_type"})
    return fixed


def main():
    parser = argparse.ArgumentParser(description="知识库完整性检查 (OKF v0.2)")
    parser.add_argument("--skip-url-check", action="store_true", help="跳过 URL 可达性检查")
    parser.add_argument("--fix", action="store_true", help="自动修复发现的问题")
    parser.add_argument("--check-duplicates", action="store_true", help="检查重复条目")
    args = parser.parse_args()

    result = cmd_lint(skip_url_check=args.skip_url_check, check_duplicates_flag=args.check_duplicates)

    if args.fix:
        fix_actions = {}
        if result.get("dead_links"):
            fix_actions["dead_links_fixed"] = fix_dead_links(result["dead_links"])
        if result.get("orphans"):
            fix_actions["orphans_fixed"] = fix_orphans(result["orphans"])
        if result.get("missing_urls"):
            fix_actions["missing_urls_fixed"] = fix_missing_urls(result["missing_urls"])

        # PDF 导入计划 — 不自动导入，但生成结构化清单供 LLM 驱动
        pdf_pairing = result.get("pdf_pairing", [])
        pdf_pending = build_pdf_pending_plan(KNOWLEDGE_DIR, pdf_pairing)
        if pdf_pending:
            fix_actions["pdf_pending"] = pdf_pending

        # 重建索引 + 标签索引
        index_result = regenerate_index(KNOWLEDGE_DIR)
        fix_actions["index_rebuilt"] = index_result
        tag_index_result = regenerate_tag_indexes(KNOWLEDGE_DIR)
        fix_actions["tag_indexes_rebuilt"] = tag_index_result

        # 重建图谱
        try:
            from km_visualize import cmd_visualize
            graph_result = cmd_visualize()
            fix_actions["graph_rebuilt"] = graph_result
        except Exception:
            pass

        # git push
        if fix_actions and is_repo(KNOWLEDGE_DIR):
            push_result = _git_sync(KNOWLEDGE_DIR, "chore: lint --fix 自动修复")
            fix_actions["git_push"] = {"success": push_result["success"],
                                       "message": push_result.get("files_changed", "") or push_result.get("error", "")}

        # 重新 lint 确认修复结果
        if fix_actions:
            result = cmd_lint(skip_url_check=args.skip_url_check, check_duplicates_flag=args.check_duplicates)
            result["fix_actions"] = fix_actions

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
