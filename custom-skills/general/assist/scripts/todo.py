#!/usr/bin/env python3
"""TODO 管理脚本"""

import argparse
import os
import re
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(os.environ.get("ASSIST_HOME", "/Users/chengshun/Assist"))
TODO_DIR = WORKSPACE / "TODO"


def get_today_file() -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    return TODO_DIR / f"{today}.md"


def get_main_todo() -> Path:
    return TODO_DIR / "TODO.md"


def read_todo(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_todo(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


def today_cmd():
    """显示今日待办"""
    path = get_today_file()
    if not path.exists():
        print(f"今日暂无待办: {path.name}")
        return

    content = read_todo(path)
    print(f"=== {path.stem} ===")
    print(content or "（空）")

    # 也显示高优任务
    main = get_main_todo()
    if main.exists():
        content = read_todo(main)
        high_priority = extract_section(content, "高优")
        if high_priority:
            print("\n=== 高优任务 ===")
            print(high_priority)


def extract_section(content: str, section: str) -> str:
    """提取 markdown 章节"""
    pattern = rf"#+\s*{section}.*?(?=\n#+\s|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    return match.group(0).strip() if match else ""


def add_cmd(task: str, priority: str = "medium"):
    """添加任务到今日待办"""
    path = get_today_file()
    content = read_todo(path)

    prefix = "🔴" if priority == "high" else "🟡" if priority == "medium" else "⚪"
    task_line = f"- [ ] {prefix} {task}\n"

    if content:
        content = content.rstrip() + "\n" + task_line
    else:
        content = f"# {path.stem}\n\n{task_line}"

    write_todo(path, content)
    print(f"已添加: {task}")


def _mark_done_in_file(filepath: Path, keyword: str) -> int:
    """在单个文件中标记完成，返回匹配数"""
    if not filepath.exists():
        return 0
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    found = 0
    for i, line in enumerate(lines):
        if keyword in line and line.startswith("- [ ]"):
            lines[i] = line.replace("- [ ]", "- [x]")
            found += 1
            print(f"已完成: {line.strip()}  ({filepath.name})")
    if found:
        filepath.write_text("\n".join(lines), encoding="utf-8")
    return found


def done_cmd(keyword: str):
    """标记任务完成（搜索每日文件 + 主 TODO）"""
    files = [get_today_file(), get_main_todo()]
    total = sum(_mark_done_in_file(f, keyword) for f in files)
    if total == 0:
        print(f"未找到包含 '{keyword}' 的未完成任务")


def archive_cmd():
    """归档已完成任务：收集 - [x] 行写入 ARCHIVE.md，然后从源文件移除"""
    archive_file = TODO_DIR / "ARCHIVE.md"
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    archived_items = []

    for f in sorted(TODO_DIR.glob("*.md")):
        if f.name == "ARCHIVE.md":
            continue
        content = f.read_text(encoding="utf-8")
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if line.startswith("- [x]"):
                archived_items.append((f.name, line.strip()))
            else:
                new_lines.append(line)
        if len(new_lines) != len(lines):
            f.write_text("\n".join(new_lines), encoding="utf-8")

    if not archived_items:
        print("无待归档任务")
        return

    # 追加到归档文件
    entry = f"\n## {today_str}\n" + "\n".join(
        f"- {item}  ← {src}" for src, item in archived_items
    ) + "\n"

    existing = archive_file.read_text(encoding="utf-8") if archive_file.exists() else "# 归档记录\n"
    archive_file.write_text(existing.rstrip() + entry, encoding="utf-8")

    print(f"已归档 {len(archived_items)} 项 → {archive_file}")


def main():
    parser = argparse.ArgumentParser(description="TODO 管理")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("today", help="显示今日待办")

    add_parser = subparsers.add_parser("add", help="添加任务")
    add_parser.add_argument("task", help="任务内容")
    add_parser.add_argument("--priority", choices=["high", "medium", "low"], default="medium")

    done_parser = subparsers.add_parser("done", help="完成任务")
    done_parser.add_argument("keyword", help="任务关键词")

    subparsers.add_parser("archive", help="归档已完成")

    args = parser.parse_args()

    if args.command == "today":
        today_cmd()
    elif args.command == "add":
        add_cmd(args.task, args.priority)
    elif args.command == "done":
        done_cmd(args.keyword)
    elif args.command == "archive":
        archive_cmd()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
