#!/usr/bin/env python3
"""
Skills & hooks 同步脚本。

用法:
  python sync.py --profile home
  python sync.py --profile work --dry-run
  python sync.py --profile home --agent hermes
  python sync.py --profile home --hooks-only
  python sync.py --list

profile 在 deploy.yaml 中定义，包含每个 agent 需要同步哪些分类。
base 分类始终同步，无需在 profile 中声明。
"""

import argparse
import json
import shutil
from pathlib import Path

STORE_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = STORE_ROOT / "custom-skills"
HOOKS_SRC = STORE_ROOT / "hooks"
DEPLOY_FILE = STORE_ROOT / "deploy.json"


def load_config() -> dict:
    with open(DEPLOY_FILE, encoding="utf-8") as f:
        return json.load(f)


def _remove(path: Path):
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def sync_skills(categories: list[str], skills_dir: str) -> int:
    dest_root = Path(skills_dir).expanduser()
    dest_root.mkdir(parents=True, exist_ok=True)
    count = 0

    # base always synced
    base = SKILLS_SRC / "base"
    if base.exists():
        for item in base.iterdir():
            if not item.is_dir():
                continue
            dest = dest_root / item.name
            _remove(dest)
            shutil.copytree(str(item), str(dest))
            count += 1

    for cat in categories:
        cat_dir = SKILLS_SRC / cat
        if not cat_dir.exists():
            continue
        for item in cat_dir.iterdir():
            if not item.is_dir() or not (item / "SKILL.md").exists():
                continue
            dest = dest_root / item.name
            _remove(dest)
            shutil.copytree(str(item), str(dest))
            count += 1

    return count


def sync_hooks(agent_name: str, hooks_dir: str) -> int:
    src = HOOKS_SRC / agent_name
    if not src.exists():
        return 0

    dest_root = Path(hooks_dir).expanduser()
    dest_root.mkdir(parents=True, exist_ok=True)
    count = 0

    for hook_dir in src.iterdir():
        if not hook_dir.is_dir():
            continue
        dest = dest_root / hook_dir.name
        _remove(dest)
        shutil.copytree(str(hook_dir), str(dest))
        count += 1

    return count


def list_profiles(config: dict):
    print("Available profiles:")
    for name, agents in sorted(config["profiles"].items()):
        print(f"\n  {name}:")
        for agent, categories in agents.items():
            cats = ", ".join(categories)
            print(f"    {agent}: [{cats}]")


def main():
    parser = argparse.ArgumentParser(description="Sync skills & hooks to agents")
    parser.add_argument("--profile", required=True, help="profile name (required)")
    parser.add_argument("--agent", help="only sync this agent")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hooks-only", action="store_true")
    parser.add_argument("--skills-only", action="store_true")
    parser.add_argument("--list", action="store_true", help="list available profiles")
    args = parser.parse_args()

    config = load_config()

    if args.list:
        list_profiles(config)
        return

    profile = config["profiles"].get(args.profile)
    if not profile:
        print(f"profile '{args.profile}' not found in deploy.yaml")
        print("available:", ", ".join(sorted(config["profiles"])))
        return

    agents_cfg = config["agents"]

    for agent_name, categories in profile.items():
        if args.agent and agent_name != args.agent:
            continue

        cfg = agents_cfg.get(agent_name)
        if not cfg:
            print(f"  unknown agent: {agent_name}")
            continue

        print(f"\n=== {agent_name} ===")

        if not args.hooks_only:
            if args.dry_run:
                print(f"  [dry-run] skills: base + {categories} → {cfg['skills_dir']}")
            else:
                n = sync_skills(categories, cfg["skills_dir"])
                print(f"  skills: {n} synced → {cfg['skills_dir']}")

        if not args.skills_only:
            if args.dry_run:
                print(f"  [dry-run] hooks: → {cfg.get('hooks_dir', '(none)')}")
            else:
                n = sync_hooks(agent_name, cfg.get("hooks_dir", ""))
                print(f"  hooks: {n} synced → {cfg.get('hooks_dir', '(none)')}")

    print("\nDone.")


if __name__ == "__main__":
    main()
