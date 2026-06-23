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
  from knowledge import parse_index, build_entry, slugify, search_entries, validate_okf, regenerate_index, find_cross_references
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timezone, timedelta
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


def migrate_index(knowledge_dir: Path) -> None:
    """旧格式迁移：Index.md → entries/index.md，index/*.md → entries/index.md。"""
    # 迁移1: 根 Index.md → entries/index.md
    old_root_index = knowledge_dir / "Index.md"
    if old_root_index.exists():
        entries_dir = knowledge_dir / ENTRIES_DIR
        entries_dir.mkdir(parents=True, exist_ok=True)
        idx_file = entries_dir / "index.md"
        content = old_root_index.read_text(encoding="utf-8")
        if idx_file.exists():
            idx_file.write_text(idx_file.read_text(encoding="utf-8").rstrip() + "\n" + content, encoding="utf-8")
        else:
            idx_file.write_text(content, encoding="utf-8")
        old_root_index.rename(old_root_index.with_suffix(".md.bak"))

    # 迁移2: index/category.md → entries/index.md (合并)
    old_index_dir = knowledge_dir / "index"
    if old_index_dir.is_dir():
        entries_dir = knowledge_dir / ENTRIES_DIR
        entries_dir.mkdir(parents=True, exist_ok=True)
        idx_file = entries_dir / "index.md"
        existing = idx_file.read_text(encoding="utf-8") if idx_file.exists() else ""
        for f in sorted(old_index_dir.glob("*.md")):
            new_content = f.read_text(encoding="utf-8")
            existing = existing.rstrip() + "\n" + new_content
            f.unlink()
        idx_file.write_text(existing.rstrip() + "\n", encoding="utf-8")
        try:
            old_index_dir.rmdir()
        except OSError:
            pass

    # 迁移3: 各分类目录下的 index.md → entries/index.md (合并)
    for cat_dir in sorted(knowledge_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        if cat_dir.name.startswith(".") or cat_dir.name.startswith("_"):
            continue
        if cat_dir.name in (ENTRIES_DIR, "reports", "res", "index"):
            continue
        idx_file = cat_dir / "index.md"
        if idx_file.exists():
            entries_dir = knowledge_dir / ENTRIES_DIR
            entries_dir.mkdir(parents=True, exist_ok=True)
            target_idx = entries_dir / "index.md"
            existing = target_idx.read_text(encoding="utf-8") if target_idx.exists() else ""
            content = idx_file.read_text(encoding="utf-8")
            target_idx.write_text(existing.rstrip() + "\n" + content, encoding="utf-8")
            idx_file.unlink()


def parse_index(knowledge_dir: Path) -> tuple[list[dict], set[str]]:
    """解析 entries/ 目录下所有 OKF 知识条目。

    返回:
      entries: [{title, path, type, description, timestamp, resource, source_type, tags}, ...]
      indexed_paths: 所有条目相对路径集合
    """
    migrate_index(knowledge_dir)

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


def _split_query(query: str) -> list[str]:
    """拆分查询为多词：长词优先，逐词递减。中文字符逐字+双字组合。"""
    words = []
    q = query.strip()
    # 完整短语（最高权重）
    words.append(q)
    # 空格分隔的词
    parts = [p.strip() for p in q.split() if len(p.strip()) >= 1]
    words.extend(parts)
    # 中文双字组合（"福耀玻璃"→["福耀","玻璃"]）
    if any('一' <= c <= '鿿' for c in q):
        cleaned = re.sub(r'[^一-鿿]', '', q)
        for i in range(len(cleaned) - 1):
            words.append(cleaned[i:i+2])
    return list(dict.fromkeys(words))  # 去重保序


def _match_score(title: str, desc: str, tags: list[str], content_text: str, query_words: list[str]) -> tuple[float, dict]:
    """多词加权匹配评分。返回 (score, match_detail)。"""
    title_l = title.lower()
    desc_l = desc.lower()
    content_l = content_text[:3000].lower()  # 前 3000 字符
    tag_str = " ".join(t.lower() for t in tags)

    detail: dict[str, list[str]] = {"title": [], "desc": [], "tag": [], "content": []}
    score = 0.0

    # 权重递减：完整短语 > 空格分词 > 中文双字 > 超长截断
    weights = [4.0, 3.0, 2.0, 1.0]
    for i, word in enumerate(query_words):
        w = weights[i] if i < len(weights) else 0.5

        # 标题匹配（权重×3）
        if word.lower() in title_l:
            score += w * 3
            detail["title"].append(word)

        # 标签匹配（权重×2，支持部分匹配如 "fuyao" 匹配 "fuyao-glass"）
        for t in tags:
            if word.lower() in t.lower() or t.lower() in word.lower():
                score += w * 2
                detail["tag"].append(f"{word}→{t}")
                break

        # 描述匹配（权重×2）
        if word.lower() in desc_l:
            score += w * 2
            detail["desc"].append(word)

        # 内容匹配（权重×1）
        if word.lower() in content_l:
            score += w * 1
            detail["content"].append(word)

    return score, detail


def search_entries(knowledge_dir: Path, query: str,
                   entry_type: str | None = None,
                   tag: str | None = None,
                   source_type: str | None = None,
                   date_after: str | None = None,
                   date_before: str | None = None) -> list[dict]:
    """搜索知识库条目，多词加权评分排序。

    返回匹配条目列表，按综合评分降序排列。score=0 的结果不返回。
    """
    query_words = _split_query(query)
    entries_dir = knowledge_dir / ENTRIES_DIR
    if not entries_dir.is_dir():
        return []

    # 日期过滤
    after_d = date.fromisoformat(date_after) if date_after else None
    before_d = date.fromisoformat(date_before) if date_before else None

    results = []
    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md" or md_file.name.startswith("."):
            continue

        fm = _read_frontmatter(md_file)
        title = fm.get("title") or md_file.stem
        desc = fm.get("description") or ""
        etype = fm.get("type") or ""
        stype = fm.get("source_type") or ""
        etags = _parse_tags(fm.get("tags", ""))
        timestamp = fm.get("timestamp") or ""
        resource = fm.get("resource") or ""
        rel_path = str(md_file.relative_to(knowledge_dir))

        # 日期过滤
        if after_d or before_d:
            try:
                ts_date = date.fromisoformat(timestamp[:10]) if timestamp else None
                if ts_date:
                    if after_d and ts_date < after_d:
                        continue
                    if before_d and ts_date > before_d:
                        continue
            except ValueError:
                pass

        # 过滤器
        if entry_type and etype != entry_type:
            continue
        if tag and tag not in etags:
            continue
        if source_type and stype != source_type:
            continue

        # 读取正文（用于内容匹配）
        content_text = ""
        try:
            content_text = md_file.read_text(encoding="utf-8")
        except Exception:
            pass

        score, detail = _match_score(title, desc, etags, content_text, query_words)
        if score <= 0:
            continue

        # 从 snippet 提取交叉引用
        refs = []
        ref_re = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')
        for m in ref_re.finditer(content_text):
            refs.append({"title": m.group(1), "path": m.group(2)})

        results.append({
            "title": title,
            "path": rel_path,
            "type": etype,
            "source_type": stype,
            "description": desc,
            "timestamp": timestamp,
            "resource": resource,
            "tags": etags,
            "score": round(score, 1),
            "match_detail": detail,
            "cross_refs": refs[:5],  # 最多 5 个交叉引用
        })

    # 按评分降序
    results.sort(key=lambda x: -x["score"])

    # 去重：去掉标题高度相似的低分条目
    seen_titles: set[str] = set()
    deduped = []
    for r in results:
        t = r["title"].lower()[:30]
        if t in seen_titles:
            continue
        seen_titles.add(t)
        deduped.append(r)

    return deduped


def _search_res_files(knowledge_dir: Path, query: str) -> list[dict]:
    """搜索 res/ 下文件名匹配的 PDF，返回匹配列表。"""
    res_dir = knowledge_dir / "res"
    if not res_dir.is_dir():
        return []
    query_lower = query.lower()
    matches = []
    for f in sorted(res_dir.rglob("*.pdf")):
        if f.name.startswith("."):
            continue
        if query_lower in f.name.lower():
            matches.append({
                "name": f.name,
                "folder": f.parent.name if f.parent != res_dir else "",
                "path": str(f.relative_to(knowledge_dir)),
            })
    return matches


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


# ── 交叉关联发现 ─────────────────────────────────────────────────────────

def find_cross_references(knowledge_dir: Path, min_score: float = 1.0) -> list[dict]:
    """扫描知识库，自动发现可建立交叉引用的条目对。min_score=1.0 确保同标的+共享标签+关键词重叠都能匹配。"""
    entries_dir = knowledge_dir / ENTRIES_DIR
    if not entries_dir.is_dir():
        return []

    all_entries: list[dict] = []
    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md":
            continue
        if md_file.name.startswith("."):
            continue
        fm = _read_frontmatter(md_file)
        if not fm.get("type"):
            continue
        try:
            body = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        m = FRONTMATTER_RE.match(body)
        body_text = body[m.end():].strip() if m else body

        all_entries.append({
            "path": str(md_file.relative_to(knowledge_dir)),
            "title": fm.get("title", ""),
            "description": fm.get("description", ""),
            "tags": _parse_tags(fm.get("tags", "")),
            "source_type": fm.get("source_type", ""),
            "body": body_text,
        })

    def _keywords(entry: dict) -> set[str]:
        kw = set()
        text = f"{entry['title']} {entry.get('description', '')}"
        for i in range(len(entry['title']) - 1):
            bigram = entry["title"][i:i+2]
            if not re.search(r"[^\w一-鿿]", bigram):
                kw.add(bigram.lower())
        for w in re.findall(r"[A-Za-z]{3,}", text):
            kw.add(w.lower())
        for code in re.findall(r"\b\d{4,6}\b", text):
            kw.add(code)
        body_words = re.findall(r"[\w一-鿿]{2,}", entry.get("body", "")[:2000])
        word_counts = Counter(w.lower() for w in body_words if len(w) >= 2)
        for w, c in word_counts.most_common(30):
            if c >= 3:
                kw.add(w)
        return kw

    stopwords = {"的","了","是","在","和","也","就","都","而","及","与","或","但","不","这","那","有","个","为",
                 "the","and","for","with","this","that","from","are","has","its","will","can","all","not","but"}

    results = []
    for i in range(len(all_entries)):
        for j in range(i + 1, len(all_entries)):
            a, b = all_entries[i], all_entries[j]
            score = 0.0
            reasons = []

            # 共享 tag（权重 2.0/tag）
            shared_tags = set(a["tags"]) & set(b["tags"])
            if shared_tags:
                score += len(shared_tags) * 2.0
                reasons.append(f"共享标签: {', '.join(list(shared_tags)[:3])}")

            # 同标的（共享标的标签如 fuyao-glass，额外 +3.0）
            ticker_tags = {t for t in shared_tags if not t.startswith("#") and not t.startswith("202") and t not in
                          {"competitive-advantage","risk-factor","valuation","profit-trend","fx-risk","business-model",
                           "technology-moat","sentiment","capital-flow","margin-trading","manufacturing-excellence",
                           "baseline-data","official-source","third-party-analysis","news-roundup","industry-policy",
                           "semiconductor","ai","cloud-computing","social-media","memory-chip","ecommerce"}}
            if ticker_tags:
                score += 3.0
                reasons.append(f"同标的: {', '.join(list(ticker_tags)[:2])}")

            # 同 source_type（+0.5）
            if a.get("source_type") and a["source_type"] == b.get("source_type"):
                score += 0.5

            # 标题/描述关键词重叠（权重 0.5/词）
            kw_a = _keywords(a) - stopwords
            kw_b = _keywords(b) - stopwords
            shared = kw_a & kw_b
            if shared:
                score += len(shared) * 0.5
                if len(shared) >= 3:
                    reasons.append(f"共同关键词({len(shared)}): {', '.join(list(shared)[:4])}")

            # 标题重叠（一个标题的关键词出现在另一个标题中，+1.0）
            title_words_a = set(re.findall(r"[\w一-鿿]{2,}", a["title"].lower()))
            title_words_b = set(re.findall(r"[\w一-鿿]{2,}", b["title"].lower()))
            title_overlap = title_words_a & title_words_b - stopwords
            if title_overlap:
                score += 1.0

            if score >= min_score:
                results.append({
                    "source": a["path"],
                    "target": b["path"],
                    "source_title": a["title"],
                    "target_title": b["title"],
                    "score": round(score, 1),
                    "reason": "; ".join(reasons) if reasons else "内容相似",
                })

    results.sort(key=lambda x: -x["score"])
    return results


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
