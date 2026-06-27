#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""知识导入：资源文件导入 + 知识条目存储 + 只读 PDF 提取。

子命令:
  store       - 存储知识条目（OKF v0.2）
  res         - 导入资源文件：归档到 res/ + 提取文本
  read        - 只读提取已归档 PDF 文本（无副作用，下游技能读原始研报用）

URL 抓取改由 LLM 用 firecrawl_scrape MCP 工具完成，不再内置 fetch 子命令。

用法:
  uv run km_import.py store --title "标题" --resource ... --source_type url --content-file /tmp/x.md
  uv run km_import.py res --file ~/xxx.pdf --target 腾讯控股
  uv run km_import.py read --file ~/.inv-knowledge/res/福耀玻璃/xxx.pdf --pages edges
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from git import is_repo, sync as _git_sync

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import slugify, build_entry, parse_index, now_iso, ENTRIES_DIR

_DEFAULT_KNOWLEDGE_DIR = Path.home() / ".inv-knowledge"
DEFAULT_MAX_CHARS = 12000
DEFAULT_MAX_PAGES = 30

DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _get_knowledge_dir() -> Path:
    env = os.environ.get("INV_KNOWLEDGE_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_KNOWLEDGE_DIR


KNOWLEDGE_DIR = _get_knowledge_dir()
REPO_BRANCH = "master"


# ─── store 子命令 ─────────────────────────────────────────


def _update_index(title: str, rel_path: str, description: str = "") -> None:
    """追加条目到 entries/index.md。"""
    entries_dir = KNOWLEDGE_DIR / ENTRIES_DIR
    entries_dir.mkdir(parents=True, exist_ok=True)
    index_file = entries_dir / "index.md"
    desc_segment = f" — {description}" if description else ""
    entry_line = f"- [{title}]({rel_path}){desc_segment}\n"
    try:
        with open(index_file, "a", encoding="utf-8") as f:
            f.write(entry_line)
    except (OSError, PermissionError) as e:
        print(f"Error: cannot write to index {index_file}: {e}", file=sys.stderr)
        raise


def _auto_description(content: str, title: str, max_len: int = 120) -> str:
    """从内容自动提取一句话描述。取第一个非标题非空段落。"""
    lines = content.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(("- ", "* ", "[", "|", ">")):
            continue
        desc = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
        desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)
        if len(desc) > 20:
            if len(desc) > max_len:
                desc = desc[:max_len].rsplit("。", 1)[0] + "。"
            return desc
    return f"{title}相关知识的整理与摘要。"


def _find_existing_by_title_and_resource(title: str, resource: str) -> list[dict]:
    """基于 title + resource 查找已存在的条目，用于去重。

    匹配规则：title 完全相同 或 (title 相似度 > 80% 且 resource 相同)。
    """
    from difflib import SequenceMatcher

    entries_dir = KNOWLEDGE_DIR / ENTRIES_DIR
    if not entries_dir.is_dir():
        return []

    existing = []
    for md_file in sorted(entries_dir.glob("*.md")):
        if md_file.name == "index.md":
            continue
        if md_file.name.startswith("."):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue
        fm_text = m.group(1)
        fm_title = ""
        fm_resource = ""
        for line in fm_text.split("\n"):
            if line.startswith("title:"):
                fm_title = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("resource:"):
                fm_resource = line.split(":", 1)[1].strip().strip('"').strip("'")

        if not fm_title:
            continue

        # 规则1: 标题完全相同
        if fm_title == title:
            existing.append({
                "title": fm_title,
                "path": str(md_file.relative_to(KNOWLEDGE_DIR)),
                "reason": "标题完全相同",
            })
            continue

        # 规则2: 标题相似度 > 80% 且 resource 相同
        similarity = SequenceMatcher(None, fm_title, title).ratio()
        if similarity > 0.8 and resource and fm_resource == resource:
            existing.append({
                "title": fm_title,
                "path": str(md_file.relative_to(KNOWLEDGE_DIR)),
                "reason": f"标题相似度 {similarity:.0%} 且 resource 相同",
            })

    return existing


def cmd_store(
    title: str,
    resource: str,
    content: str,
    *,
    source_type: str = "url",
    min_content_length: int = 100,
    tags: list[str] | None = None,
    entry_type: str = "Article",
    description: str = "",
) -> dict:
    """存储知识条目到 ~/.inv-knowledge/entries/，更新 index，git 同步。
    输出符合 OKF v0.2 格式。"""
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "error": f"{KNOWLEDGE_DIR} 不存在，请先运行 km_init.py",
        }

    # resource 校验
    if not resource or not resource.strip():
        return {
            "success": False,
            "error": "resource 为必填字段（OKF v0.2），请提供 --resource",
        }

    # source_type 校验
    valid_types = ("url", "pdf", "note")
    if source_type not in valid_types:
        return {
            "success": False,
            "error": f"source_type 无效: {source_type}，有效值: {', '.join(valid_types)}",
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

    slug = slugify(title)
    today = date.today().isoformat()
    rel_path = f"{ENTRIES_DIR}/{slug}.md"
    file_path = KNOWLEDGE_DIR / rel_path

    # 确保 entries/ 目录存在
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 同名文件加日期后缀避免覆盖
    if file_path.exists():
        slug = f"{slug}-{today}"
        rel_path = f"{ENTRIES_DIR}/{slug}.md"
        file_path = KNOWLEDGE_DIR / rel_path

    # 去重检查
    existing_entries = _find_existing_by_title_and_resource(title, resource)
    if existing_entries:
        return {
            "success": False,
            "error": f"疑似重复入库：已存在标题为「{existing_entries[0]['title']}」且 resource 为「{resource}」的条目（{existing_entries[0]['path']}）。如确认需要重新导入，请修改标题或 resource。",
            "existing": existing_entries,
        }

    entry_md = build_entry(
        title=title,
        description=description,
        resource=resource,
        content=content,
        entry_type=entry_type,
        source_type=source_type,
        tags=tags,
    )
    file_path.write_text(entry_md, encoding="utf-8")

    _update_index(title, rel_path, description)

    commit_msg = f"import: {title} ({source_type})"
    git_result = _git_sync(KNOWLEDGE_DIR, commit_msg, branch=REPO_BRANCH)

    # 追加 log.md
    try:
        log_file = KNOWLEDGE_DIR / "log.md"
        today_str = date.today().isoformat()
        log_entry = f"- [{title}]({rel_path}) — {entry_type} ({source_type})\n"
        existing = log_file.read_text(encoding="utf-8") if log_file.exists() else "# 变更日志\n\n"
        if f"## {today_str}" not in existing:
            existing = existing.rstrip() + f"\n\n## {today_str}\n"
        log_file.write_text(existing.rstrip() + "\n" + log_entry + "\n", encoding="utf-8")
    except Exception:
        pass

    # 图谱不在此更新：store 调用太频繁，改为 km_lint --fix 或用户 /km_graph 时生成
    return {
        "success": True,
        "path": rel_path,
        "type": entry_type,
        "source_type": source_type,
        "resource": resource,
        "description": description,
        **git_result,
    }


# ─── PDF 导入 ────────────────────────────────────────────


def _filename_date(name: str) -> str | None:
    m = DATE_PREFIX.match(name)
    return m.group(1) if m else None


def _filename_date_as_date(name: str) -> date | None:
    raw = _filename_date(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _timeliness_label(report_date: date | None, as_of: date | None = None) -> str:
    if report_date is None:
        return "unknown"
    ref = as_of or date.today()
    days = (ref - report_date).days
    if days <= 90:
        return "fresh"
    if days <= 183:
        return "aging"
    return "stale"


def _md5_file(path: Path) -> str:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except (FileNotFoundError, PermissionError):
        return ""
    return h.hexdigest()


def _ensure_pymupdf_venv():
    venv_dir = Path("/tmp/research-pdf-venv")
    if not venv_dir.exists():
        subprocess.run([sys.executable, "-m", "venv", "--clear", str(venv_dir)], check=True, capture_output=True)
        subprocess.run([str(venv_dir / "bin" / "pip"), "install", "-q", "pymupdf"], check=True, capture_output=True)


def _need_fitz():
    try:
        import fitz
        return fitz
    except ImportError:
        print("缺少 pymupdf，正在安装...", file=sys.stderr)
        _ensure_pymupdf_venv()
        # 将 venv 的 site-packages 加入 sys.path 以便导入
        import glob as _glob
        venv_site = list(Path("/tmp/research-pdf-venv/lib").glob("python*/site-packages"))
        if venv_site:
            sys.path.insert(0, str(venv_site[0]))
        try:
            import fitz
            return fitz
        except ImportError:
            return None


def _page_indices(page_count: int, mode: str, first_n: int, max_pages: int) -> list[int]:
    if page_count <= 0:
        return []
    effective = min(page_count, max_pages)
    if mode == "all":
        return list(range(effective))
    if mode == "first-n":
        return list(range(min(first_n or 3, effective)))
    idxs = {0}
    if effective > 1:
        idxs.add(effective - 1)
    return sorted(idxs)


def _archive_file(src: Path, target_folder: str) -> Path:
    """归档文件到 res/{target_folder}/，返回目标路径。"""
    res_dir = KNOWLEDGE_DIR / "res"
    target_dir = res_dir / target_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / src.name

    # 已在目标位置
    try:
        if src.resolve() == target_path.resolve():
            return target_path
    except Exception:
        pass

    if target_path.exists():
        if _md5_file(src) == _md5_file(target_path):
            print(f"# 跳过重复: {src.name}", file=sys.stderr)
            try:
                src.unlink()
            except Exception:
                pass
            return target_path
        stem, suffix = target_path.stem, target_path.suffix
        counter = 2
        while target_path.exists():
            target_path = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    shutil.move(str(src), str(target_path))
    print(f"# 归档: {src.name} → res/{target_folder}/", file=sys.stderr)
    return target_path


def _extract_pdf_text(path: Path, pages_mode: str, first_n: int, max_chars: int, max_pages: int) -> str | None:
    """提取 PDF 文本。"""
    fitz_module = _need_fitz()
    if fitz_module is None:
        return None
    try:
        doc = fitz_module.open(path)
    except Exception as exc:
        print(f"# 跳过无法打开的 PDF: {path.name} ({exc})", file=sys.stderr)
        return None
    try:
        n_pages = doc.page_count
        idxs = _page_indices(n_pages, pages_mode, first_n, max_pages)
        fd = _filename_date_as_date(path.name)
        tl = _timeliness_label(fd)
        parts: list[str] = [f"### {path.name}  (pages={n_pages}, timeliness={tl})\n"]
        used = len(parts[0])
        for i in idxs:
            text = (doc.load_page(i).get_text() or "").strip()
            if not text:
                continue
            block = f"\n--- page {i + 1} ---\n{text}"
            if used + len(block) > max_chars:
                block = block[:max(0, max_chars - used)] + "\n…(截断)"
                parts.append(block)
                break
            parts.append(block)
            used += len(block)
        if n_pages > max_pages:
            parts.append(f"\n…(仅解析前 {max_pages} 页，共 {n_pages} 页)\n")
        return "".join(parts) + "\n"
    finally:
        doc.close()


def _regenerate_res_index() -> dict:
    res_dir = KNOWLEDGE_DIR / "res"
    if not res_dir.is_dir():
        return {"entries": 0}
    folders: dict[str, list[str]] = {}
    for f in sorted(res_dir.rglob("*.pdf")):
        if f.name.startswith("."):
            continue
        folder = f.parent.name if f.parent != res_dir else "_root"
        folders.setdefault(folder, []).append(f.name)
    if not folders:
        return {"entries": 0}
    lines = ["# res 资源索引\n"]
    for folder in sorted(folders.keys()):
        lines.append(f"## {folder}")
        for pdf_name in sorted(folders[folder]):
            pct_name = pdf_name.replace("[", "%5B").replace("]", "%5D")
            lines.append(f"- [{pdf_name}]({folder}/{pct_name})")
        lines.append("")
    (res_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    count = sum(len(v) for v in folders.values())
    print(f"# res/index.md 已更新: {count} 份资源", file=sys.stderr)
    return {"entries": count}


def cmd_res(args: argparse.Namespace) -> int:
    """res 子命令：导入资源文件（归档 + 提取文本到 stdout）。"""
    if not args.target:
        print("请指定 --target（如 腾讯控股、行业研究-互联网）", file=sys.stderr)
        return 1

    texts = []
    for p in args.file:
        src = Path(p).expanduser()
        if not src.exists():
            print(f"# 文件不存在: {src}", file=sys.stderr)
            continue
        archived = _archive_file(src, args.target)
        text = _extract_pdf_text(archived, args.pages, args.first_n,
                                 args.max_chars, args.max_pages)
        if text:
            texts.append(text)

    if not texts:
        return 0

    sys.stdout.write("\n".join(texts))
    _regenerate_res_index()

    if is_repo(KNOWLEDGE_DIR):
        _git_sync(KNOWLEDGE_DIR, f"import: PDF → res/{args.target}/")

    # 更新图谱（res 操作不频繁）
    try:
        from km_visualize import cmd_visualize
        cmd_visualize()
    except Exception:
        pass
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    """read 子命令：只读提取已归档 PDF 文本，无副作用。

    用于下游技能读取 res/ 下原始研报原文，不触发归档/索引重建/git push/图谱重建。
    与 res 的区别：res 是导入（归档+提取+入库），read 是纯读取已存在文件。
    """
    texts = []
    for p in args.file:
        src = Path(p).expanduser()
        if not src.exists():
            print(f"# 文件不存在: {src}", file=sys.stderr)
            continue
        text = _extract_pdf_text(src, args.pages, args.first_n,
                                 args.max_chars, args.max_pages)
        if text:
            texts.append(text)

    if not texts:
        return 0

    sys.stdout.write("\n".join(texts))
    return 0


# ─── main ─────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="知识导入工具 (OKF v0.2)")
    sub = parser.add_subparsers(dest="command")

    # res 子命令
    p_res = sub.add_parser("res", help="导入资源文件：归档 + 提取文本")
    p_res.add_argument("--file", action="append", required=True, help="资源文件路径（可多次指定）")
    p_res.add_argument("--target", required=True, help="归档目标文件夹（如 腾讯控股、行业研究-互联网）")
    p_res.add_argument("--pages", choices=("edges", "all", "first-n"), default="edges")
    p_res.add_argument("--first-n", type=int, default=3)
    p_res.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    p_res.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)

    p_store = sub.add_parser("store", help="存储知识条目（OKF v0.2 格式）")
    p_store.add_argument("--title", required=True)
    p_store.add_argument("--resource", required=True, help="来源 URL 或文件路径（OKF v0.2 必需）")
    p_store.add_argument("--source_type", default="url", choices=("url", "pdf", "note"),
                         help="来源类型（OKF v0.2 必需），默认 url")
    p_store.add_argument("--content", default="", help="Markdown 正文内容。直接传入内容，或使用 '-' 从 stdin 读取")
    p_store.add_argument("--content-file", help="从文件读取 Markdown 内容（与 --content 互斥）")
    p_store.add_argument("--description", default="", help="一句话描述（OKF 必需）。不提供则自动从正文第一段提取")
    p_store.add_argument("--type", default="Article", help="知识类型（OKF 必需）。默认 Article")
    p_store.add_argument("--min-content-length", type=int, default=100, help="内容最小长度校验（默认 100 字符）")
    p_store.add_argument("--tags", default="", help="标签列表，逗号分隔。示例: python,async,performance")

    # read 子命令：只读提取已归档 PDF（无副作用，下游技能用）
    p_read = sub.add_parser("read", help="只读提取已归档 PDF 文本（无副作用，下游技能读原始研报用）")
    p_read.add_argument("--file", action="append", required=True, help="res/ 下 PDF 路径（可多次指定）")
    p_read.add_argument("--pages", choices=("edges", "all", "first-n"), default="edges")
    p_read.add_argument("--first-n", type=int, default=3)
    p_read.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    p_read.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "res":
        sys.exit(cmd_res(args))
    elif args.command == "read":
        sys.exit(cmd_read(args))
    elif args.command == "store":
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
            resource=args.resource,
            content=content,
            source_type=getattr(args, 'source_type', 'url'),
            min_content_length=min_length,
            tags=tags,
            entry_type=getattr(args, 'type', 'Article'),
            description=getattr(args, 'description', ''),
        )
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
