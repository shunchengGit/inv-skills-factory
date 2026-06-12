#!/usr/bin/env python3
"""Auto-generate eval dataset using LLM-driven batched generation.

Inspired by wxa-skills-eval's entity_pool → gen_intent pipeline:
  1. Parse SKILL.md → extract command surface / task types / constraints (generic, no LLM)
  2. Batched LLM generation → 10 items per call, covering all task types
  3. Validate, deduplicate, split → train/val/test

Generic design — works for any skill (dd-knowledge, dd-git-workflow, etc.)

Usage:
    python3 auto_generate_dataset.py --skill harnesses/common/skills/dd-knowledge
    python3 auto_generate_dataset.py --skill harnesses/common/skills/dd-knowledge --num-items 40 --batch-size 10
    python3 auto_generate_dataset.py --skill harnesses/common/skills/dd-knowledge --resume
    python3 auto_generate_dataset.py --skill harnesses/common/skills/dd-knowledge --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Generic SKILL.md entity extraction (no LLM)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_sections(md: str) -> dict[str, str]:
    """Parse SKILL.md into named sections by ## headers."""
    sections: dict[str, str] = {}
    current_title = "_preamble"
    current_lines: list[str] = []

    for line in md.split("\n"):
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            if current_lines:
                sections[current_title] = "\n".join(current_lines).strip()
            current_title = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_title] = "\n".join(current_lines).strip()
    return sections


def _extract_commands_generic(md: str) -> list[dict]:
    """Extract commands from SKILL.md using multiple strategies.

    Returns list of {name, args, category, desc}.
    """
    # Strategy 1: Markdown table with `backtick` commands
    table_commands = _parse_md_table_commands(md)
    if len(table_commands) >= 3:
        return table_commands

    # Strategy 2: Code blocks with executable commands
    code_commands = _parse_code_block_commands(md)
    if len(code_commands) >= 3:
        return code_commands

    # Strategy 3: backtick-enclosed command-like strings
    return _parse_inline_commands(md)


def _parse_md_table_commands(md: str) -> list[dict]:
    """Parse markdown table where first column contains `backtick` commands."""
    commands: list[dict] = []
    current_category = ""
    rows = _extract_table_rows(md)

    for row in rows:
        if not row:
            continue
        first = row[0].strip()
        # Category header like **读** or **写**
        if first.startswith("**") and first.endswith("**"):
            current_category = first.strip("*")
            continue
        # Command line like `kb produce --body ...`
        cmd_match = re.search(r"`([^`]+)`", first)
        if cmd_match:
            commands.append({
                "name": cmd_match.group(1),
                "args": _extract_args_from_cell(row[0]),
                "category": current_category,
                "desc": row[1].strip() if len(row) > 1 else "",
            })
    return commands


def _parse_code_block_commands(md: str) -> list[dict]:
    """Extract commands from ```bash code blocks."""
    commands: list[dict] = []
    in_block = False
    block_lines: list[str] = []
    prev_header = ""

    for line in md.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_block and block_lines:
                for bl in block_lines:
                    bl = bl.strip()
                    if bl and not bl.startswith("#") and not bl.startswith("export "):
                        # git commands, kb commands, etc.
                        name = bl.split(" ")[0] if " " in bl else bl
                        commands.append({
                            "name": name,
                            "args": bl[len(name):].strip(),
                            "category": prev_header,
                            "desc": "",
                        })
                block_lines = []
            in_block = not in_block
            continue
        if in_block:
            block_lines.append(line)
        else:
            m = re.match(r"^#{2,4}\s+(.+)$", stripped)
            if m:
                prev_header = m.group(1).strip()

    return commands


def _parse_inline_commands(md: str) -> list[dict]:
    """Extract backtick-enclosed terms that look like commands."""
    commands: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(r"`([^`]{2,60})`", md):
        term = m.group(1)
        if re.search(r"\s", term) and not term.startswith("$") and term not in seen:
            seen.add(term)
            commands.append({"name": term, "args": "", "category": "", "desc": ""})
    return commands


def _extract_table_rows(md: str) -> list[list[str]]:
    """Extract all rows from all markdown tables."""
    rows: list[list[str]] = []
    for table in re.finditer(r"\|[^\n]+\|\s*\n\|[-\s|]+\|\s*\n((?:\|[^\n]+\|\s*\n)*)", md):
        body = table.group(1)
        for line in body.strip().split("\n"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if cells:
                rows.append(cells)
    return rows


def _extract_args_from_cell(cell: str) -> str:
    """Extract argument portion from a command cell like 'kb produce --body [--ref ...]'."""
    # Remove leading backtick-enclosed command name
    m = re.search(r"`[^`]+`\s*(.*)", cell)
    if m:
        return m.group(1).strip()
    return ""


def _extract_task_types(md: str) -> list[str]:
    """Infer task types from SKILL.md structure.

    Strategies:
    1. Parse routing table (first column of "## 路由" table)
    2. Parse "## 何时使用" bullet list
    3. Use command categories
    """
    sections = _parse_sections(md)

    # Strategy 1: "## 路由" table — first column = task types
    if "路由" in sections:
        types = _extract_routing_task_types(sections["路由"])
        if types:
            return types

    # Strategy 2: "## 何时使用" — distill from bullet points
    for key in ["何时使用", "触发条件"]:
        if key in sections:
            types = _extract_when_task_types(sections[key])
            if types:
                return types

    # Strategy 3: command categories
    commands = _parse_md_table_commands(md)
    if commands:
        cats = sorted(set(c["category"] for c in commands if c["category"]))
        if len(cats) >= 3:
            return cats

    # Fallback: let LLM infer from full document
    return ["default"]


def _extract_routing_task_types(section: str) -> list[str]:
    """Extract task types from a routing table (first column)."""
    types: list[str] = []
    header_keywords = {"场景", "说明", "类型", "操作", "命令", "描述", "备注"}
    for line in section.split("\n"):
        line = line.strip()
        if line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if cells:
                first = cells[0]
                # Clean markdown formatting
                first = re.sub(r"[*`]", "", first).strip()
                # Skip header rows and empty cells
                if not first or first in header_keywords or re.match(r"^[-\s]+$", first):
                    continue
                types.append(first)
    return types


def _extract_when_task_types(section: str) -> list[str]:
    """Distill task types from 'when to use' bullet points."""
    action_map = [
        (r"新建分支|创建分支|checkout.*-b", "create-branch"),
        (r"撰写.*commit|写.*commit|commit.*message", "write-commit"),
        (r"审查.*commit|review.*commit|检查.*commit", "review-commit"),
        (r"推送|git.*push|push", "push"),
        (r"合并|merge", "merge"),
        (r"删除.*分支|删除.*远程|delete.*branch", "delete-branch"),
        (r"修复|bug.*fix|hotfix", "bugfix"),
        (r"部署|deploy", "deploy"),
        (r"发布|release", "release"),
        (r"回滚|rollback|revert", "rollback"),
        (r"检查|校验|核对|验证|validate|check", "validate"),
        (r"生成|generate|创建|produce", "generate"),
        (r"导入|import", "import"),
        (r"导出|export", "export"),
    ]
    keywords: list[str] = []
    # Split into lines and match each bullet
    for line in section.split("\n"):
        stripped = line.strip()
        if not re.match(r"^[-*]\s", stripped):
            continue
        # Remove bullet prefix and bold markers for cleaner matching
        text = re.sub(r"^[-*]\s+", "", stripped)
        text = re.sub(r"\*\*", "", text)
        for pattern, name in action_map:
            if re.search(pattern, text):
                if name not in keywords:
                    keywords.append(name)
    return keywords if keywords else [s.strip("- ")[:30] for s in section.split("\n") if s.strip().startswith("-")][:5]


def _extract_constraints(md: str) -> list[str]:
    """Extract constraints from SKILL.md using multiple strategies."""
    sections = _parse_sections(md)
    constraints: list[str] = []

    # Strategy 1: "关键约束" or "约束" section with numbered list
    for key in ["关键约束", "约束", "规则", "注意事项"]:
        if key in sections:
            body = sections[key]
            for m in re.finditer(r"^\d+\.\s+\*?\*?(.+?)\*?\*?\s*$", body, re.MULTILINE):
                constraints.append(m.group(1).strip())
            if not constraints:
                for m in re.finditer(r"^[-*]\s+(.+?)$", body, re.MULTILINE):
                    c = m.group(1).strip()
                    if _is_constraint(c):
                        constraints.append(c)

    # Strategy 2: "NEVER" section
    if "NEVER" in sections:
        for m in re.finditer(r"^\d+\.\s+(.+?)$", sections["NEVER"], re.MULTILINE):
            constraints.append(m.group(1).strip())

    # Strategy 3: Constraint-heavy subsections
    for key in ["推送限制（强制）", "Commit 信息（强制）", "分支命名（强制）"]:
        if key in sections:
            for m in re.finditer(r"^[-*]\s+(.+?)$", sections[key], re.MULTILINE):
                c = m.group(1).strip()
                if _is_constraint(c):
                    constraints.append(c)

    return constraints


def _is_constraint(text: str) -> bool:
    """Heuristic: is this text a constraint rather than an example/description?"""
    # Contains rule-like keywords
    if re.search(r"必须|禁止|严禁|不可|不能|NEVER|只允许|不得|务必|强制", text):
        return True
    # Too short or looks like an example (starts with backtick or contains slashes like paths)
    if len(text) < 15 or re.match(r"^`[^`]+`$", text):
        return False
    if re.match(r"^[\w./-]+/[\w./-]+", text):  # looks like a path or branch name
        return False
    # Contains actionable rule wording
    if re.search(r"^\*\*[^*]+\*\*", text) and len(text) > 20:
        return True
    return False


def _build_command_summary(commands: list[dict]) -> str:
    """Build a compact command summary for the LLM prompt."""
    if not commands:
        return "(未提取到命令 — 请参考技能文档全文)"

    lines: list[str] = []
    for c in commands:
        name = c["name"]
        args = c.get("args", "")
        desc = c.get("desc", "")
        cat = c.get("category", "")
        full = f"`{name}`" + (f" {args}" if args else "")
        parts = [full]
        if desc:
            parts.append(f"— {desc}")
        if cat:
            parts.append(f"[{cat}]")
        lines.append(" ".join(parts))
    return "\n".join(f"- {l}" for l in lines)


def extract_entities(skill_md: str) -> dict:
    """Extract entity dimensions from any SKILL.md. No LLM, fully generic."""
    commands = _extract_commands_generic(skill_md)
    task_types = _extract_task_types(skill_md)
    constraints = _extract_constraints(skill_md)
    executables = _extract_executables(skill_md)

    return {
        "commands": commands,
        "task_types": task_types,
        "constraints": constraints,
        "executables": executables,
        "command_summary": _build_command_summary(commands),
        "task_type_summary": ", ".join(task_types) if task_types else "(从技能文档推断)",
        "constraint_summary": "\n".join(f"- {c}" for c in constraints) if constraints else "(无显式约束)",
    }


def _extract_executables(skill_md: str) -> set[str]:
    """Extract recognized executable names from SKILL.md.

    Scans both the command table and all code blocks, returning the first
    token of each command line as an executable name. Used to validate that
    expected_output entries are real commands (not prose/annotations).
    """
    execs: set[str] = set()

    # From markdown command table (first column → first word)
    for c in _parse_md_table_commands(skill_md):
        words = c["name"].strip().split()
        if words and _is_likely_executable(words[0]):
            execs.add(words[0])

    # From all code blocks (first non-comment line → first word)
    in_block = False
    for line in skill_md.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        if not in_block or not stripped or stripped.startswith("#"):
            continue
        # Strip shell prompt prefix ($, >)
        stripped = re.sub(r"^[$>]\s*", "", stripped)
        words = stripped.split()
        if not words:
            continue
        # Skip pure variable assignments like FOO=bar
        if "=" in words[0] and len(words) == 1 and not words[0].startswith("="):
            continue
        if _is_likely_executable(words[0]):
            execs.add(words[0])

    return execs


def _is_likely_executable(token: str) -> bool:
    """Heuristic: does this token look like a real executable name?"""
    if len(token) < 2 or len(token) > 40:
        return False
    if not (token[0].isalpha() or token[0] == "_"):
        return False
    if any(c in token for c in "<>{}|\"'`"):
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: Batched LLM case generation
# ═══════════════════════════════════════════════════════════════════════════════

def _build_system_prompt(skill_name: str, skill_md: str, entities: dict) -> str:
    """Build generic system prompt. No skill-specific hardcoding."""
    execs = entities.get("executables") or set()
    exec_hint = (
        f"\n## 合法可执行命令前缀\n\n"
        f"`expected_output` 每行的第一个 token 必须是以下之一：{', '.join(sorted(execs))}\n"
        f"违反此约束的用例会被丢弃。**不要**输出形如 `❌ 禁止...`、`✅ 检查通过`、`执行: ...`、"
        f"`输出: ...` 这类装饰行或自然语言注释。\n"
        if execs else ""
    )
    return f"""你是一个测试用例生成专家。为 Claude Code Skill「{skill_name}」生成多样化的 eval 测试用例。

## 技能文档

{skill_md}

## 提取的命令接口

{entities['command_summary']}

## 可用任务类型

{entities['task_type_summary']}

## 约束规则

{entities['constraint_summary']}
{exec_hint}
## 输出格式

直接输出 JSON 数组（不要用 markdown 代码块包裹），每个元素格式：

{{
  "id": "tasktype-NNN",
  "task_type": "从可用任务类型中选择",
  "question": "自然语言场景描述（2-5句中文，描述用户遇到的具体场景）",
  "expected_output": ["第一行命令", "第二行命令"],
  "ground_truth": "一行解释为什么这是正确的输出"
}}

## 多样性要求

- 均匀覆盖所有可用任务类型
- "任务类型"的粒度不要太细，举例：假如有几个相近的，就用一个大的任务类型来包含即可
- 不同参数组合（flag、参数值）
- 边界情况（缺少必填参数、违反约束、极端值）
- 多步骤的组合场景
- question 用真实中文场景，不要模板化
- expected_output 必须是**可直接执行的命令行**，不要任何前缀符号、emoji 或解释文字
"""


def _build_batch_prompt(batch_size: int, task_types: list[str], batch_info: str = "") -> str:
    """Build user prompt for one batch."""
    coverage = f"覆盖以下任务类型：{', '.join(task_types)}。" if task_types else ""
    info = f"\n{batch_info}\n" if batch_info else ""
    return f"""{info}请生成恰好 {batch_size} 个测试用例。{coverage}直接输出 JSON 数组。"""


def _call_claude(system: str, user: str) -> str:
    """Call claude CLI via stdin pipe. Returns response text."""
    prompt = f"{system}\n\n---\n\n{user}"
    result = subprocess.run(
        ["claude", "-p", "--output-format", "text"],
        input=prompt,
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        print(f"  ⚠ claude CLI error (code={result.returncode}): {result.stderr[:300]}")
    return result.stdout


def _extract_json(text: str) -> list[dict]:
    """Robust JSON extraction from LLM output (handles markdown fences, truncation)."""
    # Try ```json ... ``` fence (greedy — longest match)
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*\])\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Find the outermost JSON array: scan from first '[' to the matching ']'
    start = text.find("[")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break  # truncated — fall through to recovery

    # Recovery: extract individual well-formed objects from a truncated array
    objects: list[dict] = []
    for m in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", text, re.DOTALL):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                objects.append(obj)
        except json.JSONDecodeError:
            continue
    if objects:
        return objects

    # Last resort
    return json.loads(text)


def _validate_item(item: dict, idx: int, executables: set[str] | None = None) -> list[str]:
    """Validate one test item. Returns error list."""
    errors: list[str] = []
    for field in ["id", "task_type", "question", "expected_output", "ground_truth"]:
        if field not in item:
            errors.append(f"item[{idx}]: missing '{field}'")
    if "expected_output" not in item:
        return errors

    out = item["expected_output"]
    if not isinstance(out, list):
        errors.append(f"item[{idx}]: expected_output must be list, got {type(out).__name__}")
        return errors
    if not out:
        errors.append(f"item[{idx}]: expected_output is empty")
        return errors

    # Strict command validation: each line should start with a known executable
    if executables:
        bad: list[str] = []
        for line in out:
            if not isinstance(line, str):
                bad.append(f"non-string: {type(line).__name__}")
                continue
            cleaned = _clean_command_line(line)
            if not cleaned:
                bad.append(f"empty after cleaning: {line[:50]}")
                continue
            first = cleaned.split()[0] if cleaned else ""
            if first not in executables:
                bad.append(f"unknown executable '{first}': {line[:80]}")
        if bad:
            errors.append(
                f"item[{idx}]: expected_output has {len(bad)} non-command line(s): {bad[0]}"
            )
    return errors


def _clean_command_line(line: str) -> str:
    """Strip annotations like '执行:' '输出:' emoji markers, leaving raw command."""
    s = line.strip()
    # Drop wrapping parens like （注释）
    s = re.sub(r"^[（(].*?[)）]\s*", "", s)
    s = re.sub(r"^\s*[❌✅⚠️📌🔥]\s*", "", s)
    # Drop common prefixes "执行: " "运行: " "Run: " "$ " "> "
    s = re.sub(r"^(执行|运行|输出|运行后|结果|预期|实际|示例)[:：]\s*", "", s)
    s = re.sub(r"^[$>]\s*", "", s)
    return s.strip()


def generate_batch(
    skill_name: str,
    skill_md: str,
    entities: dict,
    batch_size: int,
    task_types: list[str],
    batch_info: str = "",
) -> list[dict]:
    """Generate one batch of test cases via LLM. Returns validated items."""
    system = _build_system_prompt(skill_name, skill_md, entities)
    user = _build_batch_prompt(batch_size, task_types, batch_info)
    executables = entities.get("executables") or set()

    for attempt in range(3):
        try:
            print(f"    LLM call (attempt {attempt + 1})...", end=" ", flush=True)
            t0 = time.time()
            response = _call_claude(system, user)
            elapsed = time.time() - t0

            raw = _extract_json(response)
            print(f"{len(raw)} items in {elapsed:.0f}s")

            valid: list[dict] = []
            errors: list[str] = []
            for i, item in enumerate(raw):
                item_errors = _validate_item(item, i, executables=executables)
                if item_errors:
                    errors.extend(item_errors)
                else:
                    # Clean expected_output of any annotation prefixes
                    item["expected_output"] = [
                        _clean_command_line(line) for line in item["expected_output"]
                    ]
                    valid.append(item)

            if errors:
                print(f"      ⚠ {len(errors)} validation warnings (rejected non-command lines)")
                for e in errors[:3]:
                    print(f"        - {e}")

            if valid:
                return valid
            print(f"      Retry: no valid items")
        except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            print(f"fail ({e})")
            time.sleep(5)

    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: Post-processing and split
# ═══════════════════════════════════════════════════════════════════════════════

def deduplicate(items: list[dict]) -> list[dict]:
    """Remove duplicates by question similarity (>80% overlap)."""
    seen: list[str] = []
    result: list[dict] = []
    for item in items:
        q = item.get("question", "")
        # Simple fingerprint: first 50 chars + length
        fp = f"{q[:50]}_{len(q)}"
        # Check if too similar to any seen question
        is_dup = False
        for s in seen:
            if _similarity(fp, s) > 0.8:
                is_dup = True
                break
        if not is_dup:
            seen.append(fp)
            result.append(item)
    return result


def _similarity(a: str, b: str) -> float:
    """Simple Jaccard-like similarity on character bigrams."""
    def bigrams(s: str) -> set[str]:
        return {s[i:i+2] for i in range(len(s)-1)}
    ba = bigrams(a)
    bb = bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / len(ba | bb)


def normalize_items(items: list[dict], prefix: str = "") -> list[dict]:
    """Normalize IDs and ensure consistent field names."""
    task_counts: dict[str, int] = {}
    result: list[dict] = []
    for item in items:
        tt = item.get("task_type", "misc")
        task_counts[tt] = task_counts.get(tt, 0) + 1
        new_id = f"{prefix}{tt}-{task_counts[tt]:03d}"
        result.append({
            "id": new_id,
            "task_type": tt,
            "question": item["question"],
            "expected_commands": item["expected_output"],
            "ground_truth": item["ground_truth"],
        })
    return result


def split_and_save(
    items: list[dict],
    output_dir: Path,
    ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
    seed: int = 42,
) -> dict:
    """Split items into train/val/test and write items.json."""
    rng = random.Random(seed)
    rng.shuffle(items)

    n = len(items)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])

    splits = {
        "train": items[:n_train],
        "val": items[n_train:n_train + n_val],
        "test": items[n_train + n_val:],
    }

    for split_name, split_items in splits.items():
        split_dir = output_dir / split_name
        split_dir.mkdir(parents=True, exist_ok=True)
        path = split_dir / "items.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(split_items, f, ensure_ascii=False, indent=2)
        print(f"  {split_name}: {len(split_items)} items → {path}")

    manifest = {
        "benchmark": output_dir.parent.name,
        "manifest_type": "materialized_split",
        "source": "auto_generate_dataset.py (LLM batched)",
        "counts": {k: len(v) for k, v in splits.items()},
        "ratios": list(ratios),
        "seed": seed,
        "item_fields": ["id", "task_type", "question", "expected_commands", "ground_truth"],
    }
    manifest_path = output_dir / "split_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  manifest → {manifest_path}")
    return manifest


# ═══════════════════════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-generate eval dataset using LLM batched generation (generic, multi-skill)",
    )
    parser.add_argument("--skill", required=True, help="Path to skill directory (relative to repo root)")
    parser.add_argument("--num-items", type=int, default=60, help="Total items to generate (default: 60)")
    parser.add_argument("--batch-size", type=int, default=5, help="Items per LLM call (default: 5)")
    parser.add_argument("--split-ratio", type=str, default="70:15:15", help="Train:val:test ratio (default: 70:15:15)")
    parser.add_argument("--dry-run", action="store_true", help="Preview entities without calling LLM")
    parser.add_argument("--force", action="store_true", help="Overwrite existing dataset")
    parser.add_argument("--resume", action="store_true", help="Append to existing dataset")
    args = parser.parse_args()

    # ── Resolve paths ──────────────────────────────────────────────────────
    skill_dir = (REPO_ROOT / args.skill).resolve()
    if not skill_dir.is_dir():
        print(f"Error: skill directory not found: {skill_dir}")
        sys.exit(1)

    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.is_file():
        print(f"Error: SKILL.md not found in {skill_dir}")
        sys.exit(1)

    skill_md = skill_md_path.read_text(encoding="utf-8")
    skill_name = skill_dir.name
    meta_path = skill_dir / "_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            skill_name = json.load(f).get("name", skill_name)

    # ── Phase 1: Entity extraction ─────────────────────────────────────────
    print(f"Skill: {skill_name}")
    entities = extract_entities(skill_md)
    print(f"  Commands: {len(entities['commands'])} extracted")
    print(f"  Task types: {entities['task_type_summary']}")
    print(f"  Constraints: {len(entities['constraints'])} rules")

    if args.dry_run:
        print(f"\n[dry-run] Generic entity extraction complete.")
        print(f"\n--- Command summary ---")
        print(entities["command_summary"][:1000])
        print(f"\n--- Constraints ---")
        print(entities["constraint_summary"][:800])
        print(f"\n[dry-run] Would generate {args.num_items} items in "
              f"{max(1, args.num_items // args.batch_size)} batches of {args.batch_size}")
        return

    # ── Determine output dir and handle existing data ──────────────────────
    dataset_dir = skill_dir / "eval" / "dataset"
    existing_items: list[dict] = []

    if args.resume:
        train_path = dataset_dir / "train" / "items.json"
        if train_path.exists():
            with open(train_path) as f:
                existing_items = json.load(f)
            print(f"  Resuming: {len(existing_items)} existing items found")
    elif not args.force:
        train_path = dataset_dir / "train" / "items.json"
        if train_path.exists():
            print(f"Error: dataset already exists at {dataset_dir}")
            print("  Use --force to overwrite or --resume to append")
            sys.exit(1)

    # ── Phase 2: Batched LLM generation ────────────────────────────────────
    num_batches = max(1, args.num_items // args.batch_size)
    task_types = entities["task_types"]
    all_items = list(existing_items)

    print(f"\nGenerating ~{args.num_items} items in {num_batches} batches of {args.batch_size}...")

    for batch_idx in range(num_batches):
        # Rotate through task types for even coverage
        ts = task_types[batch_idx % len(task_types):] + task_types[:batch_idx % len(task_types)]

        batch_info = f"第 {batch_idx + 1}/{num_batches} 批"
        print(f"  Batch {batch_idx + 1}/{num_batches} (target task types: {', '.join(ts[:4])}...):")

        batch_items = generate_batch(
            skill_name=skill_name,
            skill_md=skill_md,
            entities=entities,
            batch_size=min(args.batch_size, args.num_items - len(all_items)),
            task_types=ts,
            batch_info=batch_info,
        )

        if batch_items:
            all_items.extend(batch_items)
            print(f"    Total: {len(all_items)} items")
        else:
            print(f"    ⚠ Batch {batch_idx + 1} produced no valid items, retrying...")
            # Retry with different task type rotation
            batch_items = generate_batch(
                skill_name=skill_name,
                skill_md=skill_md,
                entities=entities,
                batch_size=args.batch_size,
                task_types=ts[::-1],
                batch_info=f"重试批次 {batch_idx + 1}",
            )
            if batch_items:
                all_items.extend(batch_items)

        if len(all_items) >= args.num_items:
            break

    if not all_items:
        print("Error: no valid items generated")
        sys.exit(1)

    # ── Phase 3: Post-process ──────────────────────────────────────────────
    print(f"\nPost-processing {len(all_items)} items...")
    all_items = deduplicate(all_items)
    all_items = normalize_items(all_items)
    print(f"  After dedup + normalize: {len(all_items)} items")

    # Task type distribution
    type_counts: dict[str, int] = {}
    for item in all_items:
        tt = item.get("task_type", "unknown")
        type_counts[tt] = type_counts.get(tt, 0) + 1
    print("  Distribution:")
    for tt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {tt}: {count}")

    # ── Phase 4: Split and save ────────────────────────────────────────────
    print(f"\nSaving to {dataset_dir}...")
    ratios = tuple(int(x) / 100 for x in args.split_ratio.split(":"))
    manifest = split_and_save(all_items, dataset_dir, ratios=ratios)

    print(f"\nDone. {len(all_items)} items ({manifest['counts']['train']} train / "
          f"{manifest['counts']['val']} val / {manifest['counts']['test']} test)")
    print(f"Next: python3 .claude/skills/harness-skillopt/scripts/optimize_skill.py --skill {args.skill}")


if __name__ == "__main__":
    main()
