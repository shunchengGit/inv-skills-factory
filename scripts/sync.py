#!/usr/bin/env python3
"""
Skills & hooks 同步脚本（软链接模式）。

将 SkillsStore 中的技能和 hooks 以软链接方式部署到各 Agent 目录。
软链接指向源目录，修改源文件即刻生效，无需重新同步。

用法:
  python sync.py --profile home
  python sync.py --profile work --dry-run
  python sync.py --profile home --agent hermes
  python sync.py --profile home --hooks-only
  python sync.py --list

base 分类始终同步，无需在 profile 中声明。
"""

import argparse
import json
import os
import shutil
from pathlib import Path

STORE_ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = STORE_ROOT / "custom-skills"
HOOKS_SRC = STORE_ROOT / "custom-hooks"
DEPLOY_FILE = STORE_ROOT / "deploy.json"


def load_config() -> dict:
    with open(DEPLOY_FILE, encoding="utf-8") as f:
        return json.load(f)


def _resolve_conflict(target: Path, source: Path, label: str, force: bool = False) -> bool:
    """处理目标路径冲突，返回 True 表示可以继续创建链接"""
    if not target.exists() and not target.is_symlink():
        return True

    # 已是指向同一源的软链接，无需操作
    if target.is_symlink():
        try:
            existing = Path(os.readlink(target))
            if not existing.is_absolute():
                existing = target.parent / existing
            if existing.resolve() == source.resolve():
                return False  # 已正确链接
        except OSError:
            pass
        print(f"  替换软链接: {label} (原指向 {os.readlink(target)})")
        target.unlink()
        return True

    # 是真实目录
    if target.is_dir():
        if force:
            print(f"  强制替换目录: {label} → {target}")
            shutil.rmtree(target)
            return True
        # 空目录直接删除
        if not any(target.iterdir()):
            print(f"  替换空目录: {label}")
            shutil.rmtree(target)
            return True
        # 非空目录，危险操作
        print(f"  ⚠ 跳过: {label} — 目标是非空目录 {target}")
        print(f"    如需覆盖，请使用 --force 或手动删除后重新同步")
        return False

    # 是普通文件
    if force:
        print(f"  强制替换文件: {label}")
    else:
        print(f"  替换文件: {label}")
    target.unlink()
    return True


def _create_symlink(source: Path, target: Path, label: str = "", force: bool = False) -> bool:
    """创建软链接，处理各种异常"""
    if not source.exists():
        print(f"  ⚠ 跳过: {label} — 源不存在 {source}")
        return False

    # 确保目标父目录存在
    target.parent.mkdir(parents=True, exist_ok=True)

    if not _resolve_conflict(target, source, label, force):
        return False  # 已正确或跳过

    try:
        target.symlink_to(source)
        return True
    except OSError as e:
        print(f"  ⚠ 失败: {label} — {e}")
        return False


def sync_skills(categories: list[str], skills_dir: str, force: bool = False) -> tuple[int, int, int]:
    """同步技能（软链接）。返回 (created, skipped, failed)"""
    dest_root = Path(skills_dir).expanduser()
    dest_root.mkdir(parents=True, exist_ok=True)

    created, skipped, failed = 0, 0, 0

    # base 始终同步
    all_categories = ["base"] + categories

    for cat in all_categories:
        cat_dir = SKILLS_SRC / cat
        if not cat_dir.exists():
            print(f"  ⚠ 分类不存在: {cat}")
            failed += 1
            continue

        # 同步 _shared 工具模块（如有）
        shared_dir = cat_dir / "_shared"
        if shared_dir.is_dir():
            label = f"{cat}/_shared"
            target = dest_root / "_shared"
            result = _create_symlink(shared_dir, target, label, force)
            if result:
                created += 1
            else:
                skipped += 1

        for item in cat_dir.iterdir():
            if not item.is_dir() or item.name == "_shared" or not (item / "SKILL.md").exists():
                continue

            label = f"{cat}/{item.name}"
            target = dest_root / item.name
            result = _create_symlink(item, target, label, force)

            if result:
                created += 1
            else:
                skipped += 1

    return created, skipped, failed


def sync_hooks(agent_name: str, hooks_dir: str, force: bool = False) -> tuple[int, int, int]:
    """同步 hooks（软链接）。返回 (created, skipped, failed)"""
    src = HOOKS_SRC / agent_name
    if not src.exists():
        return 0, 0, 0

    dest_root = Path(hooks_dir).expanduser()
    dest_root.mkdir(parents=True, exist_ok=True)

    created, skipped, failed = 0, 0, 0

    for hook_dir in src.iterdir():
        if not hook_dir.is_dir():
            continue

        label = f"{agent_name}/{hook_dir.name}"
        target = dest_root / hook_dir.name
        result = _create_symlink(hook_dir, target, label, force)

        if result:
            created += 1
        else:
            skipped += 1

    return created, skipped, failed


def list_profiles(config: dict):
    print("Available profiles:\n")
    for name, agents in sorted(config["profiles"].items()):
        print(f"  {name}:")
        for agent, categories in agents.items():
            cats = ", ".join(["base"] + categories)
            print(f"    {agent}: [{cats}]")


def main():
    parser = argparse.ArgumentParser(description="Sync skills & hooks to agents (symlink)")
    parser.add_argument("--profile", required=True, help="profile name (required)")
    parser.add_argument("--agent", help="only sync this agent")
    parser.add_argument("--dry-run", action="store_true", help="preview only")
    parser.add_argument("--hooks-only", action="store_true")
    parser.add_argument("--skills-only", action="store_true")
    parser.add_argument("--list", action="store_true", help="list available profiles")
    parser.add_argument("--force", action="store_true", help="force replace non-empty directories")
    args = parser.parse_args()

    config = load_config()

    if args.list:
        list_profiles(config)
        return

    profile = config["profiles"].get(args.profile)
    if not profile:
        print(f"profile '{args.profile}' not found in deploy.json")
        print("available:", ", ".join(sorted(config["profiles"])))
        return

    agents_cfg = config["agents"]
    total_created, total_skipped, total_failed = 0, 0, 0

    for agent_name, categories in profile.items():
        if args.agent and agent_name != args.agent:
            continue

        cfg = agents_cfg.get(agent_name)
        if not cfg:
            print(f"⚠ unknown agent: {agent_name}")
            continue

        print(f"\n=== {agent_name} ===")

        if not args.hooks_only:
            if args.dry_run:
                cats = ", ".join(["base"] + categories)
                print(f"  [dry-run] skills: [{cats}] → {cfg['skills_dir']}")
            else:
                c, s, f = sync_skills(categories, cfg["skills_dir"], force=args.force)
                total_created += c
                total_skipped += s
                total_failed += f
                print(f"  skills: {c} created, {s} skipped, {f} failed → {cfg['skills_dir']}")

        if not args.skills_only:
            hooks_dir = cfg.get("hooks_dir", "")
            if not hooks_dir:
                print(f"  hooks: no hooks_dir configured")
            elif args.dry_run:
                print(f"  [dry-run] hooks: → {hooks_dir}")
            else:
                c, s, f = sync_hooks(agent_name, hooks_dir, force=args.force)
                total_created += c
                total_skipped += s
                total_failed += f
                print(f"  hooks: {c} created, {s} skipped, {f} failed → {hooks_dir}")

    print(f"\nDone. total: {total_created} created, {total_skipped} skipped, {total_failed} failed")


if __name__ == "__main__":
    main()
