"""知识库共享工具：Index 解析、迁移、条目格式（OKF v0.1）、搜索。

OKF (Open Knowledge Format) 规范：
  - 每个知识条目是一个 UTF-8 markdown 文件，含 YAML frontmatter
  - 必需 frontmatter 字段: type, title, description, timestamp
  - 推荐字段: resource, tags
  - 保留文件名: index.md, log.md

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
  from knowledge import parse_index, migrate_index, build_entry, slugify, search_entries, validate_okf, regenerate_indexes, validate_bundle_paths
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ENTRY_LINE_RE = re.compile(r"^-\s+\[(.+?)\]\((.+?)\)\s*[—–-]\s*(.+)")
SECTION_RE = re.compile(r"^##\s+(.+)")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)

# OKF 必需字段
OKF_REQUIRED = ("type", "title", "description", "timestamp")
# 本地时区
LOCAL_TZ = timezone(timedelta(hours=8))  # Asia/Shanghai


def migrate_index(knowledge_dir: Path) -> None:
    """旧格式迁移：Index.md → */index.md，index/*.md → */index.md。"""
    # 迁移1: 根 Index.md → 各分类目录的 index.md
    old_root_index = knowledge_dir / "Index.md"
    if old_root_index.exists():
        current_category = None
        for line in old_root_index.read_text(encoding="utf-8").splitlines():
            m = SECTION_RE.match(line)
            if m:
                current_category = m.group(1).strip()
                (knowledge_dir / current_category).mkdir(parents=True, exist_ok=True)
                continue
            if current_category and line.startswith("- "):
                idx_file = knowledge_dir / current_category / "index.md"
                with open(idx_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        old_root_index.rename(old_root_index.with_suffix(".md.bak"))

    # 迁移2: index/category.md → category/index.md
    old_index_dir = knowledge_dir / "index"
    if old_index_dir.is_dir():
        for f in sorted(old_index_dir.glob("*.md")):
            category = f.stem
            cat_dir = knowledge_dir / category
            cat_dir.mkdir(parents=True, exist_ok=True)
            new_idx = cat_dir / "index.md"
            if not new_idx.exists():
                f.rename(new_idx)
            else:
                # 合并：追加内容
                existing = new_idx.read_text(encoding="utf-8")
                new_content = f.read_text(encoding="utf-8")
                new_idx.write_text(existing.rstrip() + "\n" + new_content, encoding="utf-8")
                f.unlink()
        # 清理空的 index/ 目录
        try:
            old_index_dir.rmdir()
        except OSError:
            pass


def parse_index(knowledge_dir: Path) -> tuple[dict[str, list[dict]], set[str]]:
    """按 OKF bundle 结构解析索引：每个目录下的 index.md。

    categories: {category: [{title, path, url, type, description?, timestamp?}, ...]}
    indexed_paths: 所有被引用的相对路径集合
    """
    migrate_index(knowledge_dir)

    categories: dict[str, list[dict]] = {}
    indexed_paths: set[str] = set()

    # 扫描所有子目录的 index.md（OKF bundle 结构）
    for idx_file in sorted(knowledge_dir.rglob("index.md")):
        category = idx_file.parent.name
        # 跳过根目录 index.md（那是 bundle 入口，不是分类索引）
        if idx_file.parent == knowledge_dir:
            continue
        # 跳过隐藏目录
        if category.startswith(".") or category.startswith("_"):
            continue

        entries: list[dict] = []
        for line in idx_file.read_text(encoding="utf-8").splitlines():
            m = ENTRY_LINE_RE.match(line)
            if m:
                entry = {
                    "title": m.group(1).strip(),
                    "path": m.group(2).strip(),
                    "url": m.group(3).strip(),
                }
                file_path = knowledge_dir / entry["path"]
                fm = _read_frontmatter(file_path) if file_path.exists() else {}
                if fm.get("type"):
                    entry["type"] = fm["type"]
                if fm.get("description"):
                    entry["description"] = fm["description"]
                if fm.get("timestamp"):
                    entry["timestamp"] = fm["timestamp"]
                entries.append(entry)
                indexed_paths.add(entry["path"])
        if entries:
            categories[category] = entries

    return categories, indexed_paths


def slugify(title: str, max_len: int = 80) -> str:
    """标题 → kebab-case slug。"""
    s = re.sub(r"[^\w一-鿿]+", "-", title.strip())
    s = s.strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "untitled"


def now_iso() -> str:
    """当前时间 ISO 8601 含时区。"""
    return datetime.now(LOCAL_TZ).isoformat()


def build_entry(
    title: str,
    description: str,
    url: str = "",
    content: str = "",
    *,
    entry_type: str = "Article",
    tags: list[str] | None = None,
    timestamp: str | None = None,
) -> str:
    """构建符合 OKF v0.1 的知识条目 markdown。

    必需 frontmatter: type, title, description, timestamp
    推荐: resource (=url), tags
    """
    ts = timestamp or now_iso()
    tags_line = f"tags: [{', '.join(tags)}]" if tags else ""
    resource_line = f"resource: {url}" if url else ""

    lines = [
        "---",
        f"type: {entry_type}",
        f"title: {title}",
        f"description: {description}",
        f"timestamp: {ts}",
    ]
    if resource_line:
        lines.append(resource_line)
    if tags_line:
        lines.append(tags_line)
    lines.append("---")

    frontmatter = "\n".join(lines)
    body = content.strip() if content.strip() else f"# {title}\n"

    return f"{frontmatter}\n\n{body}\n"


def validate_okf(file_path: Path) -> dict:
    """校验单个知识文件是否符合 OKF v0.1。

    返回 {"valid": bool, "errors": [...], "warnings": [...]}
    """
    result = {"valid": True, "errors": [], "warnings": []}

    if not file_path.exists():
        result["valid"] = False
        result["errors"].append("文件不存在")
        return result

    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"读取失败: {e}")
        return result

    m = FRONTMATTER_RE.match(text)
    if not m:
        result["valid"] = False
        result["errors"].append("缺少 YAML frontmatter (--- ... ---)")
        return result

    fm_text = m.group(1)

    # 解析 frontmatter 为 dict
    fm: dict[str, str] = {}
    current_key = None
    current_val: list[str] = []
    for line in fm_text.split("\n"):
        if line.strip().startswith("#"):
            continue
        if ":" in line and not line.startswith((" ", "\t")):
            if current_key:
                fm[current_key] = "\n".join(current_val).strip()
            key, _, val = line.partition(":")
            current_key = key.strip()
            current_val = [val.strip()] if val.strip() else []
        elif current_key and (line.startswith("  ") or line.startswith("\t")):
            current_val.append(line.strip())
    if current_key:
        fm[current_key] = "\n".join(current_val).strip()

    # 必需字段
    for field in OKF_REQUIRED:
        if field not in fm or not fm[field]:
            result["valid"] = False
            result["errors"].append(f"缺少必需字段: {field}")

    # timestamp 格式
    if "timestamp" in fm and fm["timestamp"]:
        ts = fm["timestamp"].strip().strip('"').strip("'")
        # 接受 ISO 8601 日期或日期时间
        if not re.match(r"^\d{4}-\d{2}-\d{2}", ts):
            result["valid"] = False
            result["errors"].append(f"timestamp 格式无效: {ts}（期望 ISO 8601）")

    # 推荐字段缺失
    for field in ("resource", "tags"):
        if field not in fm or not fm[field]:
            result["warnings"].append(f"缺少推荐字段: {field}")

    return result


def _read_frontmatter(file_path: Path) -> dict[str, str]:
    """读取文件的 YAML frontmatter 为简单 dict。"""
    try:
        text = file_path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            return {}
        fm: dict[str, str] = {}
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith((" ", "\t", "#")):
                key, _, val = line.partition(":")
                fm[key.strip()] = val.strip().strip('"').strip("'")
        return fm
    except Exception:
        return {}


def search_entries(knowledge_dir: Path, query: str) -> list[dict]:
    """搜索知识库条目，支持标题、描述和内容匹配。

    返回匹配条目列表，按相关性排序（标题匹配优先）。
    """
    query_lower = query.lower()
    categories, _ = parse_index(knowledge_dir)
    results = []

    for cat, entries in categories.items():
        for entry in entries:
            title_match = query_lower in entry["title"].lower()
            desc_match = query_lower in entry.get("description", "").lower()

            # 读取文件内容检查
            file_path = knowledge_dir / entry["path"]
            content_match = False
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8").lower()
                    content_match = query_lower in content
                except Exception:
                    pass

            if title_match or desc_match or content_match:
                results.append({
                    "title": entry["title"],
                    "path": entry["path"],
                    "url": entry["url"],
                    "category": cat,
                    "type": entry.get("type", ""),
                    "description": entry.get("description", ""),
                    "timestamp": entry.get("timestamp", ""),
                    "title_match": title_match,
                    "description_match": desc_match,
                    "content_match": content_match,
                })

    # 排序：标题匹配 > 描述匹配 > 内容匹配
    results.sort(key=lambda x: (
        not x["title_match"],
        not x["description_match"],
        not x["content_match"],
    ))
    return results


# ── 索引重建 ─────────────────────────────────────────────────────────────

# OKF 路径段合法字符（允许中文字符，不允许路径遍历 ../ 和控制字符）
_PATH_SEGMENT_RE = re.compile(r"^[^\x00-\x1f\\/:*?\"<>|]+$")


def validate_path_segment(segment: str) -> bool:
    """校验路径段是否合法（OKF 规范：字母/数字/下划线开头，允许 .-_）。"""
    return bool(_PATH_SEGMENT_RE.match(segment))


def validate_bundle_paths(knowledge_dir: Path) -> list[dict]:
    """扫描 bundle 所有路径，返回不合法的路径段。"""
    issues = []
    for md_file in sorted(knowledge_dir.rglob("*.md")):
        # 跳过隐藏/系统文件
        if md_file.name.startswith("."):
            continue
        rel = md_file.relative_to(knowledge_dir)
        for part in rel.parts:
            if not validate_path_segment(part.replace(".md", "")):
                issues.append({
                    "path": str(rel),
                    "segment": part,
                    "issue": "invalid_path_segment",
                })
    return issues


def regenerate_indexes(knowledge_dir: Path) -> dict:
    """从文件系统重建所有 index.md。

    扫描每个目录，解析 OKF frontmatter，按 type 分组生成 index.md。
    覆盖手动编辑的 index.md，解决漂移问题。
    返回 {category: {entries: N, types: [...]}}。
    """
    result: dict[str, dict] = {}

    for cat_dir in sorted(knowledge_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        if cat_dir.name.startswith(".") or cat_dir.name.startswith("_"):
            continue
        if cat_dir.name == "index":
            continue

        # 收集该目录下的概念文档
        entries: list[tuple[str, str, str, str]] = []  # (type, title, path, description)
        for md_file in sorted(cat_dir.glob("*.md")):
            if md_file.name in ("index.md", "log.md"):
                continue
            if md_file.name.startswith("."):
                continue

            fm = _read_frontmatter(md_file)
            entry_type = fm.get("type") or "Unknown"
            title = fm.get("title") or md_file.stem
            description = fm.get("description") or ""
            rel_path = str(md_file.relative_to(knowledge_dir))
            entries.append((entry_type, title, rel_path, description))

        if not entries:
            continue

        # 按 type 分组
        groups: dict[str, list[tuple]] = {}
        for t, title, path, desc in entries:
            groups.setdefault(t, []).append((title, path, desc))

        # 生成 index.md
        lines = []
        for t in sorted(groups.keys()):
            lines.append(f"## {t}")
            for title, path, desc in sorted(groups[t], key=lambda x: x[0].lower()):
                desc_seg = f" — {desc}" if desc else ""
                lines.append(f"- [{title}]({path}){desc_seg}")
            lines.append("")

        idx_file = cat_dir / "index.md"
        idx_file.write_text("\n".join(lines), encoding="utf-8")

        result[cat_dir.name] = {
            "entries": len(entries),
            "types": sorted(groups.keys()),
        }

    return result
