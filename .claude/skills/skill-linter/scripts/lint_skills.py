#!/usr/bin/env python3
"""技能仓库 Lint 检查：合并到单一脚本，一次跑完所有检查项。"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

def _find_repo_root() -> Path:
    """沿目录树向上查找包含 CLAUDE.md 的仓库根目录。"""
    for p in Path(__file__).resolve().parents:
        if (p / "CLAUDE.md").is_file():
            return p
    raise FileNotFoundError("找不到仓库根目录（缺少 CLAUDE.md）")

ROOT = _find_repo_root()
SKILLS_DIR = ROOT / "custom-skills"
HERMES_SKILLS = Path.home() / ".hermes" / "skills" / "inv-skills"
DEPLOY_JSON = ROOT / ".claude" / "skills" / "skill-deployer" / "scripts" / "deploy.json"
CLAUDE_MD = ROOT / "CLAUDE.md"

ERRORS = 0
WARNINGS = 0

def err(msg: str) -> None:
    global ERRORS
    print(f"  ❌ {msg}")
    ERRORS += 1

def warn(msg: str) -> None:
    global WARNINGS
    print(f"  ⚠ {msg}")
    WARNINGS += 1

def ok(msg: str) -> None:
    print(f"  ✅ {msg}")

# ── 工具函数 ─────────────────────────────────────────────────────────────

def find_skills() -> dict[str, Path]:
    """返回 {skill_name: skill_dir} 映射。"""
    skills = {}
    if not SKILLS_DIR.exists():
        return skills
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name == "_shared":
            continue
        if (d / "SKILL.md").exists():
            skills[d.name] = d
    return skills

def parse_frontmatter(path: Path) -> dict | None:
    """解析 Markdown YAML frontmatter。
    先找 --- 起止边界，再逐行解析 key: value。
    支持多行值（缩进续行）、引号值、简单列表。"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None

    lines = text.split("\n")
    if lines[0].strip() != "---":
        return None

    # 找闭合 ---
    end_idx = None
    for i in range(1, min(len(lines), 30)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None

    result = {}
    current_key = None
    current_val: list[str] = []

    def flush():
        nonlocal current_key, current_val
        if current_key:
            val = "\n".join(current_val).strip().strip('"').strip("'")
            # YAML 列表：每行以 "- item" 开头
            if val and all(line.strip().startswith("- ") for line in val.split("\n") if line.strip()):
                val = [line.strip()[2:].strip().strip('"').strip("'") for line in val.split("\n") if line.strip().startswith("- ")]
            elif val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            result[current_key] = val
            current_key = None
            current_val = []

    for line in lines[1:end_idx]:
        # YAML 列表项：以 "- " 开头
        if current_key and re.match(r"^\s*-\s+", line):
            item = re.sub(r"^\s*-\s+", "", line).strip().strip('"').strip("'")
            if item:
                current_val.append(f"- {item}")  # 保留列表标记供后续解析
            continue

        # 多行值的续行（缩进开头，但不是列表项）
        if current_key and (line.startswith("  ") or line.startswith("\t")):
            current_val.append(line.strip())
            continue

        # 遇到新 key，先 flush 上一个
        if ":" in line and not line.startswith((" ", "\t", "#")):
            flush()
            key, _, val = line.partition(":")
            current_key = key.strip()
            current_val = [val.strip()] if val.strip() else []
        elif current_key and line.strip():
            current_val.append(line.strip())

    flush()
    return result

def find_empty_dirs() -> list[Path]:
    """找出没有 SKILL.md 的技能目录（空壳）。"""
    empty = []
    if not SKILLS_DIR.exists():
        return empty
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name == "_shared":
            continue
        if not (d / "SKILL.md").exists():
            empty.append(d)
    return empty

# ── 1. SKILL.md 校验 ───────────────────────────────────────────────────

def _check_description_best_practices(name: str, desc: str) -> None:
    """检查 description 字段是否符合最佳实践。"""
    # 规则1：不要包含触发词（"当...时"），那是 trigger 字段的职责
    if re.search(r"当.*时[使用触发调用执行]", desc):
        warn(f"{name}: description 包含触发句式（'当...时'），应改为功能描述")

    # 规则2：不要嵌入多个引号包裹的触发短语
    quote_count = len(re.findall(r'"[^"]*"', desc)) + len(re.findall(r'","[^"]*"', desc))
    if quote_count >= 3:
        warn(f"{name}: description 嵌入了触发短语（{quote_count} 处引号），应移至 trigger 字段")

    # 规则3：中文描述 ≤60 字，英文 ≤120 字符。按中文字符占比选择阈值
    chinese_chars = len(re.findall(r'[一-鿿]', desc))
    if chinese_chars > len(desc) * 0.3:
        threshold = 80  # 中文为主，80 字符（约 40 汉字+标点）
    else:
        threshold = 120  # 英文为主
    if len(desc) > threshold:
        warn(f"{name}: description 过长（{len(desc)} 字符），建议精简")

    # 规则4：不要以省略号结尾
    if desc.rstrip().endswith("..."):
        err(f"{name}: description 以省略号结尾，疑似截断")

    # 规则5：功能描述优于场景描述
    if desc.startswith("当"):
        warn(f"{name}: description 以'当'开头（场景描述），建议改为功能描述")

def check_skill_md(skills: dict[str, Path]) -> None:
    print("\n── 1. SKILL.md 校验 ──")

    for name, skill_dir in sorted(skills.items()):
        skmd = skill_dir / "SKILL.md"
        if not skmd.exists():
            err(f"{name}: 缺少 SKILL.md")
            continue

        fm = parse_frontmatter(skmd)
        if fm is None:
            err(f"{name}: SKILL.md 缺少有效的 frontmatter (--- ... ---)")
            continue

        # name 与目录名一致
        fm_name = fm.get("name", "")
        if not fm_name:
            err(f"{name}: frontmatter 缺少 name")
        elif fm_name != name:
            err(f"{name}: frontmatter name={fm_name}，与目录名不匹配")

        # version
        fm_version = fm.get("version", "")
        if not fm_version:
            warn(f"{name}: frontmatter 缺少 version")

        # description
        fm_desc = fm.get("description", "")
        if not fm_desc:
            warn(f"{name}: frontmatter 缺少 description")
        else:
            _check_description_best_practices(name, str(fm_desc))

        # trigger/triggers 字段一致性
        if "trigger" in fm and "triggers" in fm:
            warn(f"{name}: frontmatter 同时有 trigger 和 triggers，建议统一为一个")

        # dependencies 引用的技能是否存在
        deps = fm.get("dependencies", [])
        if isinstance(deps, str):
            deps = [deps]
        for dep in deps:
            if dep not in skills:
                err(f"{name}: dependencies 引用不存在的技能 {dep}")

        # scripts 文件存在性
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            for f in sorted(scripts_dir.iterdir()):
                if f.is_file() and not f.name.startswith(".") and f.suffix == ".py":
                    if not f.exists():
                        err(f"{name}: scripts/{f.name} 文件不存在")

    ok("SKILL.md 校验完成")

# ── 2. 命名规范校验 ──────────────────────────────────────────────────────

def check_naming(skills: dict[str, Path]) -> None:
    print("\n── 2. 命名规范 ──")

    for name in sorted(skills.keys()):
        if "-" not in name:
            err(f"{name}: 命名不符合规范，期望格式 `{{前缀}}-{{语义名}}`")

    ok("命名规范校验完成")

# ── 3. 空壳目录 ──────────────────────────────────────────────────────────

def check_empty_dirs() -> None:
    print("\n── 3. 空壳目录 ──")

    empty = find_empty_dirs()
    if empty:
        for d in empty:
            warn(f"{d.relative_to(ROOT)}: 无 SKILL.md，疑似空壳目录")
    else:
        ok("无空壳目录")

# ── 4. deploy.json 一致性 ────────────────────────────────────────────────

def check_deploy_json(skills: dict[str, Path]) -> None:
    print("\n── 4. deploy.json 一致性 ──")

    if not DEPLOY_JSON.exists():
        err("deploy.json 不存在")
        return

    deploy = json.loads(DEPLOY_JSON.read_text(encoding="utf-8"))

    # 检查 agents 配置完整性
    agents_cfg = deploy.get("agents", {})
    if not agents_cfg:
        warn("deploy.json 未配置任何 agent")
    for agent_name, cfg in agents_cfg.items():
        if "skills_dir" not in cfg or not cfg["skills_dir"]:
            warn(f"deploy.json agent={agent_name} 缺少 skills_dir")

    ok("deploy.json 一致性检查完成")

# ── 5. CLAUDE.md 一致性 ──────────────────────────────────────────────────

def check_claude_md(skills: dict[str, Path]) -> None:
    print("\n── 5. CLAUDE.md 一致性 ──")

    if not CLAUDE_MD.exists():
        err(f"CLAUDE.md 不存在: {CLAUDE_MD}")
        return

    claude_text = CLAUDE_MD.read_text(encoding="utf-8")
    for name in sorted(skills.keys()):
        if name not in claude_text:
            warn(f"{name}: 未在 CLAUDE.md 中找到")

    ok("CLAUDE.md 一致性检查完成")

# ── 6. SKILL.md 行数 ─────────────────────────────────────────────────────

def check_skill_length(skills: dict[str, Path]) -> None:
    print("\n── 6. SKILL.md 行数 ──")

    for name, skill_dir in sorted(skills.items()):
        lines = len((skill_dir / "SKILL.md").read_text(encoding="utf-8").splitlines())
        if lines > 300:
            warn(f"{name}: {lines} 行（严重超标，建议 <200）")
        elif lines > 200:
            warn(f"{name}: {lines} 行（略超 200 行建议值）")

    ok("行数检查完成")

# ── 7. 脚本可执行性验证 ──────────────────────────────────────────────────

def _is_pep723_script(path: Path) -> bool:
    try:
        return "# /// script" in path.read_text(encoding="utf-8")[:200]
    except Exception:
        return False

def _is_entry_point(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        return 'if __name__ == "__main__"' in text or "argparse" in text
    except Exception:
        return True

def check_scripts(skills: dict[str, Path]) -> None:
    print("\n── 7. 脚本可执行性验证 ──")

    checked = 0
    skipped = 0
    for name, skill_dir in sorted(skills.items()):
        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            continue

        for py_file in sorted(scripts_dir.glob("*.py")):
            if py_file.name.startswith("__"):
                continue

            symlink_path = HERMES_SKILLS / name / "scripts" / py_file.name
            if not symlink_path.exists():
                warn(f"{name}/{py_file.name}: symlink 不存在，跳过")
                continue

            try:
                ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError as e:
                err(f"{name}/{py_file.name}: Python 语法错误: {e}")
                continue

            if not _is_entry_point(py_file):
                skipped += 1
                continue

            checked += 1
            is_pep723 = _is_pep723_script(py_file)
            runner = ["uv", "run"] if is_pep723 else [sys.executable]

            try:
                result = subprocess.run(
                    [*runner, str(symlink_path), "--help"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    ok(f"{name}/{py_file.name} {'(uv)' if is_pep723 else '(py)'}")
                else:
                    warn(f"{name}/{py_file.name}: --help 失败（需 {'uv' if is_pep723 else 'python'}）")
            except subprocess.TimeoutExpired:
                warn(f"{name}/{py_file.name}: --help 超时")
            except FileNotFoundError:
                warn(f"{name}/{py_file.name}: {'uv' if is_pep723 else 'python'} 不可用")
            except Exception as e:
                warn(f"{name}/{py_file.name}: {e}")

    print(f"  入口脚本 {checked} 个，内部模块 {skipped} 个（仅语法检查）")

# ── 8. 跨技能路径解析验证 ──────────────────────────────────────────────

def check_path_resolution() -> None:
    """验证脚本中 __file__ 路径解析是否正确。"""
    print("\n── 8. 跨技能路径解析验证 ──")

    # 先检查：所有用 __file__ 的脚本是否做了 resolve
    unresolved = 0
    for py_file in sorted(SKILLS_DIR.rglob("scripts/*.py")):
        if py_file.name.startswith("__"):
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if "__file__" in text and ".resolve()" not in text and "abspath(__file__)" not in text:
            unresolved += 1
            skill_name = py_file.parent.parent.name
            err(f"{skill_name}/{py_file.name}: __file__ 未调用 .resolve()，软链接下可能路径错误")

    if unresolved:
        err(f"共 {unresolved} 个脚本 __file__ 未 resolve")
    else:
        ok("所有 __file__ 调用均使用 .resolve() 或 abspath")

    # 然后：验证所有 Path(__file__).resolve() 引用的目标存在
    parents_re = re.compile(
        r"Path\(__file__\)\.resolve\(\)\.(?:parents\[(\d+)\]|((?:parent\.)*parent))\s*/\s*['\"]([^'\"]+)['\"]"
    )

    verified = 0
    failed = 0

    for py_file in sorted(SKILLS_DIR.rglob("scripts/*.py")):
        if py_file.name.startswith("__"):
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        skill_name = py_file.parent.parent.name
        symlink = HERMES_SKILLS / skill_name / "scripts" / py_file.name
        if not symlink.exists():
            continue

        # 从 symlink resolve 到源文件
        r = symlink.resolve()

        for m in parents_re.finditer(text):
            n_str = m.group(1)  # parents[N] 中的 N
            parent_chain = m.group(2)  # parent.parent...
            target_dir = m.group(3)

            # 计算层级
            if n_str:
                levels = int(n_str)
            else:
                # parent.parent 对应 parents[1]（count=2 → levels=1）
                levels = parent_chain.count("parent") - 1

            expected = r.parents[levels] / target_dir
            label = f"parents[{levels}]/{target_dir}" if n_str else f"{'parent.' * (levels-1)}parent/{target_dir}"

            if expected.exists():
                verified += 1
            else:
                failed += 1
                warn(f"{skill_name}/{py_file.name}: {label} → 不存在 ({expected})")

    if verified:
        ok(f"路径解析: {verified} 处通过")
    if failed:
        err(f"路径解析: {failed} 处失败")
    if not verified and not failed:
        ok("未发现跨文件路径引用")

# ── 9. 个人路径泄露检查 ────────────────────────────────────────────────

def check_personal_paths(skills: dict[str, Path]) -> None:
    """扫描所有技能文件，检查是否包含 /Users/xxx 等暴露用户名的绝对路径。

    注意：~/xxx 形式的通用路径（如 ~/.skills-store）是合理的，不检查。
    只检查包含真实用户名的绝对路径（如 /Users/chengshun、/home/chengshun）。
    """
    print("\n── 9. 个人路径泄露检查 ──")

    # 只匹配暴露用户名的绝对路径
    personal_path_patterns = [
        re.compile(r"/Users/[^/\s]+"),
        re.compile(r"/home/[^/\s]+"),
        re.compile(r"C:\\\\Users\\\\[^\\\s]+"),
    ]

    found = 0
    for name, skill_dir in sorted(skills.items()):
        # 扫描 SKILL.md 和脚本文件
        for pattern in ["SKILL.md"]:
            file_path = skill_dir / pattern
            if not file_path.exists():
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception:
                continue

            for pat in personal_path_patterns:
                for match in pat.finditer(text):
                    matched = match.group()
                    # 排除环境变量引用
                    if matched.startswith("$"):
                        continue
                    found += 1
                    warn(f"{name}/{pattern}: 包含个人路径 `{matched}`")

        # 扫描脚本文件
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            for py_file in sorted(scripts_dir.glob("*.py")):
                try:
                    text = py_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                for pat in personal_path_patterns:
                    for match in pat.finditer(text):
                        matched = match.group()
                        if matched.startswith("$"):
                            continue
                        found += 1
                        warn(f"{name}/scripts/{py_file.name}: 包含个人路径 `{matched}`")

    if found:
        err(f"共发现 {found} 处个人路径泄露")
    else:
        ok("未发现个人路径泄露")

    if found:
        err(f"共发现 {found} 处个人路径泄露")
    else:
        ok("未发现个人路径泄露")

# ── main ─────────────────────────────────────────────────────────────────

def main() -> int:
    global ERRORS, WARNINGS

    print("=" * 60)
    print("Skills Lint 检查")
    print("=" * 60)

    if not HERMES_SKILLS.exists() or not any(HERMES_SKILLS.iterdir()):
        print("⚠ hermes 尚未部署，请执行: python3 .claude/skills/skill-deployer/scripts/sync.py --agent hermes")

    skills = find_skills()
    print(f"\n发现 {len(skills)} 个技能\n")

    
    check_skill_md(skills)
    check_naming(skills)
    check_empty_dirs()
    check_deploy_json(skills)
    check_claude_md(skills)
    check_skill_length(skills)
    check_scripts(skills)
    check_path_resolution()
    check_personal_paths(skills)

    print("\n" + "=" * 60)
    print(f"结果: {ERRORS} 错误, {WARNINGS} 警告")
    print("=" * 60)

    return 1 if ERRORS > 0 else 0

if __name__ == "__main__":
    raise SystemExit(main())
