#!/usr/bin/env python3
"""
将 SkillsStore 的 skills 和 hooks 同步到各 Agent 平台。

用法:
  python sync_skills.py              # 同步 skills + hooks
  python sync_skills.py --skills     # 只同步 skills
  python sync_skills.py --hooks      # 只同步 hooks
  python sync_skills.py --agent hermes  # 只同步到指定 agent
"""

import argparse
import json
import os
import shutil
from pathlib import Path

STORE_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = STORE_ROOT / "custom-skills"
HOOKS_SRC = STORE_ROOT / "hooks"
TARGETS_FILE = Path(__file__).resolve().parent / "agent_targets.json"


def load_targets(agent_name: str | None = None) -> list[dict]:
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    agents = [a for a in data["agents"] if a.get("enabled", True)]
    if agent_name:
        agents = [a for a in agents if a["name"] == agent_name]
    return agents


def sync_skills(target: dict) -> int:
    """同步 skills 到目标 agent，返回同步数量"""
    skills_dir = Path(target["skills_dir"]).expanduser()
    skills_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for skill_path in SKILLS_SRC.rglob("SKILL.md"):
        skill_dir = skill_path.parent
        rel = skill_dir.relative_to(SKILLS_SRC)
        dest = skills_dir / rel
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill_dir, dest)
        count += 1

    return count


def sync_hooks(target: dict) -> int:
    """同步 hooks 到目标 agent，只同步该 agent 对应子目录下的 hooks"""
    hooks_dir = Path(target.get("hooks_dir", "")).expanduser()
    if not target.get("hooks_dir") or not hooks_dir:
        return 0

    agent_name = target["name"]
    agent_hooks_src = HOOKS_SRC / agent_name
    if not agent_hooks_src.exists():
        return 0

    hooks_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for hook_dir in agent_hooks_src.iterdir():
        if not hook_dir.is_dir():
            continue
        dest = hooks_dir / hook_dir.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(hook_dir, dest)
        count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="同步 SkillsStore 到各 Agent 平台")
    parser.add_argument("--skills", action="store_true", help="只同步 skills")
    parser.add_argument("--hooks", action="store_true", help="只同步 hooks")
    parser.add_argument("--agent", type=str, help="只同步到指定 agent")
    args = parser.parse_args()

    do_skills = not args.hooks or args.skills
    do_hooks = not args.skills or args.hooks
    # 如果两个都没指定，都做
    if not args.skills and not args.hooks:
        do_skills = do_hooks = True

    targets = load_targets(args.agent)
    if not targets:
        print("没有匹配的 agent 目标")
        return

    for target in targets:
        name = target["name"]
        print(f"\n=== {name} ===")

        if do_skills:
            count = sync_skills(target)
            print(f"  skills: {count} 个技能同步到 {target['skills_dir']}")

        if do_hooks:
            count = sync_hooks(target)
            print(f"  hooks: {count} 个 hook 同步到 {target.get('hooks_dir', '(未配置)')}")


if __name__ == "__main__":
    main()
