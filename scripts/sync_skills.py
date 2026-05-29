#!/usr/bin/env python3
"""将 SkillsStore 的 skills 和 hooks 同步到各 Agent 平台。

用法:
  python sync_skills.py                     # 同步所有
  python sync_skills.py --skills            # 只同步 skills
  python sync_skills.py --hooks             # 只同步 hooks
  python sync_skills.py --agent hermes      # 只同步到指定 agent
  python sync_skills.py --category general  # 只同步指定分类（base 始终同步）
"""

import argparse
import json
import shutil
from pathlib import Path

STORE_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = STORE_ROOT / "custom-skills"
HOOKS_SRC = STORE_ROOT / "hooks"
TARGETS_FILE = Path(__file__).resolve().parent / "agent_targets.json"
BASE = "base"


def load_targets() -> list[dict]:
    with open(TARGETS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return [a for a in data.get("agents", []) if a.get("enabled", True)]


def _remove(path: Path):
    """安全删除：符号链接用 unlink，目录用 rmtree，文件用 unlink"""
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def sync_skills(target: dict, categories: list[str] | None = None):
    """同步 skills：base 必定同步，其余按指定分类"""
    skills_dir = Path(target["skills_dir"]).expanduser()
    skills_dir.mkdir(parents=True, exist_ok=True)

    # base 必定同步
    base_src = SKILLS_SRC / BASE
    if base_src.exists():
        for item in base_src.iterdir():
            if not item.is_dir():
                continue
            dest = skills_dir / item.name
            _remove(dest)
            shutil.copytree(item, dest)

    # 指定分类同步
    categories = categories or ["general", "invest"]
    for cat in categories:
        cat_src = SKILLS_SRC / cat
        if not cat_src.exists():
            continue
        for item in cat_src.iterdir():
            if not item.is_dir() or not (item / "SKILL.md").exists():
                continue
            dest = skills_dir / item.name
            _remove(dest)
            shutil.copytree(item, dest)


def sync_hooks(target: dict):
    """同步 hooks：只同步该 agent 对应子目录下的 hooks"""
    hooks_dir = target.get("hooks_dir")
    if not hooks_dir:
        return
    agent_name = target["name"]
    agent_hooks_src = HOOKS_SRC / agent_name
    if not agent_hooks_src.exists():
        return

    dest_root = Path(hooks_dir).expanduser()
    dest_root.mkdir(parents=True, exist_ok=True)

    for hook_dir in agent_hooks_src.iterdir():
        if not hook_dir.is_dir():
            continue
        dest = dest_root / hook_dir.name
        _remove(dest)
        shutil.copytree(hook_dir, dest)


def main():
    parser = argparse.ArgumentParser(description="同步 SkillsStore 到各 Agent 平台")
    parser.add_argument("--skills", action="store_true", help="只同步 skills")
    parser.add_argument("--hooks", action="store_true", help="只同步 hooks")
    parser.add_argument("--agent", type=str, help="只同步到指定 agent")
    parser.add_argument("--category", type=str, help="只同步指定分类（base 始终同步）")
    args = parser.parse_args()

    # 默认同步 skills + hooks
    do_skills = not args.hooks or args.skills
    do_hooks = not args.skills or args.hooks
    if not args.skills and not args.hooks:
        do_skills = do_hooks = True

    categories = [args.category] if args.category else None
    targets = load_targets()
    if args.agent:
        targets = [t for t in targets if t["name"] == args.agent]
    if not targets:
        print("没有匹配的 agent 目标")
        return

    for target in targets:
        name = target["name"]
        print(f"\n=== {name} ===")

        if do_skills:
            count = sync_skills(target, categories)
            print(f"  skills: 已同步到 {target['skills_dir']}")

        if do_hooks:
            sync_hooks(target)
            hooks_dir = target.get("hooks_dir", "(未配置)")
            print(f"  hooks: 已同步到 {hooks_dir}")


if __name__ == "__main__":
    main()
