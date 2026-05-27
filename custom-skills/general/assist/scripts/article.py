#!/usr/bin/env python3
"""文章抓取、总结与归档

原则：
- save: Playwright 能抓就抓，抓不到就直说失败。不 fallback，不偷换。
- 抓取原文存入技能内部 .claw/raw/，不污染 Assist 工作目录。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 路径定义
WORKSPACE = Path(os.environ.get("ASSIST_HOME", "/Users/chengshun/Assist"))
AI_LEARN_DIR = WORKSPACE / "AI学习"
INDEX_MD = AI_LEARN_DIR / "INDEX.md"

# Skill 运行时数据目录
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CLAW_DIR = SKILL_DIR / ".claw"
RAW_DIR = CLAW_DIR / "raw"
JSON_INDEX = CLAW_DIR / "index.json"


def ensure_claw_dir():
    CLAW_DIR.mkdir(parents=True, exist_ok=True)


def load_json_index() -> dict:
    if JSON_INDEX.exists():
        return json.loads(JSON_INDEX.read_text(encoding="utf-8"))
    return {"version": "1.0", "articles": [], "stats": {"total": 0, "summarized": 0, "pending": 0}}


def save_json_index(data: dict):
    ensure_claw_dir()
    total = len(data["articles"])
    summarized = sum(1 for a in data["articles"] if a.get("status") == "summarized")
    data["stats"] = {"total": total, "summarized": summarized, "pending": total - summarized}
    data["updated"] = datetime.now().isoformat()
    JSON_INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_json_index(title: str, filename: str, url: str, tags: list, status: str):
    data = load_json_index()
    today = datetime.now().strftime("%Y-%m-%d")
    for article in data["articles"]:
        if article["url"] == url:
            article.update({"title": title, "tags": tags, "status": status, "url": url, "date": today, "filename": filename})
            save_json_index(data)
            return
    data["articles"].append({"date": today, "title": title, "filename": filename, "tags": tags, "status": status, "url": url})
    save_json_index(data)


def update_md_index(title: str, filename: str, url: str, tags: list, status: str):
    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    tag_str = ", ".join(tags) if tags else "未分类"
    status_icon = "✅ 已总结" if status == "summarized" else "📝 待总结"
    title_short = title[:30]
    url_short = url[:30] + "..." if len(url) > 30 else url
    new_line = f"| {today} | [{title_short}]({filename}) | {tag_str} | {status_icon} | [{url_short}]({url}) |"

    lines = INDEX_MD.read_text(encoding="utf-8").split("\n") if INDEX_MD.exists() else [
        "# AI学习 文章索引", "",
        "| 日期 | 标题 | 标签 | 状态 | 原文 |",
        "|------|------|------|------|------|",
    ]

    for i, line in enumerate(lines):
        if url in line:
            lines[i] = new_line
            INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return

    insert_idx = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("| --") or line.startswith("|---"):
            insert_idx = i + 1
            break
    lines.insert(insert_idx, new_line)
    INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_index(title: str, filename: str, url: str, tags: list, status: str):
    update_json_index(title, filename, url, tags, status)
    update_md_index(title, filename, url, tags, status)
    print("✅ 已更新索引")


def get_claw_script() -> Path:
    local = SCRIPT_DIR / "claw_doc_browser.py"
    if local.exists():
        return local
    for p in [
        WORKSPACE / ".claude" / "dd-playwright-claw" / "scripts" / "claw_doc_browser.py",
        WORKSPACE / ".claude" / "skills" / "dd-playwright-claw" / "scripts" / "claw_doc_browser.py",
    ]:
        if p.exists():
            return p
    return None


def find_existing_by_url(url: str) -> Path:
    if not AI_LEARN_DIR.exists():
        return None
    for f in AI_LEARN_DIR.glob("*.md"):
        if f.name == "INDEX.md":
            continue
        if url in f.read_text(encoding="utf-8"):
            return f
    return None


def find_latest_raw_dir() -> Path:
    """Playwright 抓取成功后，找它刚创建的目录。不是 fallback，是正常流程。"""
    if not RAW_DIR.exists():
        return None
    dirs = [d for d in RAW_DIR.iterdir() if d.is_dir()]
    if not dirs:
        return None
    dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return dirs[0]


def save_article(url: str, title: str = None, tags: str = None, note: str = None):
    """Playwright 抓取文章。能抓到就存，抓不到就失败。无 fallback。URL 已存在时默认覆盖。"""
    existing = find_existing_by_url(url)
    if existing:
        print(f"文章已存在，将覆盖: {existing}")
        existing.unlink()
    claw_script = get_claw_script()
    if not claw_script:
        print("❌ 失败：未找到 Playwright 脚本")
        print("原因：本地没有 Playwright，无法抓取")
        print("解决：pip3 install playwright && playwright install chromium")
        return

    print(f"正在抓取: {url}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(claw_script), "--url", url, "--no-ensure-login",
         "--outdir", str(RAW_DIR)],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )

    if result.returncode == 2:
        print("❌ 失败：Playwright 未安装")
        print("解决：pip3 install playwright && playwright install chromium")
    elif result.returncode == 3:
        print("❌ 失败：遇到登录页，需要登录")
    elif result.returncode == 4:
        print("❌ 失败：正文内容为空")
    elif result.returncode != 0:
        print(f"❌ 失败：抓取异常 (exit {result.returncode})")
        if result.stderr:
            print(result.stderr)
    else:
        # 抓取成功，从 raw 目录读取结果
        raw_dir = find_latest_raw_dir()
        if not raw_dir:
            print("❌ 失败：Playwright 返回成功，但未找到输出目录")
            return
        content_file = raw_dir / "content.raw.txt"
        if not content_file.exists():
            print(f"❌ 失败：输出目录缺少 content.raw.txt")
            return

        content = content_file.read_text(encoding="utf-8")
        article_title = title or raw_dir.name
        article_title = re.sub(r'[\\/:*?"<>|\t\n\r]+', "-", article_title).strip("-").strip()
        if not article_title or article_title == "untitled":
            article_title = "未命名文章"

        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = article_title[:40].strip("-")
        filename = f"{date_str}-{safe_title}.md"
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        md_content = f"""# {article_title}

> **URL**: {url}
> **抓取时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}
> **标签**: {", ".join(tag_list) if tag_list else "未分类"}
> **状态**: 📝 待总结

## 备注
{note or "无"}

---

## 原文内容

{content[:8000]}

"""
        if len(content) > 8000:
            md_content += f"\n_（原文过长，仅显示前8000字。完整内容见 .claw/raw/{raw_dir.name}/content.raw.txt）_\n"

        AI_LEARN_DIR.mkdir(exist_ok=True)
        output_path = AI_LEARN_DIR / filename
        output_path.write_text(md_content, encoding="utf-8")
        print(f"✅ 已保存: {output_path}")
        update_index(article_title, output_path.name, url, tag_list, status="pending")


def list_pending():
    data = load_json_index()
    pending = [a for a in data["articles"] if a.get("status") != "summarized"]
    if not pending:
        print("没有待总结的文章")
        return
    print(f"=== 待总结文章 ({len(pending)}篇) ===\n")
    for article in pending:
        print(f"- {article['title']} ({article['filename']})")


def mark_summarized(filename: str):
    file_path = AI_LEARN_DIR / filename
    if not file_path.exists():
        print(f"文件不存在: {file_path}")
        return
    content = file_path.read_text(encoding="utf-8")
    if "📝 待总结" in content:
        file_path.write_text(content.replace("📝 待总结", "✅ 已总结"), encoding="utf-8")
        print(f"✅ 已标记: {filename}")
    else:
        print(f"文件状态不是待总结: {filename}")

    data = load_json_index()
    url = None
    for article in data["articles"]:
        if article["filename"] == filename:
            article["status"] = "summarized"
            url = article.get("url")
            break
    save_json_index(data)

    if INDEX_MD.exists() and url:
        lines = INDEX_MD.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            if url in line and "📝 待总结" in line:
                lines[i] = line.replace("📝 待总结", "✅ 已总结")
                break
        INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def show_index():
    data = load_json_index()
    stats = data.get("stats", {})
    print("=== AI学习 索引统计 ===")
    print(f"总计: {stats.get('total', 0)} 篇")
    print(f"已总结: {stats.get('summarized', 0)} 篇")
    print(f"待总结: {stats.get('pending', 0)} 篇")


def main():
    parser = argparse.ArgumentParser(description="文章抓取、总结与归档")
    subparsers = parser.add_subparsers(dest="command")

    save_parser = subparsers.add_parser("save", help="从 URL 抓取文章")
    save_parser.add_argument("url", help="文章URL")
    save_parser.add_argument("--title", "-t", help="自定义标题")
    save_parser.add_argument("--tags", help="标签（逗号分隔）")
    save_parser.add_argument("--note", "-n", help="备注")

    subparsers.add_parser("list-pending", help="列出待总结文章")
    subparsers.add_parser("index", help="显示索引统计")

    mark_parser = subparsers.add_parser("mark-summarized", help="标记文章为已总结")
    mark_parser.add_argument("filename", help="文件名")

    args = parser.parse_args()

    if args.command == "save":
        save_article(args.url, args.title, args.tags, args.note)
    elif args.command == "list-pending":
        list_pending()
    elif args.command == "mark-summarized":
        mark_summarized(args.filename)
    elif args.command == "index":
        show_index()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
