#!/usr/bin/env python3
"""文档生成脚本"""

import argparse
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path(os.environ.get("ASSIST_HOME", "/Users/chengshun/Assist"))
TODO_DIR = WORKSPACE / "TODO"
TEAM_DIR = WORKSPACE / "团队"
AI_LEARN_DIR = WORKSPACE / "AI学习"
AI_INDEX = AI_LEARN_DIR / "INDEX.md"
RESUME_DIR = WORKSPACE / "面试" / "resume"


def _collect_completed(todo_files: list) -> list:
    """从多个 TODO 文件中收集已完成项（- [x] 格式）"""
    completed = []
    for f in todo_files:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").split("\n"):
            if line.startswith("- [x]"):
                completed.append(line.strip())
    return completed


def _collect_pending(todo_files: list) -> list:
    """从多个 TODO 文件中收集未完成项（- [ ] 格式）"""
    pending = []
    for f in todo_files:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").split("\n"):
            if line.startswith("- [ ]"):
                pending.append(line.strip())
    return pending


def _collect_schedule_items(todo_file: Path) -> list:
    """从每日文件的表格中提取日程项（| 时间 | 事项 | 格式）"""
    items = []
    if not todo_file.exists():
        return items
    for line in todo_file.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        # 匹配表格行：| col1 | col2 |
        if line.startswith("|") and line.endswith("|") and not line.startswith("|---"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 2:
                # 第一列为时间，其余为事项
                task = " — ".join(c for c in cells if c)
                if task and "时间" not in task and "事项" not in task:
                    items.append(task)
    return items


def daily_report(date_str: str = None):
    """生成日报"""
    if date_str:
        target = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        target = datetime.now()

    today_file = TODO_DIR / f"{target.strftime('%Y-%m-%d')}.md"
    main_file = TODO_DIR / "TODO.md"

    schedule = _collect_schedule_items(today_file)
    todos = _collect_pending([today_file, main_file])
    done = _collect_completed([today_file])

    # 周四标记
    weekday = target.weekday()
    is_thursday = weekday == 3

    print(f"=== 日报 ({target.strftime('%m/%d')}) ===\n")

    print("## 每日必排")
    print("- 13:30-14:00 — 招聘简历获取")
    print("- 14:00-14:30 — 产品体验和竞品体验")
    print("- 14:30-15:00 — AI 研究学习")
    if is_thursday:
        print("- 17:00-18:00 — 客户端周会")
    print()

    print("## 今日日程")
    if schedule:
        for item in schedule:
            print(f"- {item}")
    else:
        print("- 暂无")
    print()

    print("## 待办")
    if todos:
        for item in todos[:15]:
            print(f"- {item.replace('- [ ]', '').strip()}")
    else:
        print("- 暂无")
    print()

    print("## 已完成")
    if done:
        for item in done:
            print(f"- {item.replace('- [x]', '').strip()}")
    else:
        print("- 暂无")


def weekly_report(date_str: str = None):
    """生成周报草稿"""
    if date_str:
        end_date = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        end_date = datetime.now()

    start_date = end_date - timedelta(days=7)

    # 收集本周每日文件 + 主 TODO.md
    todo_files = [TODO_DIR / "TODO.md"]
    for i in range(7):
        day = end_date - timedelta(days=i)
        todo_files.append(TODO_DIR / f"{day.strftime('%Y-%m-%d')}.md")

    completed = _collect_completed(todo_files)

    print(f"=== 周报草稿 ({start_date.strftime('%m/%d')}-{end_date.strftime('%m/%d')}) ===\n")

    print("## 本周完成")
    if completed:
        for item in completed[:10]:
            print(f"- {item.replace('- [x]', '').strip()}")
    else:
        print("- 暂无记录")

    print("\n## 招聘进展")
    if RESUME_DIR.exists():
        questions = sorted(RESUME_DIR.glob("面试题_*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
        if questions:
            for f in questions[:5]:
                content = f.read_text(encoding="utf-8")
                name = f.stem.replace("面试题_", "")
                score_match = re.search(r"总分\S*\s*(\d+)/60", content)
                rating_match = re.search(r"☑\s*([ABCD])", content)
                if score_match:
                    r = f" {rating_match.group(1)}级" if rating_match else ""
                    status = f"{score_match.group(1)}分{r}"
                else:
                    status = "待面试"
                print(f"- {name}: {status}")
        else:
            print("- 本周无面试安排")
    else:
        print("- 暂无")

    print("\n## 下周计划")
    print("- ")

    print("\n## 风险/阻塞")
    print("- ")


def cmd_digest(limit: int = 5):
    """整理待消化文章（从 AI学习/INDEX.md 读取）"""
    if not AI_INDEX.exists():
        print("暂无文章索引")
        return

    lines = AI_INDEX.read_text(encoding="utf-8").split("\n")
    articles = []
    for line in lines:
        if line.startswith("| 20") and "已总结" not in line:
            articles.append(line)

    if not articles:
        print("暂无待总结文章")
        return

    print(f"=== 待消化文章 ({min(limit, len(articles))}/{len(articles)}) ===\n")

    for line in articles[:limit]:
        parts = [c.strip() for c in line.split("|")[1:-1]]
        if len(parts) >= 4:
            date, title, tags, status = parts[0], parts[1], parts[2], parts[3]
            # title 是 markdown link 格式 [text](file)
            title_text = title.split("](")[0].strip("[") if "](" in title else title
            print(f"**{title_text}**")
            print(f"  日期: {date}  |  标签: {tags}  |  状态: {status}")
            print()


def main():
    parser = argparse.ArgumentParser(description="文档生成")
    subparsers = parser.add_subparsers(dest="command")

    daily_parser = subparsers.add_parser("daily", help="生成日报")
    daily_parser.add_argument("--date", help="日期 (YYYY-MM-DD)")

    weekly_parser = subparsers.add_parser("weekly", help="生成周报")
    weekly_parser.add_argument("--date", help="结束日期 (YYYY-MM-DD)")

    digest_parser = subparsers.add_parser("digest", help="整理收藏")
    digest_parser.add_argument("--limit", type=int, default=5, help="数量限制")

    args = parser.parse_args()

    if args.command == "daily":
        daily_report(args.date)
    elif args.command == "weekly":
        weekly_report(args.date)
    elif args.command == "digest":
        cmd_digest(args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
