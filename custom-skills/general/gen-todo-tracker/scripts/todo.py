#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""TODO 管理 — git 仓库驱动，多设备同步。

用法:
  uv run custom-skills/general/todo/scripts/todo.py init
  uv run custom-skills/general/todo/scripts/todo.py add "任务内容"
  uv run custom-skills/general/todo/scripts/todo.py add "任务内容" --priority high
  uv run custom-skills/general/todo/scripts/todo.py done "关键词"
  uv run custom-skills/general/todo/scripts/todo.py done --id abc1234
  uv run custom-skills/general/todo/scripts/todo.py migrate
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
from dotenv import load as _load_dotenv
_load_dotenv()
from git import is_repo, same_remote, clone, pull, sync as _git_sync

REPO_URL = os.environ.get("TODO_REPO_URL", "git@github.com:shunchengGit/todo.git")
TODO_DIR = Path.home() / ".todo"
TODO_MD = "TODO.md"

SECTION_KEYS = {
    "高优": "high",
    "重要不紧急": "important_not_urgent",
    "暂缓": "deferred",
    "已完成": "done",
}

PRIORITY_TO_SECTION = {
    "high": "高优",
    "medium": "重要不紧急",
    "low": "暂缓",
}

PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "⚪"}

EMOJI_TO_PRIORITY = {"🔴": "high", "🟡": "medium", "⚪": "low"}


# ─── 任务 ID ──────────────────────────────────────────────


def _task_id(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:7]


# ─── 解析 ─────────────────────────────────────────────────

# 行格式: - 🔴 任务内容 <!-- id:abc1234 -->
# 旧格式兼容: - [ ] 🔴 任务内容 <!-- id:abc1234 -->
TASK_LINE_RE = re.compile(
    r"^-\s*(?:\[[ x]\]\s*)?"   # optional [ ] or [x]
    r"(.*?)"                    # content with emoji
    r"(?:\s*<!--\s*id:(\w+)\s*-->)?\s*$"
)


def _parse_task_line(line: str) -> dict | None:
    """解析任务行，提取 id、priority、content。"""
    m = TASK_LINE_RE.match(line)
    if not m:
        return None
    raw_content = m.group(1)
    tid = m.group(2) or _task_id(raw_content)
    priority = "medium"
    content = raw_content
    for emoji, pri in EMOJI_TO_PRIORITY.items():
        if content.startswith(emoji):
            priority = pri
            content = content[len(emoji):].strip()
            break
    return {"priority": priority, "content": content, "id": tid}


def _format_task_line(content: str, priority: str, tid: str | None = None) -> str:
    """格式化任务行：- 🔴 任务内容 <!-- id:abc1234 -->"""
    emoji = PRIORITY_EMOJI.get(priority, "🟡")
    if tid is None:
        tid = _task_id(content)
    return f"- {emoji} {content} <!-- id:{tid} -->"


def _parse_section_lines(filepath: Path, section: str) -> list[dict]:
    """提取指定 section 下的任务行。"""
    if not filepath.exists():
        return []
    content = filepath.read_text(encoding="utf-8")
    pattern = rf"^#+\s+{section}\s*\n(.*?)(?=^#+\s|\Z)"
    m = re.search(pattern, content, re.DOTALL | re.MULTILINE)
    if not m:
        return []
    items = []
    for line in m.group(1).strip().splitlines():
        line = line.strip()
        if not line or line.startswith("<!--"):
            continue
        parsed = _parse_task_line(line)
        if parsed:
            items.append(parsed)
    return items


def _list_todo_md() -> dict[str, list[dict]]:
    """解析 TODO.md 所有 section。"""
    filepath = TODO_DIR / TODO_MD
    if not filepath.exists():
        return {}
    sections: dict[str, list[dict]] = {}
    for zh_name, key in SECTION_KEYS.items():
        sections[key] = _parse_section_lines(filepath, zh_name)
    return sections


# ─── TODO.md 写入 ─────────────────────────────────────────


def _ensure_section(content: str, section_zh: str) -> str:
    """确保 content 中存在指定 ## section，不存在则追加。"""
    if re.search(rf"^#+\s+{section_zh}\s*$", content, re.MULTILINE):
        return content
    return content.rstrip() + f"\n\n# {section_zh}\n"


def _add_to_todo_md(task: str, priority: str) -> None:
    """将任务追加到 TODO.md 对应 section。"""
    filepath = TODO_DIR / TODO_MD
    content = filepath.read_text(encoding="utf-8") if filepath.exists() else ""

    section_zh = PRIORITY_TO_SECTION.get(priority, "重要不紧急")
    tid = _task_id(task)
    task_line = _format_task_line(task, priority, tid)

    content = _ensure_section(content, section_zh)

    pattern = rf"(^#+\s+{section_zh}\s*\n)"
    m = re.search(pattern, content, re.MULTILINE)
    if m:
        insert_pos = m.end()
        # 跳过 section 头后的注释行
        rest = content[insert_pos:]
        comment_lines = re.match(r"((?:<!--.*?-->\s*\n)*)", rest)
        skip = comment_lines.end() if comment_lines else 0
        content = content[:insert_pos + skip] + task_line + "\n" + content[insert_pos + skip:]
    else:
        content = content.rstrip() + "\n" + task_line + "\n"

    filepath.write_text(content, encoding="utf-8")


def _find_and_move_to_done(keyword: str | None, task_id: str | None) -> tuple[int, list[str]]:
    """在 TODO.md 中查找任务并移到已完成 section。

    返回 (matched_count, [matched_content_list])
    """
    filepath = TODO_DIR / TODO_MD
    if not filepath.exists():
        return 0, []

    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    # 收集所有非已完成 section 的任务行及其索引
    current_section = None
    candidates: list[tuple[int, str, dict]] = []

    for i, line in enumerate(lines):
        sec_m = re.match(r"^#+\s+(.+)$", line)
        if sec_m:
            current_section = sec_m.group(1).strip()
            continue
        if current_section == "已完成":
            continue
        parsed = _parse_task_line(line)
        if parsed:
            candidates.append((i, line, parsed))

    # 匹配
    matched_indices = []
    matched_contents = []

    if task_id:
        for idx, line, parsed in candidates:
            if parsed["id"] == task_id:
                matched_indices.append(idx)
                matched_contents.append(parsed["content"])
    elif keyword:
        for idx, line, parsed in candidates:
            if keyword in parsed["content"]:
                matched_indices.append(idx)
                matched_contents.append(parsed["content"])

    if not matched_indices:
        return 0, []

    # 从后往前删除匹配行
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    done_lines = []
    for idx in sorted(matched_indices, reverse=True):
        parsed = _parse_task_line(lines[idx])
        done_line = _format_task_line(parsed["content"], parsed["priority"], parsed["id"])
        done_lines.append(done_line)
        del lines[idx]

    # 确保 # 已完成 section 存在并追加
    content = "\n".join(lines)
    content = _ensure_section(content, "已完成")

    pattern = r"(^#+\s+已完成\s*\n)"
    m = re.search(pattern, content, re.MULTILINE)
    if m:
        insert_pos = m.end()
        for dl in reversed(done_lines):
            content = content[:insert_pos] + dl + "\n" + content[insert_pos:]

    filepath.write_text(content, encoding="utf-8")
    return len(matched_indices), matched_contents


# ─── init ─────────────────────────────────────────────────


def _init_repo() -> dict:
    if not TODO_DIR.exists():
        return clone(REPO_URL, TODO_DIR)

    if not is_repo(TODO_DIR):
        return {
            "success": False, "action": "none",
            "error": f"{TODO_DIR} 已存在但不是 git 仓库，请手动处理",
            "hint": f"备份后删除 {TODO_DIR}，或将其初始化为 git 仓库",
        }

    if not same_remote(TODO_DIR, REPO_URL):
        return {
            "success": False, "action": "none",
            "error": f"{TODO_DIR} 的 remote origin 不是 {REPO_URL}",
            "hint": "请手动调整 git remote 或备份后重新 init",
        }

    return pull(TODO_DIR)


def cmd_init() -> dict:
    result = _init_repo()
    if not result["success"]:
        return result
    _tidy_todo_md()
    tasks = _list_todo_md()
    return {**result, "tasks": tasks}


# ─── add ──────────────────────────────────────────────────


def cmd_add(task: str, priority: str = "medium") -> dict:
    if not TODO_DIR.exists():
        return {"success": False, "error": f"{TODO_DIR} 不存在，请先运行 init"}

    # 去重
    filepath = TODO_DIR / TODO_MD
    if filepath.exists():
        existing = _list_todo_md()
        for section_tasks in existing.values():
            for t in section_tasks:
                if t["content"] == task and section_tasks is not existing.get("done"):
                    return {"success": True, "task": task, "priority": priority, "id": t["id"], "duplicate": True}

    tid = _task_id(task)
    _add_to_todo_md(task, priority)
    result = _git_sync(TODO_DIR, f"add: {task}", files=TODO_MD)
    if not result["success"]:
        return result

    return {"success": True, "task": task, "priority": priority, "id": tid, **result}


# ─── done ─────────────────────────────────────────────────


def cmd_done(keyword: str | None, task_id: str | None = None) -> dict:
    if not TODO_DIR.exists():
        return {"success": False, "error": f"{TODO_DIR} 不存在，请先运行 init"}

    if not keyword and not task_id:
        return {"success": False, "error": "请提供关键词或 --id"}

    filepath = TODO_DIR / TODO_MD
    if not filepath.exists():
        return {"success": False, "error": "TODO.md 不存在"}

    # 预扫描匹配数量
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    current_section = None
    candidates = []
    for line in lines:
        sec_m = re.match(r"^#+\s+(.+)$", line)
        if sec_m:
            current_section = sec_m.group(1).strip()
            continue
        if current_section == "已完成":
            continue
        parsed = _parse_task_line(line)
        if parsed:
            if task_id and parsed["id"] == task_id:
                candidates.append(parsed)
            elif keyword and not task_id and keyword in parsed["content"]:
                candidates.append(parsed)

    if not candidates:
        return {"success": True, "matched": 0, "hint": "未找到匹配的未完成任务"}

    if len(candidates) > 1 and not task_id:
        return {
            "success": False,
            "error": f"匹配到 {len(candidates)} 个任务，请用 --id 精确指定",
            "candidates": [{"id": c["id"], "content": c["content"]} for c in candidates],
        }

    _find_and_move_to_done(keyword, task_id)
    result = _git_sync(TODO_DIR, f"done: {keyword or task_id}", files=TODO_MD)
    if not result["success"]:
        return result

    matched_contents = [c["content"] for c in candidates]
    return {"success": True, "matched": len(candidates), "completed": matched_contents, **{k: v for k, v in result.items() if k != "matched_contents"}}


# ─── tidy ─────────────────────────────────────────────────


def _tidy_todo_md() -> None:
    """整理 TODO.md：统一行格式（去掉 [x]/[ ]），为所有行添加 ID。"""
    filepath = TODO_DIR / TODO_MD
    if not filepath.exists():
        return
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    changed = False

    current_section = None
    done_indices = []

    for i, line in enumerate(lines):
        sec_m = re.match(r"^#+\s+(.+)$", line)
        if sec_m:
            current_section = sec_m.group(1).strip()
            continue

        parsed = _parse_task_line(line)
        if not parsed:
            continue

        # 非已完成 section 中有 [x] 行 → 标记待移除
        if current_section and current_section != "已完成" and "[x]" in line:
            done_indices.append((i, parsed))
            changed = True
            continue

        # 统一格式：去掉 [ ]/[x]，确保有 ID
        normalized = _format_task_line(parsed["content"], parsed["priority"], parsed["id"])
        if line.strip() != normalized:
            lines[i] = normalized
            changed = True

    # 移除非已完成 section 中的 [x] 行到已完成
    if done_indices:
        for idx, _ in sorted(done_indices, reverse=True):
            del lines[idx]

        content = "\n".join(lines)
        content = _ensure_section(content, "已完成")
        pattern = r"(^#+\s+已完成\s*\n)"
        m = re.search(pattern, content, re.MULTILINE)
        if m:
            insert_pos = m.end()
            for _, parsed in reversed(done_indices):
                dl = _format_task_line(parsed["content"], parsed["priority"], parsed["id"])
                content = content[:insert_pos] + dl + "\n" + content[insert_pos:]
        lines = content.split("\n")

    if changed:
        filepath.write_text("\n".join(lines), encoding="utf-8")


# ─── migrate ──────────────────────────────────────────────


def cmd_migrate() -> dict:
    """合并每日日志任务到 TODO.md，并为所有任务添加 ID。"""
    if not TODO_DIR.exists():
        return {"success": False, "error": f"{TODO_DIR} 不存在，请先运行 init"}

    result = pull(TODO_DIR)
    if not result["success"]:
        return {"success": False, "error": "git pull 失败", "detail": result.get("error", "")[:300]}

    # 整理现有 TODO.md
    _tidy_todo_md()

    # 扫描每日日志文件
    daily_files = sorted(TODO_DIR.glob("????-??-??.md"))
    merged_count = 0
    skipped_count = 0

    existing = _list_todo_md()
    existing_contents = set()
    for section_tasks in existing.values():
        for t in section_tasks:
            existing_contents.add(t["content"])

    for daily_file in daily_files:
        tasks = []
        for line in daily_file.read_text(encoding="utf-8").splitlines():
            parsed = _parse_task_line(line)
            if parsed:
                tasks.append(parsed)

        for t in tasks:
            if t["content"] in existing_contents:
                skipped_count += 1
                continue
            # 已完成的直接追加到已完成 section，未完成的追加到对应 section
            if t.get("status") == "done":
                _add_to_done_section(t["content"], t["priority"])
            else:
                _add_to_todo_md(t["content"], t["priority"])
            existing_contents.add(t["content"])
            merged_count += 1

    # 再次整理
    _tidy_todo_md()

    # 提交
    git_result = _git_sync(TODO_DIR, "migrate: 合并每日日志到 TODO.md + 添加任务 ID", files=TODO_MD)

    return {
        "success": True,
        "merged": merged_count,
        "skipped_duplicates": skipped_count,
        "daily_files_scanned": len(daily_files),
        **git_result,
    }


def _add_to_done_section(content: str, priority: str) -> None:
    """将已完成任务追加到 TODO.md 的 # 已完成 section。"""
    filepath = TODO_DIR / TODO_MD
    text = filepath.read_text(encoding="utf-8") if filepath.exists() else ""
    text = _ensure_section(text, "已完成")
    tid = _task_id(content)
    task_line = _format_task_line(content, priority, tid)

    pattern = r"(^#+\s+已完成\s*\n)"
    m = re.search(pattern, text, re.MULTILINE)
    if m:
        insert_pos = m.end()
        text = text[:insert_pos] + task_line + "\n" + text[insert_pos:]
    else:
        text = text.rstrip() + "\n" + task_line + "\n"

    filepath.write_text(text, encoding="utf-8")


# ─── main ─────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="TODO 管理 (git 同步)")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="克隆/拉取仓库 + 输出 TODO.md 全量任务 JSON")

    add_parser = subparsers.add_parser("add", help="添加任务")
    add_parser.add_argument("task", help="任务内容")
    add_parser.add_argument("--priority", choices=["high", "medium", "low"], default="medium")

    done_parser = subparsers.add_parser("done", help="完成任务")
    done_parser.add_argument("keyword", nargs="?", help="任务关键词")
    done_parser.add_argument("--id", dest="task_id", help="任务 ID（精确匹配）")

    subparsers.add_parser("migrate", help="合并每日日志到 TODO.md + 添加任务 ID")

    args = parser.parse_args()

    if args.command == "init":
        result = cmd_init()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result.get("success"):
            sys.exit(1)
    elif args.command == "add":
        result = cmd_add(args.task, args.priority)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "done":
        result = cmd_done(args.keyword, args.task_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "migrate":
        result = cmd_migrate()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
