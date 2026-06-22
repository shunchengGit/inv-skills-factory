#!/usr/bin/env python3
"""技能仓库 Lint 检查：合并到单一脚本，一次跑完所有检查项。"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "custom-skills"
HERMES_SKILLS = Path.home() / ".hermes" / "skills" / "skills-store"
DEPLOY_JSON = ROOT / ".claude" / "skills" / "deploy-skills" / "scripts" / "deploy.json"
CLAUDE_MD = ROOT / "CLAUDE.md"
SKILL_INDEX_FILE = SKILLS_DIR / "base" / "base-skill-loader" / "SKILL.md"

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
    for d in sorted(SKILLS_DIR.rglob("SKILL.md")):
        if "_shared" in d.parts or ".archive" in d.parts:
            continue
        name = d.parent.name
        skills[name] = d.parent
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
    """找出没有 SKILL.md 的技能目录（空壳），不再硬编码分类。"""
    empty = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name == "_shared":
            continue
        # 一级目录（分类目录如 base/general/invest）
        if (d / "SKILL.md").exists():
            continue
        for sub in sorted(d.iterdir()):
            if sub.is_dir() and not sub.name.startswith(".") and sub.name != "_shared":
                if not (sub / "SKILL.md").exists():
                    empty.append(sub)
    return empty


def get_category(name: str, skills: dict[str, Path]) -> str | None:
    """根据技能名获取其分类目录名。"""
    if name in skills:
        return skills[name].parent.name
    return None


# ── 1. _meta.json 校验 ──────────────────────────────────────────────────

def check_meta_json(skills: dict[str, Path]) -> None:
    print("\n── 1. _meta.json 校验 ──")

    for name, skill_dir in sorted(skills.items()):
        meta_file = skill_dir / "_meta.json"

        # 1a. 存在性
        if not meta_file.exists():
            err(f"{name}: 缺少 _meta.json")
            continue

        # 1b. JSON 语法
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            err(f"{name}: _meta.json JSON 解析失败: {e}")
            continue

        # 1c. name 与实际目录一致
        meta_name = meta.get("name", "")
        if meta_name != name:
            err(f"{name}: _meta.json name={meta_name}，与目录名不匹配")

        # 1d. 必需字段
        for field in ["version", "description"]:
            if not meta.get(field):
                warn(f"{name}: _meta.json 缺少 {field}")

        # 1e. dependencies 引用的技能是否存在
        deps = meta.get("dependencies", [])
        for dep in deps:
            if dep not in skills:
                err(f"{name}: dependencies 引用不存在的技能 {dep}")

        # 1f. 跨分类依赖检查
        cat = get_category(name, skills)
        if cat:
            for dep in deps:
                dep_cat = get_category(dep, skills)
                if dep_cat and dep_cat != cat:
                    warn(f"{name}: 跨分类引用 {dep}（{cat} → {dep_cat}），违反隔离原则")

        # 1g. scripts 指向的文件是否存在
        for script_key, script_path in meta.get("scripts", {}).items():
            if "/" in str(script_path) or str(script_path).endswith(".py"):
                full_path = skill_dir / script_path
            else:
                full_path = skill_dir / "scripts" / script_key
            if not full_path.exists():
                err(f"{name}: scripts.{script_key} → 文件不存在")

        # 1h. derivedFrom 引用的源技能是否存在（如果是字符串且为技能名）
        derived = meta.get("derivedFrom")
        if derived and isinstance(derived, str) and derived not in skills:
            # 允许 null / 非技能名的描述
            if "-" in derived:
                warn(f"{name}: derivedFrom={derived}，该技能可能不存在")

    # 1i. 反过来：有没有 _meta.json 但无 SKILL.md 的
    for mf in sorted(SKILLS_DIR.rglob("_meta.json")):
        skill_dir = mf.parent
        if "_shared" in skill_dir.parts or ".archive" in skill_dir.parts:
            continue
        if not (skill_dir / "SKILL.md").exists():
            err(f"{skill_dir.name}: 有 _meta.json 但缺少 SKILL.md")

    ok("_meta.json 校验完成")


# ── 2. SKILL.md frontmatter 校验 ────────────────────────────────────────

def _check_description_best_practices(name: str, desc: str) -> None:
    """检查 description 字段是否符合最佳实践。"""
    # 规则1：不要包含触发词（"当...时"），那是 trigger 字段的职责
    if re.search(r"当.*时[使用触发调用执行]", desc):
        warn(f"{name}: description 包含触发句式（'当...时'），应改为功能描述")

    # 规则2：不要嵌入多个引号包裹的触发短语
    quote_count = len(re.findall(r'"[^"]*"', desc)) + len(re.findall(r'"[^"]*"', desc))
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

    # 规则6：应与 _meta.json 的 description 一致
    for cat_dir in sorted(SKILLS_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        p = cat_dir / name / "_meta.json"
        if p.exists():
            meta = json.loads(p.read_text(encoding="utf-8"))
            meta_desc = meta.get("description", "")
            if meta_desc and meta_desc != desc:
                warn(f"{name}: frontmatter description 与 _meta.json 不一致")
            break


def check_frontmatter(skills: dict[str, Path]) -> None:
    print("\n── 2. SKILL.md frontmatter 校验 ──")

    for name, skill_dir in sorted(skills.items()):
        fm = parse_frontmatter(skill_dir / "SKILL.md")
        if fm is None:
            err(f"{name}: SKILL.md 缺少有效的 frontmatter (--- ... ---)")
            continue

        if "name" not in fm:
            err(f"{name}: frontmatter 缺少 name")
        elif fm["name"] != name:
            err(f"{name}: frontmatter name={fm['name']}，与目录名不匹配")

        if "version" not in fm:
            warn(f"{name}: frontmatter 缺少 version")
        if "description" not in fm:
            warn(f"{name}: frontmatter 缺少 description")
        else:
            _check_description_best_practices(name, str(fm["description"]))

        # trigger/triggers 字段一致性（有些用单数有些用复数，都接受）
        if "trigger" in fm and "triggers" in fm:
            warn(f"{name}: frontmatter 同时有 trigger 和 triggers，建议统一为一个")

        # 交叉验证 version / description / commands 与 _meta.json 一致
        meta_file = skill_dir / "_meta.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if "version" in fm and "version" in meta:
                if str(fm["version"]) != str(meta["version"]):
                    warn(f"{name}: version 不一致（fm={fm['version']} vs meta={meta['version']}）")

            # commands 字段一致性
            fm_cmds = fm.get("commands", [])
            meta_cmds = meta.get("commands", [])
            if isinstance(fm_cmds, str):
                fm_cmds = [fm_cmds]
            if fm_cmds and meta_cmds:
                fm_set = set(c.strip() for c in fm_cmds)
                meta_set = set(c.strip() for c in meta_cmds)
                if fm_set != meta_set:
                    warn(f"{name}: commands 不一致")

    ok("frontmatter 校验完成")


# ── 3. 命名规范校验 ──────────────────────────────────────────────────────

def check_naming(skills: dict[str, Path]) -> None:
    print("\n── 3. 命名规范 ──")

    prefix_map = {"base": "base-", "general": "gen-", "invest": "inv-"}

    for name, skill_dir in sorted(skills.items()):
        parent = skill_dir.parent.name
        expected_prefix = prefix_map.get(parent)
        if expected_prefix is None:
            warn(f"{name}: 未知分类目录 {parent}")
            continue
        if not name.startswith(expected_prefix):
            err(f"{name}: 命名不符合规范，期望前缀 {expected_prefix}")

    ok("命名规范校验完成")


# ── 4. 空壳目录 ──────────────────────────────────────────────────────────

def check_empty_dirs() -> None:
    print("\n── 4. 空壳目录 ──")

    empty = find_empty_dirs()
    if empty:
        for d in empty:
            warn(f"{d.relative_to(ROOT)}: 无 SKILL.md，疑似空壳目录")
    else:
        ok("无空壳目录")


# ── 5. deploy.json 一致性 ────────────────────────────────────────────────

def check_deploy_json(skills: dict[str, Path]) -> None:
    print("\n── 5. deploy.json 一致性 ──")

    if not DEPLOY_JSON.exists():
        err("deploy.json 不存在")
        return

    deploy = json.loads(DEPLOY_JSON.read_text(encoding="utf-8"))

    # 收集各分类的实际技能
    categories: dict[str, set[str]] = defaultdict(set)
    for name, skill_dir in skills.items():
        cat = skill_dir.parent.name
        categories[cat].add(name)

    # 检查 profile 引用的分类
    for profile_name, agents in deploy.get("profiles", {}).items():
        for agent, cat_list in agents.items():
            for cat in cat_list:
                if cat not in categories and cat != "base":
                    warn(f"deploy.json profile={profile_name} 引用未知分类 {cat}")

    ok("deploy.json 一致性检查完成")


# ── 6. 索引表一致性 ──────────────────────────────────────────────────────

def check_index(skills: dict[str, Path]) -> None:
    print("\n── 6. 索引表与 CLAUDE.md 一致性 ──")

    if not SKILL_INDEX_FILE.exists():
        err(f"索引文件不存在: {SKILL_INDEX_FILE}")
        return

    index_text = SKILL_INDEX_FILE.read_text(encoding="utf-8")

    # 从索引表提取已登记技能
    indexed = set()
    for m in re.finditer(r"\|\s*\*\*(.*?)\*\*\s*\|", index_text):
        name = m.group(1).strip()
        if "-" in name:
            indexed.add(name)

    # 有 SKILL.md 但不在索引表中
    missing = set(skills.keys()) - indexed
    for name in sorted(missing):
        warn(f"{name}: 有 SKILL.md 但不在索引表中")

    # 在索引表但无 SKILL.md
    stale = indexed - set(skills.keys())
    for name in sorted(stale):
        err(f"{name}: 在索引表中但无 SKILL.md")

    # CLAUDE.md 目录结构中是否列出
    claude_text = CLAUDE_MD.read_text(encoding="utf-8")
    for name in sorted(skills.keys()):
        if name not in claude_text:
            warn(f"{name}: 未在 CLAUDE.md 中找到")

    ok("索引表一致性检查完成")


# ── 7. SKILL.md 行数 ─────────────────────────────────────────────────────

def check_skill_length(skills: dict[str, Path]) -> None:
    print("\n── 7. SKILL.md 行数 ──")

    for name, skill_dir in sorted(skills.items()):
        lines = len((skill_dir / "SKILL.md").read_text(encoding="utf-8").splitlines())
        if lines > 300:
            warn(f"{name}: {lines} 行（严重超标，建议 <200）")
        elif lines > 200:
            warn(f"{name}: {lines} 行（略超 200 行建议值）")

    ok("行数检查完成")


# ── 8. 脚本可执行性验证 ──────────────────────────────────────────────────

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
    print("\n── 8. 脚本可执行性验证 ──")

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


# ── 9. 跨技能路径解析验证 ──────────────────────────────────────────────

def check_path_resolution() -> None:
    """验证脚本中 __file__ 路径解析是否正确。"""
    print("\n── 9. 跨技能路径解析验证 ──")

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


# ── 10. 个人路径泄露检查 ────────────────────────────────────────────────

def check_personal_paths(skills: dict[str, Path]) -> None:
    """扫描所有技能文件，检查是否包含 /Users/xxx 等暴露用户名的绝对路径。

    注意：~/xxx 形式的通用路径（如 ~/.skills-store）是合理的，不检查。
    只检查包含真实用户名的绝对路径（如 /Users/chengshun、/home/chengshun）。
    """
    print("\n── 10. 个人路径泄露检查 ──")

    # 只匹配暴露用户名的绝对路径
    personal_path_patterns = [
        re.compile(r"/Users/[^/\s]+"),
        re.compile(r"/home/[^/\s]+"),
        re.compile(r"C:\\\\Users\\\\[^\\\s]+"),
    ]

    found = 0
    for name, skill_dir in sorted(skills.items()):
        # 扫描 SKILL.md、_meta.json、脚本文件
        for pattern in ["SKILL.md", "_meta.json"]:
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


# ── 11. references 目录与 _meta.json 一致性 ──────────────────────────────

def check_references_consistency(skills: dict[str, Path]) -> None:
    """检查 references/ 目录下的文件与 _meta.json references 字段是否一致。"""
    print("\n── 11. references 目录与 _meta.json 一致性 ──")

    for name, skill_dir in sorted(skills.items()):
        meta_file = skill_dir / "_meta.json"
        if not meta_file.exists():
            continue

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        meta_refs = set(meta.get("references", {}).keys())

        refs_dir = skill_dir / "references"
        actual_refs = set()
        if refs_dir.is_dir():
            for f in sorted(refs_dir.iterdir()):
                if f.is_file() and not f.name.startswith("."):
                    actual_refs.add(f.name)

        # meta 声明了但实际不存在
        missing = meta_refs - actual_refs
        for ref in sorted(missing):
            warn(f"{name}: _meta.json 声明 references.{ref} 但文件不存在")

        # 实际存在但未在 meta 声明
        extra = actual_refs - meta_refs
        for ref in sorted(extra):
            warn(f"{name}: references/{ref} 存在但未在 _meta.json 中声明")

    ok("references 一致性检查完成")


# ── 12. scripts 目录与 _meta.json 一致性 ─────────────────────────────────

def check_scripts_consistency(skills: dict[str, Path]) -> None:
    """检查 scripts/ 目录下的文件与 _meta.json scripts 字段是否一致。"""
    print("\n── 12. scripts 目录与 _meta.json 一致性 ──")

    for name, skill_dir in sorted(skills.items()):
        meta_file = skill_dir / "_meta.json"
        if not meta_file.exists():
            continue

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        meta_scripts = set(meta.get("scripts", {}).keys())

        scripts_dir = skill_dir / "scripts"
        actual_scripts = set()
        if scripts_dir.is_dir():
            for f in sorted(scripts_dir.iterdir()):
                if f.is_file() and not f.name.startswith("."):
                    # 去掉扩展名作为 key
                    stem = f.stem
                    actual_scripts.add(stem)

        # meta 声明了但实际不存在
        missing = meta_scripts - actual_scripts
        for script in sorted(missing):
            warn(f"{name}: _meta.json 声明 scripts.{script} 但文件不存在")

        # 实际存在但未在 meta 声明（排除 __init__.py 等）
        extra = actual_scripts - meta_scripts
        for script in sorted(extra):
            warn(f"{name}: scripts/{script} 存在但未在 _meta.json 中声明")

    ok("scripts 一致性检查完成")


# ── 13. 未使用分类检查 ───────────────────────────────────────────────────

def check_unused_categories(skills: dict[str, Path]) -> None:
    """检查是否有分类目录未被 deploy.json 引用（base 除外）。"""
    print("\n── 13. 未使用分类检查 ──")

    if not DEPLOY_JSON.exists():
        err("deploy.json 不存在")
        return

    deploy = json.loads(DEPLOY_JSON.read_text(encoding="utf-8"))

    # 收集 deploy.json 中引用的所有分类
    used_cats: set[str] = set()
    for profile_name, agents in deploy.get("profiles", {}).items():
        for agent, cat_list in agents.items():
            used_cats.update(cat_list)

    # 收集实际存在的分类目录
    actual_cats: set[str] = set()
    for d in sorted(SKILLS_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and d.name not in ("_shared",):
            actual_cats.add(d.name)

    unused = actual_cats - used_cats - {"base"}
    for cat in sorted(unused):
        warn(f"分类 `{cat}` 未在 deploy.json 中引用")

    ok("未使用分类检查完成")


# ── main ─────────────────────────────────────────────────────────────────

def main() -> int:
    global ERRORS, WARNINGS

    print("=" * 60)
    print("Skills Lint 检查")
    print("=" * 60)

    if not (HERMES_SKILLS / "base-skill-loader").exists():
        print("⚠ 尚未部署，正在部署 home profile...")
        subprocess.run(
            [sys.executable, str(ROOT / "deploy" / "sync.py"), "--profile", "home"],
            cwd=ROOT,
        )

    skills = find_skills()
    print(f"\n发现 {len(skills)} 个技能\n")

    check_meta_json(skills)
    check_frontmatter(skills)
    check_naming(skills)
    check_empty_dirs()
    check_deploy_json(skills)
    check_index(skills)
    check_skill_length(skills)
    check_scripts(skills)
    check_path_resolution()
    check_personal_paths(skills)
    check_references_consistency(skills)
    check_scripts_consistency(skills)
    check_unused_categories(skills)

    print("\n" + "=" * 60)
    print(f"结果: {ERRORS} 错误, {WARNINGS} 警告")
    print("=" * 60)

    return 1 if ERRORS > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
