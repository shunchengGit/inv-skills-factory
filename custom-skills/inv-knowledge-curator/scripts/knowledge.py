"""知识库共享工具：索引解析、迁移、条目格式（OKF v0.2）、搜索。

OKF (Open Knowledge Format) v0.2 规范：
  - 每个知识条目是一个 UTF-8 markdown 文件，含 YAML frontmatter
  - 必需 frontmatter 字段: type, title, description, timestamp, resource, source_type
  - 推荐字段: tags
  - 目录结构: entries/ (扁平), res/{ticker}/ (原始 PDF)

v0.1 → v0.2 变更：
  - resource 从推荐升级为必需
  - 新增 source_type 字段 (url | pdf | note)
  - 目录从 investing/ 改为 entries/，reports/ 改为 res/

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
  from knowledge import parse_index, build_entry, slugify, validate_okf, regenerate_index, regenerate_tag_indexes
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ENTRY_LINE_RE = re.compile(r"^-\s+\[(.+?)\]\((.+?)\)\s*[—–-]\s*(.+)")
SECTION_RE = re.compile(r"^##\s+(.+)")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)

# OKF v0.2 必需字段: resource 和 source_type 现在是必需的
OKF_REQUIRED = ("type", "title", "description", "timestamp", "resource", "source_type")
# 有效的 source_type 取值
VALID_SOURCE_TYPES = ("url", "pdf", "note")
# 本地时区
LOCAL_TZ = timezone(timedelta(hours=8))  # Asia/Shanghai

# 知识条目存储目录 (相对于知识库根目录)
ENTRIES_DIR = "entries"
# 原始资源存储目录
RES_DIR = "res"
RES_DIR_NAME = "res"


def parse_index(knowledge_dir: Path) -> tuple[list[dict], set[str]]:
    """解析 entries/ 目录下所有 OKF 知识条目。

    返回:
      entries: [{title, path, type, description, timestamp, resource, source_type, tags}, ...]
      indexed_paths: 所有条目相对路径集合
    """
    entries_dir = knowledge_dir / ENTRIES_DIR
    if not entries_dir.is_dir():
        return [], set()

    entries: list[dict] = []
    indexed_paths: set[str] = set()

    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md":
            continue
        if md_file.name.startswith("."):
            continue

        fm = _read_frontmatter(md_file)
        rel_path = str(md_file.relative_to(knowledge_dir))
        entry = {
            "title": fm.get("title") or md_file.stem,
            "path": rel_path,
            "type": fm.get("type") or "Unknown",
            "description": fm.get("description") or "",
            "timestamp": fm.get("timestamp") or "",
            "resource": fm.get("resource") or "",
            "source_type": fm.get("source_type") or "",
            "tags": _parse_tags(fm.get("tags", "")),
        }
        entries.append(entry)
        indexed_paths.add(rel_path)

    return entries, indexed_paths


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
    resource: str = "",
    content: str = "",
    *,
    entry_type: str = "Article",
    source_type: str = "url",
    tags: list[str] | None = None,
    timestamp: str | None = None,
) -> str:
    """构建符合 OKF v0.2 的知识条目 markdown。

    必需 frontmatter: type, title, description, timestamp, resource, source_type
    推荐: tags
    """
    ts = timestamp or now_iso()
    tags_line = f"tags: [{', '.join(tags)}]" if tags else ""

    lines = [
        "---",
        f"type: {entry_type}",
        f"title: {title}",
        f"description: {description}",
        f"timestamp: {ts}",
        f"resource: {resource}",
        f"source_type: {source_type}",
    ]
    if tags_line:
        lines.append(tags_line)
    lines.append("---")

    frontmatter = "\n".join(lines)
    body = content.strip() if content.strip() else f"# {title}\n"

    return f"{frontmatter}\n\n{body}\n"


def validate_okf(file_path: Path) -> dict:
    """校验单个知识文件是否符合 OKF v0.2。

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
        if not re.match(r"^\d{4}-\d{2}-\d{2}", ts):
            result["valid"] = False
            result["errors"].append(f"timestamp 格式无效: {ts}（期望 ISO 8601）")

    # source_type 取值校验
    if "source_type" in fm and fm["source_type"]:
        st = fm["source_type"].strip().strip('"').strip("'")
        if st not in VALID_SOURCE_TYPES:
            result["warnings"].append(f"source_type 值无效: {st}（期望: {', '.join(VALID_SOURCE_TYPES)}）")

    # 推荐字段缺失
    if "tags" not in fm or not fm["tags"]:
        result["warnings"].append("缺少推荐字段: tags")

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


# ── 索引重建 ─────────────────────────────────────────────────────────────

def regenerate_index(knowledge_dir: Path) -> dict:
    """从 entries/ 目录重建 index.md。

    扫描所有 OKF 条目，按 type 分组生成 entries/index.md。
    返回 {"entries": N, "types": [...]}
    """
    entries_dir = knowledge_dir / ENTRIES_DIR
    if not entries_dir.is_dir():
        return {"entries": 0, "types": []}

    # 收集所有条目
    typed_entries: dict[str, list[tuple[str, str, str]]] = {}  # type -> [(title, path, desc)]
    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md":
            continue
        if md_file.name.startswith("."):
            continue
        fm = _read_frontmatter(md_file)
        etype = fm.get("type") or "Unknown"
        title = fm.get("title") or md_file.stem
        desc = fm.get("description") or ""
        rel_path = str(md_file.relative_to(knowledge_dir))
        typed_entries.setdefault(etype, []).append((title, rel_path, desc))

    if not typed_entries:
        return {"entries": 0, "types": []}

    # 生成 index.md
    lines = []
    for t in sorted(typed_entries.keys()):
        lines.append(f"## {t}")
        for title, path, desc in sorted(typed_entries[t], key=lambda x: x[0].lower()):
            desc_seg = f" — {desc}" if desc else ""
            lines.append(f"- [{title}]({path}){desc_seg}")
        lines.append("")

    idx_file = entries_dir / "index.md"
    idx_file.write_text("\n".join(lines), encoding="utf-8")

    total = sum(len(v) for v in typed_entries.values())
    return {"entries": total, "types": sorted(typed_entries.keys())}


def regenerate_tag_indexes(knowledge_dir: Path) -> dict:
    """按标签生成索引页：entries/by-tag/{tag}.md，列出所有含该标签的条目。"""
    entries_dir = knowledge_dir / ENTRIES_DIR
    tag_dir = entries_dir / "by-tag"
    if not entries_dir.is_dir():
        return {"tags": 0, "entries": 0}

    tag_entries: dict[str, list[tuple[str, str, str]]] = {}  # tag → [(title, path, type)]

    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md" or md_file.name.startswith("."):
            continue
        fm = _read_frontmatter(md_file)
        title = fm.get("title") or md_file.stem
        etype = fm.get("type") or ""
        rel_path = str(md_file.relative_to(knowledge_dir))
        for tag in _parse_tags(fm.get("tags", "")):
            tag_entries.setdefault(tag, []).append((title, rel_path, etype))

    # 清理旧文件
    if tag_dir.exists():
        for old in tag_dir.glob("*.md"):
            old.unlink()
    tag_dir.mkdir(parents=True, exist_ok=True)

    total_refs = 0
    for tag, items in sorted(tag_entries.items()):
        lines = [f"# {tag}\n"]
        for title, path, etype in sorted(items, key=lambda x: x[0].lower()):
            lines.append(f"- [{title}]({path}) — {etype}")
        (tag_dir / f"{tag}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        total_refs += len(items)

    return {"tags": len(tag_entries), "total_refs": total_refs}


def find_backlinks(knowledge_dir: Path, target_path: str) -> list[dict]:
    """查找哪些条目引用了 target_path。"""
    entries_dir = knowledge_dir / ENTRIES_DIR
    if not entries_dir.is_dir():
        return []

    LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')
    backlinks = []
    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md" or md_file.name.startswith("."):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in LINK_RE.finditer(text):
            ref_path = m.group(2)
            # Normalize: entries/foo.md == foo.md
            if ref_path == target_path or ref_path.endswith("/" + target_path) or ("/" + ref_path == target_path):
                backlinks.append({
                    "from_title": _read_frontmatter(md_file).get("title") or md_file.stem,
                    "from_path": str(md_file.relative_to(knowledge_dir)),
                    "label": m.group(1),
                })
                break  # 只报告一次
    return backlinks


def _parse_tags(tags_val) -> list[str]:
    """解析 tags 字段（兼容字符串和列表）。"""
    if isinstance(tags_val, list):
        return [str(t).strip() for t in tags_val if t]
    if isinstance(tags_val, str):
        s = tags_val.strip().strip("[]")
        if not s:
            return []
        return [t.strip().strip("\"'") for t in s.split(",") if t.strip()]
    return []


def get_all_tags(knowledge_dir: Path) -> Counter:
    """收集所有标签及其出现频率。"""
    entries_dir = knowledge_dir / ENTRIES_DIR
    tag_counts: Counter = Counter()
    if not entries_dir.is_dir():
        return tag_counts
    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md" or md_file.name.startswith("."):
            continue
        fm = _read_frontmatter(md_file)
        for t in _parse_tags(fm.get("tags", "")):
            tag_counts[t] += 1
    return tag_counts
