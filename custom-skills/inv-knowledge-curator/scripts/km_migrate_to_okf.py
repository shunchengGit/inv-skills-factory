#!/usr/bin/env python3
"""将旧格式知识条目批量迁移为 OKF v0.1 格式。

旧格式:
  ---
  url: https://...
  imported: 2026-05-27
  category: investing
  ---

OKF v0.1:
  ---
  type: Article
  title: xxx
  description: xxx
  timestamp: 2026-05-27T00:00:00+08:00
  resource: https://...
  ---

用法:
  python3 km_migrate_to_okf.py           # 预览变更（dry-run）
  python3 km_migrate_to_okf.py --apply   # 执行迁移
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import validate_okf, now_iso

KNOWLEDGE_DIR = Path.home() / ".inv-knowledge"
LOCAL_TZ = timezone(timedelta(hours=8))

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_old_frontmatter(text: str) -> tuple[dict, str]:
    """解析旧格式 frontmatter，返回 (fm_dict, body_text)。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    body = text[m.end():].strip()
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, body


def extract_title(body: str, file_path: Path) -> str:
    """从正文提取标题。"""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    # fallback: 文件名
    return file_path.stem


def extract_description(body: str, title: str) -> str:
    """从正文第一段提取描述。"""
    lines = body.splitlines()
    skip_headers = True
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 跳过头、摘要标记、HTML 注释
        if stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        if stripped.startswith("## 摘要"):
            skip_headers = False
            continue
        if skip_headers and stripped.startswith("##"):
            continue
        # 跳过列表、引用、链接
        if stripped.startswith(("- ", "* ", "[", "|", ">", "```")):
            continue
        # 清理 markdown 标记
        desc = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
        desc = re.sub(r"\*\*([^*]+)\*\*", r"\1", desc)
        desc = re.sub(r"`([^`]+)`", r"\1", desc)
        if len(desc) > 20:
            if len(desc) > 120:
                desc = desc[:120].rsplit("。", 1)[0] + "。"
            return desc
    return f"{title}。"


def migrate_file(file_path: Path, dry_run: bool = True) -> dict:
    """迁移单个文件。"""
    rel = str(file_path.relative_to(KNOWLEDGE_DIR))
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"path": rel, "status": "error", "error": str(e)}

    old_fm, body = parse_old_frontmatter(text)

    # 检查是否已是 OKF 格式
    if "type" in old_fm and "timestamp" in old_fm:
        return {"path": rel, "status": "skip", "reason": "已是 OKF 格式"}

    title = extract_title(body, file_path)
    description = extract_description(body, title)

    # 时间戳
    imported = old_fm.get("imported", "")
    if imported:
        try:
            dt = datetime.strptime(imported, "%Y-%m-%d")
            timestamp = dt.replace(tzinfo=LOCAL_TZ).isoformat()
        except ValueError:
            timestamp = now_iso()
    else:
        timestamp = now_iso()

    # 构建 OKF frontmatter
    resource = old_fm.get("url", "")
    tags = old_fm.get("tags", "")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    lines = [
        "---",
        f"type: Article",
        f"title: {title}",
        f"description: {description}",
        f"timestamp: {timestamp}",
    ]
    if resource:
        lines.append(f"resource: {resource}")
    if tag_list:
        lines.append(f"tags: [{', '.join(tag_list)}]")
    lines.append("---")

    new_text = "\n".join(lines) + "\n\n" + body

    if not dry_run:
        file_path.write_text(new_text, encoding="utf-8")

    # 验证
    if dry_run:
        # 临时写文件验证
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(new_text)
            tmp = Path(f.name)
        result = validate_okf(tmp)
        tmp.unlink()
    else:
        result = validate_okf(file_path)

    return {
        "path": rel,
        "status": "preview" if dry_run else "migrated",
        "title": title,
        "description": description[:60],
        "valid": result["valid"],
        "errors": result.get("errors", []),
    }


def main():
    dry_run = "--apply" not in sys.argv

    if dry_run:
        print("🔍 DRY-RUN 模式（预览变更，不实际写入）\n")
    else:
        print("⚠️  MIGRATE 模式（将实际写入文件）\n")
        print("   按 Ctrl+C 取消...")
        try:
            import time
            time.sleep(2)
        except KeyboardInterrupt:
            print("已取消")
            return

    results = []
    for md_file in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        if md_file.parent.name == "index":
            continue
        if md_file.name in ("index.md", "log.md", "README.md"):
            continue
        if md_file.suffix == ".bak":
            continue

        r = migrate_file(md_file, dry_run=dry_run)
        icon = {"preview": "🔍", "migrated": "✅", "skip": "⏭️", "error": "❌"}.get(r["status"], "?")
        title = r.get("title", "")[:40]
        desc = r.get("description", "")[:50]
        print(f"  {icon} {r['status']:8s} | {title:<40s} | {desc}")
        results.append(r)

    migrated = sum(1 for r in results if r["status"] in ("preview", "migrated"))
    skipped = sum(1 for r in results if r["status"] == "skip")
    errors = sum(1 for r in results if r["status"] == "error")
    invalid = sum(1 for r in results if r["status"] in ("preview", "migrated") and not r["valid"])

    print(f"\n{'─' * 60}")
    print(f"总计: {len(results)} | 需迁移: {migrated} | 已是OKF: {skipped} | 错误: {errors}")
    if invalid:
        print(f"⚠  {invalid} 个条目迁移后 OKF 校验不通过")
    if dry_run:
        print(f"\n确认无误后运行: python3 km_migrate_to_okf.py --apply")


if __name__ == "__main__":
    main()
