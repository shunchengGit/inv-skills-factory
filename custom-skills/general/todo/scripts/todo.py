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
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_URL = "git@github.com:shunchengGit/todo.git"
TODO_DIR = Path.home() / ".todo"
TODO_MD = "TODO.md"
SECTION_KEYS = {
    "高优": "high",
    "重要不紧急": "important_not_urgent",
    "暂缓": "deferred",
    "已完成": "done",
}


# ─── git 工具 ─────────────────────────────────────────────


def _run_git(args: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd or TODO_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _same_remote(path: Path) -> bool:
    r = _run_git(["remote", "get-url", "origin"], cwd=path)
    if r.returncode != 0:
        return False
    return r.stdout.strip() == REPO_URL


def _git_sync(commit_msg: str) -> dict:
    r_add = _run_git(["add", "-A"])
    if r_add.returncode != 0:
        return {"success": False, "step": "add", "error": r_add.stderr.strip()[:300]}

    r_commit = _run_git(["commit", "-m", commit_msg])
    if r_commit.returncode != 0 and "nothing to commit" not in r_commit.stdout:
        return {"success": False, "step": "commit", "error": r_commit.stderr.strip()[:300]}

    r_push = _run_git(["push"], timeout=30)
    if r_push.returncode != 0:
        return {
            "success": True,
            "push_failed": True,
            "hint": "push 失败，本地已保存。请稍后手动执行: git -C ~/.todo pull && git -C ~/.todo push",
            "push_error": r_push.stderr.strip()[:300],
        }

    return {"success": True, "push_failed": False}


# ─── TODO.md 解析 ─────────────────────────────────────────


def _today_filename() -> str:
    return datetime.now().strftime("%Y-%m-%d") + ".md"


def _parse_tasks(filepath: Path) -> list[dict]:
    if not filepath.exists():
        return []
    tasks = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^-\s*\[([ x])\]\s*(.*)", line)
        if not m:
            continue
        status = "done" if m.group(1) == "x" else "pending"
        content = m.group(2)
        priority = "medium"
        for emoji, pri in [("🔴", "high"), ("🟡", "medium"), ("⚪", "low")]:
            if content.startswith(emoji):
                priority = pri
                content = content[len(emoji):].strip()
                break
        tasks.append({"status": status, "priority": priority, "content": content})
    return tasks


def _parse_section_lines(filepath: Path, section: str) -> list[dict]:
    """提取指定 section 下的行（checkbox 或纯文本）。"""
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
        m2 = re.match(r"^-\s*\[([ x])\]\s*(.*)", line)
        if m2:
            status = "done" if m2.group(1) == "x" else "pending"
            content = m2.group(2)
            priority = "medium"
            for emoji, pri in [("🔴", "high"), ("🟡", "medium"), ("⚪", "low")]:
                if content.startswith(emoji):
                    priority = pri
                    content = content[len(emoji):].strip()
                    break
            items.append({"status": status, "priority": priority, "content": content})
        else:
            items.append({"content": line})
    return items


# ─── init ─────────────────────────────────────────────────


def _init_repo() -> dict:
    if not TODO_DIR.exists():
        r = _run_git(["clone", REPO_URL, str(TODO_DIR)], cwd=Path.home())
        if r.returncode != 0:
            err = r.stderr.strip()
            if "Could not read from remote" in err or "Permission denied" in err:
                hint = "请检查 SSH key 配置：ssh -T git@github.com"
            elif "Repository not found" in err or "not found" in err.lower():
                hint = f"远程仓库不存在，请确认 {REPO_URL} 是否已创建"
            else:
                hint = "网络连接失败，请检查网络或代理设置"
            return {"success": False, "action": "clone", "error": err[:500], "hint": hint}
        return {"success": True, "action": "clone"}

    if not _is_git_repo(TODO_DIR):
        return {
            "success": False, "action": "none",
            "error": f"{TODO_DIR} 已存在但不是 git 仓库，请手动处理",
            "hint": f"备份后删除 {TODO_DIR}，或将其初始化为 git 仓库",
        }

    if not _same_remote(TODO_DIR):
        return {
            "success": False, "action": "none",
            "error": f"{TODO_DIR} 的 remote origin 不是 {REPO_URL}",
            "hint": "请手动调整 git remote 或备份后重新 init",
        }

    r = _run_git(["pull"])
    if r.returncode != 0:
        return {
            "success": False, "action": "pull",
            "error": r.stderr.strip()[:500],
            "hint": "git pull 失败，可能需要手动解决冲突",
        }

    return {"success": True, "action": "pull"}


def _list_todo_md() -> dict[str, list[dict]]:
    """解析 ~/.todo/TODO.md 所有 ## section，返回 {key: [{status, priority, content}]}。"""
    filepath = TODO_DIR / TODO_MD
    if not filepath.exists():
        return {}
    content = filepath.read_text(encoding="utf-8")
    sections: dict[str, list[dict]] = {}
    for zh_name, key in SECTION_KEYS.items():
        items = _parse_section_lines(filepath, zh_name)
        sections[key] = items
    return sections


def cmd_init() -> dict:
    result = _init_repo()
    if not result["success"]:
        return result

    tasks = _list_todo_md()
    return {**result, "tasks": tasks}


# ─── add ──────────────────────────────────────────────────


def cmd_add(task: str, priority: str = "medium") -> dict:
    if not TODO_DIR.exists():
        return {"success": False, "error": f"{TODO_DIR} 不存在，请先运行 init"}

    r = _run_git(["pull"])
    if r.returncode != 0:
        return {"success": False, "error": "git pull 失败，请先手动处理冲突或检查网络", "detail": r.stderr.strip()[:300]}

    today_file = TODO_DIR / _today_filename()
    emoji = {"high": "🔴", "medium": "🟡", "low": "⚪"}.get(priority, "🟡")
    task_line = f"- [ ] {emoji} {task}\n"

    if today_file.exists():
        content = today_file.read_text(encoding="utf-8").rstrip() + "\n" + task_line
    else:
        content = f"# {_today_filename().replace('.md', '')}\n\n" + task_line + "\n"

    today_file.write_text(content, encoding="utf-8")

    git_result = _git_sync(f"add: {task}")
    return {"success": True, "task": task, "priority": priority, **git_result}


# ─── done ─────────────────────────────────────────────────


def _mark_done_in_file(filepath: Path, keyword: str) -> int:
    if not filepath.exists():
        return 0
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    found = 0
    for i, line in enumerate(lines):
        if keyword in line and line.startswith("- [ ]"):
            lines[i] = line.replace("- [ ]", "- [x]")
            found += 1
            print(f"已完成: {line.strip()}  ({filepath.name})", file=sys.stderr)
    if found:
        filepath.write_text("\n".join(lines), encoding="utf-8")
    return found


def cmd_done(keyword: str) -> dict:
    if not TODO_DIR.exists():
        return {"success": False, "error": f"{TODO_DIR} 不存在，请先运行 init"}

    r = _run_git(["pull"])
    if r.returncode != 0:
        return {"success": False, "error": "git pull 失败，请先手动处理冲突或检查网络", "detail": r.stderr.strip()[:300]}

    files = [TODO_DIR / _today_filename(), TODO_DIR / TODO_MD]
    total = sum(_mark_done_in_file(f, keyword) for f in files)

    if total == 0:
        print(f"未找到包含 '{keyword}' 的未完成任务", file=sys.stderr)
        return {"success": True, "matched": 0}

    git_result = _git_sync(f"done: {keyword}")
    return {"success": True, "matched": total, **git_result}


# ─── main ─────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="TODO 管理 (git 同步)")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="克隆/拉取仓库 + 输出 TODO.md 全量任务 JSON")

    add_parser = subparsers.add_parser("add", help="添加任务")
    add_parser.add_argument("task", help="任务内容")
    add_parser.add_argument("--priority", choices=["high", "medium", "low"], default="medium")

    done_parser = subparsers.add_parser("done", help="完成任务")
    done_parser.add_argument("keyword", help="任务关键词")

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
        result = cmd_done(args.keyword)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
