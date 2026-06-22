#!/usr/bin/env python3
"""
Skills 同步脚本（软链接模式）。

将 SkillsStore 中的技能以软链接方式部署到各 Agent 目录。
软链接指向源目录，修改源文件即刻生效，无需重新同步。

用法:
  python3 .claude/skills/skill-deployer/scripts/sync.py --profile home
  python3 .claude/skills/skill-deployer/scripts/sync.py --profile work --dry-run
  python3 .claude/skills/skill-deployer/scripts/sync.py --profile home --agent hermes
  python3 .claude/skills/skill-deployer/scripts/sync.py --list
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

STORE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(STORE_ROOT / "custom-skills" / "_shared"))
from dotenv import load as _load_dotenv
_load_dotenv()
SKILLS_SRC = STORE_ROOT / "custom-skills"
DEPLOY_FILE = Path(__file__).resolve().parent / "deploy.json"


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


def _collect_expected_skills() -> set[str]:
    """收集期望同步的所有技能目录名（不含路径）"""
    expected = set()
    if not SKILLS_SRC.exists():
        return expected
    # _shared
    if (SKILLS_SRC / "_shared").is_dir():
        expected.add("_shared")
    for item in SKILLS_SRC.iterdir():
        if item.is_dir() and item.name != "_shared" and (item / "SKILL.md").exists():
            expected.add(item.name)
    return expected


def _remove_stale_dirs(dest_root: Path, expected: set[str], dry_run: bool = False, force: bool = False) -> int:
    """清理目标目录中非软链接的过期目录，返回删除/警告数量"""
    count = 0
    if not dest_root.exists():
        return count
    for item in dest_root.iterdir():
        if item.is_symlink():
            continue
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        if item.name in expected:
            continue
        if force:
            if dry_run:
                print(f"  [dry-run] 强制删除过期目录: {item.name}")
            else:
                print(f"  强制删除过期目录: {item.name} (非软链接)")
                shutil.rmtree(item)
            count += 1
        else:
            print(f"  ⚠ 发现过期目录: {item.name} (非软链接，非预期技能)")
            print(f"    手动删除: rm -rf {item}")
            print(f"    或使用 --force 自动清理")
            count += 1
    return count


def _remove_stale_links(dest_root: Path, expected: set[str], dry_run: bool = False) -> int:
    """删除目标目录中不再需要的软链接，返回删除数量"""
    removed = 0
    if not dest_root.exists():
        return removed
    for item in dest_root.iterdir():
        if not item.is_symlink():
            continue
        if item.name not in expected:
            if dry_run:
                print(f"  [dry-run] 删除旧链接: {item.name}")
            else:
                print(f"  删除旧链接: {item.name}")
                item.unlink()
            removed += 1
    return removed


def sync_skills(skills_dir: str, force: bool = False, dry_run: bool = False) -> tuple[int, int, int, int]:
    """同步技能（软链接）。返回 (created, skipped, failed, removed)"""
    dest_root = Path(skills_dir).expanduser()
    dest_root.mkdir(parents=True, exist_ok=True)

    created, skipped, failed = 0, 0, 0

    if not SKILLS_SRC.exists():
        print(f"  ⚠ 技能源目录不存在: {SKILLS_SRC}")
        return 0, 0, 1, 0

    # 同步 _shared 工具模块（如有）
    shared_dir = SKILLS_SRC / "_shared"
    if shared_dir.is_dir():
        label = "_shared"
        target = dest_root / "_shared"
        result = _create_symlink(shared_dir, target, label, force)
        if result:
            created += 1
        else:
            skipped += 1

    for item in SKILLS_SRC.iterdir():
        if not item.is_dir() or item.name == "_shared" or not (item / "SKILL.md").exists():
            continue

        label = item.name
        target = dest_root / item.name
        result = _create_symlink(item, target, label, force)

        if result:
            created += 1
        else:
            skipped += 1

    # 清理旧链接和过期目录
    expected = _collect_expected_skills()
    removed = _remove_stale_links(dest_root, expected, dry_run=dry_run)
    stale_dir_count = _remove_stale_dirs(dest_root, expected, dry_run=dry_run, force=force)
    removed += stale_dir_count

    return created, skipped, failed, removed


def list_profiles(config: dict):
    print("Available profiles:\n")
    for name, agents in sorted(config["profiles"].items()):
        print(f"  {name}: {agents}")


def main():
    parser = argparse.ArgumentParser(description="Sync skills to agents (symlink)")
    parser.add_argument("--profile", default=os.environ.get("SYNC_PROFILE"), help="profile name (default: $SYNC_PROFILE)")
    parser.add_argument("--agent", help="only sync this agent")
    parser.add_argument("--dry-run", action="store_true", help="preview only")
    parser.add_argument("--list", action="store_true", help="list available profiles")
    parser.add_argument("--force", action="store_true", help="force replace non-empty directories")
    args = parser.parse_args()

    config = load_config()

    if args.list:
        list_profiles(config)
        return

    if not args.profile:
        print("请指定 --profile 或在 .env 中设置 SYNC_PROFILE")
        print("available:", ", ".join(sorted(config["profiles"])))
        return

    agents = config["profiles"].get(args.profile)
    if not agents:
        print(f"profile '{args.profile}' not found in deploy.json")
        print("available:", ", ".join(sorted(config["profiles"])))
        return

    agents_cfg = config["agents"]
    total_created, total_skipped, total_failed, total_removed = 0, 0, 0, 0

    for agent_name in agents:
        if args.agent and agent_name != args.agent:
            continue

        cfg = agents_cfg.get(agent_name)
        if not cfg:
            print(f"⚠ unknown agent: {agent_name}")
            continue

        print(f"\n=== {agent_name} ===")

        if args.dry_run:
            print(f"  [dry-run] skills: → {cfg['skills_dir']}")
        else:
            c, s, f, r = sync_skills(cfg["skills_dir"], force=args.force, dry_run=args.dry_run)
            total_created += c
            total_skipped += s
            total_failed += f
            total_removed += r
            print(f"  skills: {c} created, {s} skipped, {f} failed, {r} removed → {cfg['skills_dir']}")

    print(f"\nDone. total: {total_created} created, {total_skipped} skipped, {total_failed} failed, {total_removed} removed")


if __name__ == "__main__":
    main()
