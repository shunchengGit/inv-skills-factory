"""Git 操作工具 — add / commit / push / pull / clone。

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "_shared"))
  from git import run, is_repo, same_remote, clone, pull, sync
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List


def run(args: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def is_repo(path: Path) -> bool:
    return (path / ".git").exists()


def same_remote(path: Path, url: str) -> bool:
    r = run(["remote", "get-url", "origin"], cwd=path)
    return r.returncode == 0 and r.stdout.strip() == url


def clone(url: str, path: Path, branch: str = "master") -> dict:
    """克隆仓库，返回 {success, action, error?, hint?}。"""
    r = run(["clone", "-b", branch, url, str(path)])
    if r.returncode == 0:
        return {"success": True, "action": "clone"}

    err = r.stderr.strip()
    if "Could not read from remote" in err or "Permission denied" in err:
        hint = "请检查 SSH key 配置：ssh -T git@github.com"
    elif "Repository not found" in err or "not found" in err.lower():
        hint = f"远程仓库不存在，请确认 {url} 是否已创建"
    else:
        hint = "网络连接失败，请检查网络或代理设置"
    return {"success": False, "action": "clone", "error": err[:500], "hint": hint}


def pull(path: Path, branch: str = "master") -> dict:
    """拉取仓库，返回 {success, action, error?, files_changed?}。"""
    r = run(["pull", "origin", branch], cwd=path)
    if r.returncode == 0:
        return {"success": True, "action": "pull", "files_changed": r.stdout.strip() or ""}
    return {
        "success": False, "action": "pull",
        "error": r.stderr.strip()[:500],
        "hint": "git pull 失败，可能需要手动解决冲突",
    }


def sync(cwd: Path, commit_msg: str, files: str = "-A", branch: str = "master",
         max_retries: int = 2) -> dict:
    """pull --rebase → add → commit → push（push 失败自动重试）。

    返回 {success, push_failed?, error?, no_change?}。
    """
    r_pull = run(["pull", "--rebase", "origin", branch], cwd=cwd)
    if r_pull.returncode != 0:
        if "conflict" in (r_pull.stderr + r_pull.stdout).lower():
            run(["rebase", "--abort"], cwd=cwd)
            return {"success": False, "step": "pull", "error": "合并冲突，请手动解决后重试"}
        # non-conflict pull failure (no remote, network) — 继续尝试

    r_add = run(["add", files], cwd=cwd)
    if r_add.returncode != 0:
        return {"success": False, "step": "add", "error": r_add.stderr.strip()[:300]}

    r_commit = run(["commit", "-m", commit_msg], cwd=cwd)
    if r_commit.returncode != 0:
        if "nothing to commit" in r_commit.stdout:
            return {"success": True, "push_failed": False, "no_change": True}
        return {"success": False, "step": "commit", "error": r_commit.stderr.strip()[:300]}

    for attempt in range(max_retries + 1):
        r_push = run(["push", "origin", branch], cwd=cwd, timeout=30)
        if r_push.returncode == 0:
            return {"success": True, "push_failed": False}
        if attempt < max_retries:
            # re-pull before retry
            r_retry_pull = run(["pull", "--rebase", "origin", branch], cwd=cwd)
            if r_retry_pull.returncode != 0 and "conflict" in (r_retry_pull.stderr + r_retry_pull.stdout).lower():
                run(["rebase", "--abort"], cwd=cwd)
                return {"success": False, "step": "pull", "error": "合并冲突，请手动解决后重试"}

    return {
        "success": True,
        "push_failed": True,
        "hint": f"push 失败，本地已保存。稍后手动: git -C {cwd} push",
        "push_error": r_push.stderr.strip()[:300],
    }
