#!/usr/bin/env python3
"""将 custom-skills/ 中的技能通过软链接同步到各 Agent 的技能目录。

用法:
  python3 sync_skills.py                  # 执行同步
  python3 sync_skills.py --dry-run        # 仅预览，不执行变更
  python3 sync_skills.py --config agent_targets.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


def _resolve(path: str) -> Path:
    """展开 ~ 并返回绝对路径。"""
    return Path(os.path.expanduser(path)).resolve()


def read_config(config_path: Path) -> list[dict]:
    """读取 agent_targets.json，返回 enabled Agent 列表。

    对每个 Agent 展开 skills_dir 中的 ~。
    """
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"错误: 配置文件 JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    agents = data.get("agents", [])
    if not isinstance(agents, list):
        print("错误: agents 必须是数组", file=sys.stderr)
        sys.exit(1)

    result = []
    for agent in agents:
        if not agent.get("enabled", True):
            print(f"[跳过] {agent.get('name', 'unknown')}: enabled=false")
            continue
        name = agent.get("name", "unknown")
        raw_dir = agent.get("skills_dir")
        if not raw_dir:
            print(f"[跳过] {name}: skills_dir 未配置", file=sys.stderr)
            continue
        agent["skills_dir"] = str(_resolve(raw_dir))
        result.append(agent)

    return result


def discover_skills(custom_skills_dir: Path) -> list[Path]:
    """扫描 custom-skills/，返回所有子目录列表（含 _shared 等基础设施目录）。"""
    if not custom_skills_dir.exists():
        print(f"错误: custom-skills 目录不存在: {custom_skills_dir}", file=sys.stderr)
        sys.exit(1)

    skills = []
    for entry in sorted(custom_skills_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            skills.append(entry)
    return skills


def _find_bak_path(target: Path) -> Path:
    """为冲突目录寻找可用的 _bak 名称。

    尝试 target_bak，若已存在则尝试 target_bak2, target_bak3...
    """
    parent = target.parent
    base = target.name
    bak = parent / f"{base}_bak"
    if not bak.exists():
        return bak
    i = 2
    while True:
        bak = parent / f"{base}_bak{i}"
        if not bak.exists():
            return bak
        i += 1


def _is_symlink(path: Path) -> bool:
    """检查路径是否为符号链接。"""
    return path.is_symlink()


def _is_broken_symlink(path: Path) -> bool:
    """检查是否为断开的符号链接。"""
    try:
        path.is_symlink() and not path.exists()
    except Exception:
        pass
    return path.is_symlink() and not os.path.exists(str(path))


def sync_skill(
    skill_dir: Path,
    agent: dict,
    *,
    dry_run: bool = False,
) -> tuple[str, str]:
    """将单个技能同步到单个 Agent。

    返回 (操作类型, 描述)。

    场景:
      - 目标不存在 → 创建软链接
      - 目标已是正确软链接 → 跳过
      - 目标是软链接但指向不同 → 更新
      - 目标是普通目录 → 重命名为 _bak 后创建
      - 目标是断开软链接 → 删除后重建
    """
    skill_name = skill_dir.name
    target = Path(agent["skills_dir"]) / skill_name
    source = skill_dir.resolve()
    agent_name = agent["name"]

    # 场景 A: 目标不存在
    if not target.exists() and not target.is_symlink():
        if dry_run:
            return ("创建", f"[{agent_name}] {skill_name} → {target}")
        target.symlink_to(source, target_is_directory=True)
        return ("创建", f"[{agent_name}] {skill_name} → {target}")

    # 场景 E: 断开的符号链接
    if target.is_symlink() and not target.exists():
        if dry_run:
            return ("重建", f"[{agent_name}] {skill_name}: 断开的链接 → 重建")
        target.unlink()
        target.symlink_to(source, target_is_directory=True)
        return ("重建", f"[{agent_name}] {skill_name}: 断开的链接已重建")

    # 场景 B: 已是正确的符号链接
    if target.is_symlink():
        current_target = os.readlink(str(target))
        resolved_current = _resolve(str(current_target))
        if resolved_current == source:
            return ("跳过", f"[{agent_name}] {skill_name}: 已是正确链接")
        # 场景 C: 符号链接但指向不同
        if dry_run:
            return ("更新", f"[{agent_name}] {skill_name}: {current_target} → {source}")
        target.unlink()
        target.symlink_to(source, target_is_directory=True)
        return ("更新", f"[{agent_name}] {skill_name}: 链接已更新")

    # 场景 D: 目标存在且不是符号链接（普通目录）
    bak_path = _find_bak_path(target)
    if dry_run:
        return ("重命名", f"[{agent_name}] {skill_name}: {target} → {bak_path.name}，然后创建链接")
    target.rename(bak_path)
    target.symlink_to(source, target_is_directory=True)
    return ("重命名", f"[{agent_name}] {skill_name}: {bak_path.name}（备份），已创建链接 → {source}")


def main() -> int:
    parser = argparse.ArgumentParser(description="技能同步脚本")
    parser.add_argument(
        "--config",
        default=None,
        help="agent_targets.json 路径 (默认: 脚本同级目录下的 agent_targets.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不执行任何文件变更",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    custom_skills_dir = repo_root / "custom-skills"
    config_path = Path(args.config) if args.config else (Path(__file__).parent / "agent_targets.json")

    # 读取配置
    agents = read_config(config_path)
    if not agents:
        print("没有 enabled 的 Agent，退出。")
        return 0

    # 发现技能
    skills = discover_skills(custom_skills_dir)
    if not skills:
        print("custom-skills/ 中没有发现有效技能。")
        return 0

    if args.dry_run:
        print("=== DRY RUN 模式: 仅预览，不执行变更 ===\n")

    print(f"Agent 数: {len(agents)}，技能数: {len(skills)}\n")

    # 确保 Agent 技能目录存在
    for agent in agents:
        target_dir = Path(agent["skills_dir"])
        if not target_dir.exists():
            if args.dry_run:
                print(f"[创建目录] {agent['name']}: {target_dir}")
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
                print(f"[创建目录] {agent['name']}: {target_dir}")

    # 执行同步
    stats = {"创建": 0, "跳过": 0, "更新": 0, "重命名": 0, "重建": 0}
    for skill_dir in skills:
        for agent in agents:
            op, msg = sync_skill(skill_dir, agent, dry_run=args.dry_run)
            stats[op] += 1
            print(f"  {msg}")

    # 汇总
    total = sum(stats.values())
    print(f"\n{'=== DRY RUN 预览 ===' if args.dry_run else '=== 同步完成 ==='}")
    print(f"总计: {total} 操作")
    for op, count in stats.items():
        if count > 0:
            print(f"  {op}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
