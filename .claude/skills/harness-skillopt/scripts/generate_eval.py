#!/usr/bin/env python3
"""Generate eval/ directory scaffold for a DDHarnessFactory skill.

Usage:
    python generate_eval.py --skill harnesses/common/skills/dd-knowledge
    python generate_eval.py --skill harnesses/common/skills/dd-git-workflow --eval-type contains_all
    python generate_eval.py --skill harnesses/common/skills/dd-knowledge --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

EVAL_TYPES = ["command_match", "json_schema", "contains_all", "exact_match"]


# ── Template generators ─────────────────────────────────────────────────────

def _gen_init(skill_name: str) -> str:
    class_name = _to_class_name(skill_name)
    return f'''"""{{skill_name}} skill optimization environment."""
from .adapter import {class_name}Adapter

__all__ = ["{class_name}Adapter"]
'''.replace("{skill_name}", skill_name)


def _gen_reflect() -> str:
    return '"""Reflect stage — delegates to generic minibatch reflect."""\n'


def _gen_dataloader(skill_name: str) -> str:
    class_name = _to_class_name(skill_name)
    return f'''"""{{skill_name}} task dataloader."""
from __future__ import annotations

import json

from skillopt.datasets.base import SplitDataLoader


class {class_name}DataLoader(SplitDataLoader):
    """{class_name} dataloader.

    Each split directory (train/, val/, test/) contains items.json —
    a JSON array of task items.
    """

    def load_raw_items(self, data_path: str) -> list[dict]:
        with open(data_path) as f:
            content = f.read().strip()
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data") or list(data.values())
        return []
'''.replace("{skill_name}", skill_name)


def _gen_evaluator(skill_name: str, eval_type: str) -> str:
    class_name = _to_class_name(skill_name)

    if eval_type == "command_match":
        return f'''"""{{skill_name}} evaluator — strict CLI command matching.

Scoring dimensions (5 points total, em requires >= 4.5):
1. Script path (1pt) — correct script/command present
2. URL exact match (1pt) — URL value matches expected (normalized)
3. Required flags present (1pt) — all expected flags appear
4. No extra flags (0.5pt) — no unexpected flags beyond safe defaults
5. Parameter values exact (1.5pt) — numeric/choice params match expected values
"""
from __future__ import annotations

import re


def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    m = re.match(r"^([A-Za-z]+://)?([^/]+)(.*)", url)
    if m:
        scheme = (m.group(1) or "").lower()
        host = m.group(2).lower()
        path = m.group(3)
        return f"{{scheme}}{{host}}{{path}}"
    return url.lower()


def _extract_url(cmd: str) -> str:
    # Try --url '...' first, then positional URL
    m = re.search(r"--url\\s+['\\\"]?([^'\\\"\\s]+)['\\\"]?", cmd)
    if m:
        return m.group(1)
    m = re.search(r"(https?://[^\\s'\\\"]+)", cmd)
    return m.group(1) if m else ""


def _extract_flags(cmd: str) -> set[str]:
    flags = set()
    for m in re.finditer(r"--([a-zA-Z][\\w-]*)", cmd):
        flags.add(m.group(1))
    return flags


def _extract_flag_value(cmd: str, flag: str) -> str:
    m = re.search(rf"--{{flag}}\\s+['\\\"]?([^'\\\"\\s]+)['\\\"]?", cmd)
    return m.group(1) if m else ""


# Flags that carry a value (not boolean)
_VALUE_FLAGS = {{
    "timeout", "wait-ms", "login-wait-s", "manual-wait-s",
    "storage-state", "save-storage", "wait-until", "format",
    "iframe-selector", "cookie", "cookie-file",
}}

# Flags safe to include even if not expected
_SAFE_EXTRA_FLAGS = {{"url"}}


def evaluate_output(
    predicted: str,
    expected_commands: list[str],
) -> dict:
    """Strictly evaluate predicted command for {{skill_name}}."""
    if not expected_commands:
        return {{"em": 1.0, "f1": 1.0, "predicted_commands": predicted.strip(), "match_count": 0, "expected_count": 0}}

    predicted_lines = [
        line.strip() for line in predicted.split("\\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    predicted_cmd = predicted_lines[0] if predicted_lines else ""
    expected_cmd = expected_commands[0] if expected_commands else ""

    score = 0.0
    max_score = 5.0
    details = {{}}

    # 1. Script path (1pt) — check if expected script/command appears in predicted
    # Extract the script/command part (first meaningful token after python3)
    exp_script = expected_cmd.split()
    script_match = False
    for part in exp_script:
        if part.endswith(".py") or part in ("dws", "kb", "git"):
            if part in predicted_cmd:
                script_match = True
                break
    if not script_match:
        # Fallback: check if predicted contains any .py from expected
        for part in expected_cmd.split():
            if ".py" in part and part in predicted_cmd:
                script_match = True
                break
    if script_match:
        score += 1.0
    details["script_path"] = script_match

    # 2. URL exact match (1pt)
    pred_url = _extract_url(predicted_cmd)
    exp_url = _extract_url(expected_cmd)
    url_match = bool(pred_url) and _normalize_url(pred_url) == _normalize_url(exp_url)
    if url_match:
        score += 1.0
    details["url_match"] = url_match

    # 3. Required flags present (1pt)
    pred_flags = _extract_flags(predicted_cmd)
    exp_flags = _extract_flags(expected_cmd)
    exp_flags.discard("url")
    pred_flags.discard("url")
    missing_flags = exp_flags - pred_flags
    if not missing_flags:
        score += 1.0
    details["flags_present"] = not missing_flags
    details["missing_flags"] = sorted(missing_flags)

    # 4. No extra flags (0.5pt)
    extra_flags = pred_flags - exp_flags - _SAFE_EXTRA_FLAGS
    if not extra_flags:
        score += 0.5
    details["no_extra_flags"] = not extra_flags
    details["extra_flags"] = sorted(extra_flags)

    # 5. Parameter values exact (1.5pt)
    value_score = 0.0
    checked_values = 0
    for flag in exp_flags:
        if flag not in _VALUE_FLAGS:
            continue
        exp_val = _extract_flag_value(expected_cmd, flag)
        if not exp_val:
            continue
        pred_val = _extract_flag_value(predicted_cmd, flag)
        checked_values += 1
        if pred_val == exp_val:
            value_score += 1.0
        elif flag == "wait-until":
            valid_choices = {{"commit", "domcontentloaded", "load", "networkidle"}}
            if pred_val.lower() in valid_choices:
                value_score += 0.3
        elif flag == "format":
            pass  # format mismatch = 0
        elif flag in {{"timeout", "wait-ms", "login-wait-s", "manual-wait-s"}}:
            try:
                ratio = float(pred_val) / float(exp_val)
                if 0.9 <= ratio <= 1.1:
                    value_score += 0.5
            except (ValueError, ZeroDivisionError):
                pass

    if checked_values > 0:
        per_flag = 1.5 / checked_values
        score += value_score * per_flag
    else:
        score += 1.5
    details["value_check"] = {{"checked": checked_values, "correct": int(value_score)}}

    em = 1.0 if score >= 4.5 else 0.0
    f1 = score / max_score

    return {{
        "em": em,
        "f1": f1,
        "predicted_commands": predicted_cmd,
        "match_count": round(score, 2),
        "expected_count": max_score,
        "details": details,
    }}
'''.replace("{{skill_name}}", skill_name)

    elif eval_type == "json_schema":
        return f'''"""{{skill_name}} evaluator — JSON schema matching."""
from __future__ import annotations

import json


def evaluate_output(
    predicted: str,
    expected_fields: dict,
) -> dict:
    """Evaluate predicted JSON output against expected field values.

    expected_fields format: {{"field_name": "expected_value_or_pattern"}}
    Use "*" as value to only check field existence.

    Returns dict with em, f1, and match details.
    """
    try:
        predicted_data = json.loads(predicted)
    except json.JSONDecodeError:
        return {{"em": 0.0, "f1": 0.0, "match_count": 0, "expected_count": len(expected_fields)}}

    if not isinstance(predicted_data, dict):
        predicted_data = {{"value": predicted_data}}

    matched = 0
    for field, expected_val in expected_fields.items():
        actual = predicted_data.get(field)
        if actual is None:
            continue
        if expected_val == "*" or str(actual).lower() == str(expected_val).lower():
            matched += 1

    total = len(expected_fields)
    precision = matched / len(predicted_data) if predicted_data else 0.0
    recall = matched / total if total else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    em = 1.0 if matched == total else 0.0

    return {{
        "em": em,
        "f1": f1,
        "match_count": matched,
        "expected_count": total,
    }}
'''.replace("{skill_name}", skill_name)

    elif eval_type == "contains_all":
        return f'''"""{{skill_name}} evaluator — check output contains all expected points."""
from __future__ import annotations


def evaluate_output(
    predicted: str,
    expected_points: list[str],
) -> dict:
    """Evaluate whether predicted output contains all expected points.

    Returns dict with em, f1, and match details.
    """
    predicted_lower = predicted.lower()
    matched = sum(1 for point in expected_points if point.lower() in predicted_lower)

    total = len(expected_points) if expected_points else 1
    recall = matched / total if total else 1.0
    # Penalize very short outputs that happen to match by luck
    precision = min(matched / max(len(predicted.split()), 1), 1.0) if predicted.strip() else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    em = 1.0 if matched == total else 0.0

    return {{
        "em": em,
        "f1": f1,
        "match_count": matched,
        "expected_count": len(expected_points),
    }}
'''.replace("{skill_name}", skill_name)

    else:  # exact_match
        return f'''"""{{skill_name}} evaluator — exact string matching."""
from __future__ import annotations


def evaluate_output(
    predicted: str,
    expected: str,
) -> dict:
    """Evaluate predicted output against expected exact match."""
    pred = predicted.strip()
    exp = expected.strip()
    em = 1.0 if pred == exp else 0.0
    f1 = em  # No partial credit for exact match

    return {{
        "em": em,
        "f1": f1,
        "match_count": int(em),
        "expected_count": 1,
    }}
'''.replace("{skill_name}", skill_name)


def _gen_adapter(skill_name: str, eval_type: str) -> str:
    class_name = _to_class_name(skill_name)
    task_types = _infer_task_types(skill_name)

    return f'''"""{{skill_name}} environment adapter for ReflACT."""
from __future__ import annotations

import os

from skillopt.datasets.base import BatchSpec
from skillopt.envs.base import EnvAdapter
from skillopt.gradient.reflect import run_minibatch_reflect
from skillopt.prompts import load_prompt

from .dataloader import {class_name}DataLoader
from .rollout import run_batch


class {class_name}Adapter(EnvAdapter):
    """{class_name} environment adapter."""

    def __init__(
        self,
        split_dir: str = "",
        data_path: str = "",
        split_mode: str = "ratio",
        split_ratio: str = "2:1:7",
        split_seed: int = 42,
        split_output_dir: str = "",
        max_turns: int = 1,
        exec_timeout: int = 120,
        workers: int = 8,
        analyst_workers: int = 16,
        failure_only: bool = False,
        minibatch_size: int = 8,
        edit_budget: int = 4,
        seed: int = 42,
        limit: int = 0,
        max_completion_tokens: int = 16384,
        eval_dir: str = "",
    ) -> None:
        self.max_turns = max_turns
        self.exec_timeout = exec_timeout
        self.workers = workers
        self.max_completion_tokens = int(max_completion_tokens)
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        self.eval_dir = eval_dir
        self.dataloader = {class_name}DataLoader(
            split_dir=split_dir,
            data_path=data_path,
            split_mode=split_mode,
            split_ratio=split_ratio,
            split_seed=split_seed,
            split_output_dir=split_output_dir,
            seed=seed,
            limit=limit,
        )

    @property
    def _env_name(self) -> str:
        if self.eval_dir:
            return os.path.basename(os.path.dirname(self.eval_dir))
        return super()._env_name

    def _load_env_prompt(self, name: str) -> str | None:
        if self.eval_dir:
            prompt_path = os.path.join(self.eval_dir, "prompts", f"{{name}}.md")
            if os.path.isfile(prompt_path):
                with open(prompt_path, encoding="utf-8") as f:
                    return f.read()
        return super()._load_env_prompt(name)

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_env_from_batch(self, batch: BatchSpec, **kwargs):
        return list(batch.payload or [])

    def build_train_env(self, batch_size: int, seed: int, **kwargs):
        batch = self.dataloader.build_train_batch(batch_size=batch_size, seed=seed, **kwargs)
        return self.build_env_from_batch(batch, **kwargs)

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs):
        batch = self.dataloader.build_eval_batch(env_num=env_num, split=split, seed=seed, **kwargs)
        return self.build_env_from_batch(batch, **kwargs)

    def rollout(self, env_manager, skill_content: str, out_dir: str, **kwargs) -> list[dict]:
        items: list[dict] = env_manager
        system_prompt_template = self._load_env_prompt("rollout_system")
        if system_prompt_template is None:
            system_prompt_template = load_prompt("rollout_system", env="{skill_name}")
        return run_batch(
            items=items,
            out_root=out_dir,
            skill_content=skill_content,
            system_prompt_template=system_prompt_template,
            max_completion_tokens=self.max_completion_tokens,
            exec_timeout=self.exec_timeout,
            workers=self.workers,
            task_timeout=self.exec_timeout + 60,
        )

    def reflect(self, results: list[dict], skill_content: str, out_dir: str, **kwargs) -> list[dict | None]:
        prediction_dir = kwargs.get("prediction_dir", os.path.join(out_dir, "predictions"))
        patches_dir = kwargs.get("patches_dir", os.path.join(out_dir, "patches"))
        random_seed = kwargs.get("random_seed")
        step_buffer_context = kwargs.get("step_buffer_context", "")
        meta_skill_context = kwargs.get("meta_skill_context", "")

        return run_minibatch_reflect(
            results=results,
            skill_content=skill_content,
            prediction_dir=prediction_dir,
            patches_dir=patches_dir,
            workers=self.analyst_workers,
            failure_only=self.failure_only,
            minibatch_size=self.minibatch_size,
            edit_budget=self.edit_budget,
            random_seed=random_seed,
            error_system=self.get_error_minibatch_prompt(),
            success_system=self.get_success_minibatch_prompt(),
            step_buffer_context=step_buffer_context,
            meta_skill_context=meta_skill_context,
            update_mode=getattr(self, "_cfg", {{}}).get("skill_update_mode", "patch"),
        )

    def get_task_types(self) -> list[str]:
        return {task_types}
'''.replace("{skill_name}", skill_name).replace("{class_name}", class_name).replace("{task_types}", task_types)


def _gen_rollout(skill_name: str, eval_type: str) -> str:
    class_name = _to_class_name(skill_name)

    # Determine the expected field name based on eval type
    if eval_type == "command_match":
        expected_field = "expected_commands"
        expected_type = "list[str]"
        eval_call = "evaluate_commands(response, expected_commands)"
        eval_import = "from .evaluator import evaluate_output as evaluate_commands"
    elif eval_type == "json_schema":
        expected_field = "expected_fields"
        expected_type = "dict"
        eval_call = "evaluate_json(response, expected_fields)"
        eval_import = "from .evaluator import evaluate_output as evaluate_json"
    elif eval_type == "contains_all":
        expected_field = "expected_points"
        expected_type = "list[str]"
        eval_call = "evaluate_contains(response, expected_points)"
        eval_import = "from .evaluator import evaluate_output as evaluate_contains"
    else:  # exact_match
        expected_field = "expected"
        expected_type = "str"
        eval_call = "evaluate_exact(response, expected)"
        eval_import = "from .evaluator import evaluate_output as evaluate_exact"

    return f'''"""{{skill_name}} rollout — single-turn generation + batch execution."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from skillopt.model import chat_target
{eval_import}


# ── Prompt builders ────────────────────────────────────────────────────────

def _build_system(skill_content: str, system_prompt_template: str) -> str:
    if skill_content.strip():
        skill_section = f"## Skill\\n{{skill_content.strip()}}\\n\\n"
    else:
        skill_section = ""
    return system_prompt_template.format(skill_section=skill_section)


def _build_user(question: str, task_type: str = "") -> str:
    parts = [f"## Scenario\\n{{question}}"]
    if task_type:
        parts.append(f"## Task Type\\n{{task_type}}")
    parts.append(
        "## Instructions\\n"
        "Produce the correct output based on the skill instructions above.\\n"
        "Do NOT include explanation — only the requested output."
    )
    return "\\n\\n".join(parts)


# ── Single-item execution ──────────────────────────────────────────────────

def process_one(
    item: dict,
    out_root: str,
    skill_content: str,
    system_prompt_template: str,
    max_completion_tokens: int = 16384,
    exec_timeout: int = 120,
) -> dict:
    """Process a single item: run agent + evaluate."""
    item_id = str(item["id"])
    question = item.get("question", "")
    task_type = item.get("task_type", "")
    {expected_field} = item.get("{expected_field}", {"[]" if eval_type != "json_schema" and eval_type != "exact_match" else '""' if eval_type == "exact_match" else "{{}}"})
    ground_truth = item.get("ground_truth", "")

    result = {{
        "id": item_id,
        "question": question,
        "task_type": task_type,
        "hard": 0,
        "soft": 0.0,
        "predicted_answer": "",
        "fail_reason": "",
        "agent_ok": False,
        "n_turns": 0,
    }}

    try:
        pred_dir = os.path.join(out_root, "predictions", item_id)
        os.makedirs(pred_dir, exist_ok=True)

        system = _build_system(skill_content, system_prompt_template)
        user = _build_user(question, task_type)

        response, _ = chat_target(
            system=system,
            user=user,
            max_completion_tokens=max_completion_tokens,
            retries=3,
            stage="rollout",
            timeout=exec_timeout,
        )

        result["response"] = response
        result["agent_ok"] = True
        result["n_turns"] = 1

        with open(os.path.join(pred_dir, "target_system_prompt.txt"), "w") as f:
            f.write(system)
        with open(os.path.join(pred_dir, "target_user_prompt.txt"), "w") as f:
            f.write(user)

        eval_result = {eval_call}
        result["em"] = eval_result["em"]
        result["f1"] = eval_result["f1"]
        result["hard"] = int(eval_result["em"])
        result["soft"] = eval_result["f1"]
        result["predicted_answer"] = response.strip()

        if eval_result["em"] < 1.0:
            result["fail_reason"] = f"F1={{eval_result['f1']:.2f}}: matched {{eval_result['match_count']}}/{{eval_result['expected_count']}}"

        conversation = [
            {{"type": "message", "turn": 1, "content": response}},
        ]
        eval_detail = (
            f"[EVALUATION RESULT]\\n"
            f"Scenario: {{question[:200]}}\\n"
            f"Ground truth: {{ground_truth}}\\n"
            f"Match: {{eval_result['match_count']}}/{{eval_result['expected_count']}}\\n"
            f"EM: {{eval_result['em']}}\\n"
            f"F1: {{eval_result['f1']:.4f}}"
        )
        conversation.append({{"role": "system", "content": eval_detail}})
        with open(os.path.join(pred_dir, "conversation.json"), "w") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)

    except Exception as e:
        result["fail_reason"] = f"error: {{e}}"

    return result


# ── Batch execution ────────────────────────────────────────────────────────

def run_batch(
    items: list[dict],
    out_root: str,
    skill_content: str,
    system_prompt_template: str,
    max_completion_tokens: int = 16384,
    exec_timeout: int = 120,
    workers: int = 8,
    task_timeout: int = 600,
    **kwargs,
) -> list[dict]:
    """Run agent on all items with ThreadPoolExecutor. Resume-aware."""
    results_path = os.path.join(out_root, "results.jsonl")
    os.makedirs(out_root, exist_ok=True)

    done_ids: set[str] = set()
    existing: list[dict] = []
    if os.path.exists(results_path):
        with open(results_path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done_ids.add(str(r["id"]))
                    existing.append(r)
                except Exception:
                    pass

    pending = [it for it in items if str(it["id"]) not in done_ids]
    if not pending:
        return existing

    total = len(existing) + len(pending)
    completed = len(existing)
    correct_count = sum(1 for r in existing if r.get("hard", 0))
    if existing:
        print(f"    [rollout] resuming: {{completed}}/{{total}} already done", flush=True)

    results = list(existing)

    def _timeout_result(item: dict) -> dict:
        return {{
            "id": str(item["id"]),
            "question": item.get("question", ""),
            "task_type": item.get("task_type") or "{skill_name}",
            "hard": 0, "soft": 0.0, "predicted_answer": "",
            "response": "", "fail_reason": f"task-timeout-{{task_timeout}}s",
            "agent_ok": False, "n_turns": 0,
        }}

    started_at: dict[str, float] = {{}}

    def _run_one(item: dict) -> dict:
        started_at[str(item["id"])] = time.time()
        return process_one(item, out_root, skill_content, system_prompt_template, max_completion_tokens, exec_timeout)

    with open(results_path, "a") as outf:
        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            futs = {{ex.submit(_run_one, it): it for it in pending}}
            pending_futs = set(futs)
            while pending_futs:
                done, _ = wait(pending_futs, timeout=5, return_when=FIRST_COMPLETED)
                now = time.time()
                timed_out = [
                    fut for fut in pending_futs - done
                    if str(futs[fut]["id"]) in started_at
                    and now - started_at[str(futs[fut]["id"])] >= task_timeout
                ]
                for fut in done:
                    pending_futs.remove(fut)
                    item = futs[fut]
                    try:
                        res = fut.result()
                    except Exception as exc:
                        res = _timeout_result(item)
                        res["fail_reason"] = f"unexpected: {{type(exc).__name__}}: {{exc}}"
                    results.append(res)
                    completed += 1
                    if res.get("hard", 0):
                        correct_count += 1
                    acc = correct_count / completed if completed else 0
                    print(f"    [rollout] {{completed}}/{{total}} (acc={{acc:.3f}}) id={{res['id']}} hard={{res.get('hard', '?')}}", flush=True)
                    outf.write(json.dumps(res, ensure_ascii=False) + "\\n")
                    outf.flush()
                for fut in timed_out:
                    pending_futs.remove(fut)
                    fut.cancel()
                    res = _timeout_result(futs[fut])
                    results.append(res)
                    completed += 1
                    acc = correct_count / completed if completed else 0
                    print(f"    [rollout] {{completed}}/{{total}} (acc={{acc:.3f}}) id={{res['id']}} TIMEOUT", flush=True)
                    outf.write(json.dumps(res, ensure_ascii=False) + "\\n")
                    outf.flush()
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

    return results
'''.replace("{skill_name}", skill_name).replace("{class_name}", class_name)


def _gen_rollout_prompt(skill_name: str, skill_md_content: str) -> str:
    """Generate rollout_system.md from SKILL.md content."""
    # Extract the description from frontmatter
    desc_match = re.search(r"^description:\s*(.+)$", skill_md_content, re.MULTILINE)
    description = desc_match.group(1).strip() if desc_match else skill_name

    # Extract command table if present
    lines = skill_md_content.split("\n")
    commands_section = []
    in_table = False
    for line in lines:
        if line.strip().startswith("|") and "---" not in line:
            in_table = True
            commands_section.append(line)
        elif in_table and not line.strip().startswith("|"):
            in_table = False

    commands_text = "\n".join(commands_section) if commands_section else "(See SKILL.md for command reference)"

    return f"""You are an expert agent that follows skill instructions precisely.

{description}

## Command Reference

{commands_text}

{{skill_section}}## Response Format

Produce the correct output based on the scenario. Follow the skill instructions exactly.
Do NOT include explanations — only the requested output.
"""


def _gen_dataset_generator(skill_name: str) -> str:
    class_name = _to_class_name(skill_name)
    return f'''"""Generate training dataset for {{skill_name}} skill optimization.

TODO: Replace placeholder items with real scenarios covering all task types.
Each item must have:
  - id: unique identifier (e.g., "task-001")
  - task_type: one of the task types from adapter.get_task_types()
  - question: natural language scenario description
  - expected_commands / expected_fields / expected_points / expected: ground truth for evaluation
  - ground_truth: human-readable explanation of the correct output
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path


def generate_items() -> list[dict]:
    """Generate all training items."""
    items: list[dict] = []

    # TODO: Add items for each task type. Use "hard-" prefix for trap/difficult items
    # to ensure stratified splitting distributes them across train/val/test.
    # Easy items:
    # items.append({{
    #     "id": "task-001",
    #     "task_type": "example_type",
    #     "question": "Scenario description here",
    #     "expected_commands": ["command --arg value"],
    #     "ground_truth": "Explanation of correct output",
    # }})
    # Hard/trap items (id starts with "hard-"):
    # items.append({{
    #     "id": "hard-001",
    #     "task_type": "example_type",
    #     "question": "Tricky scenario with semantic trap",
    #     "expected_commands": ["command --tricky-flag value"],
    #     "ground_truth": "Trap: X implies Y, not Z",
    # }})

    return items


def split_and_save(
    items: list[dict],
    output_dir: str | Path,
    ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
    seed: int = 42,
) -> None:
    """Stratified split: ensure hard and easy items are distributed across all splits."""
    output_dir = Path(output_dir)
    rng = random.Random(seed)

    hard_items = [it for it in items if it["id"].startswith("hard-")]
    easy_items = [it for it in items if not it["id"].startswith("hard-")]

    rng.shuffle(hard_items)
    rng.shuffle(easy_items)

    def _split_list(lst, ratios):
        n = len(lst)
        n_train = int(n * ratios[0])
        n_val = int(n * ratios[1])
        return lst[:n_train], lst[n_train:n_train + n_val], lst[n_train + n_val:]

    hard_splits = _split_list(hard_items, ratios)
    easy_splits = _split_list(easy_items, ratios)

    splits = {{
        "train": hard_splits[0] + easy_splits[0],
        "val": hard_splits[1] + easy_splits[1],
        "test": hard_splits[2] + easy_splits[2],
    }}

    for split_name, split_items in splits.items():
        split_dir = output_dir / split_name
        split_dir.mkdir(parents=True, exist_ok=True)
        with open(split_dir / "items.json", "w", encoding="utf-8") as f:
            json.dump(split_items, f, ensure_ascii=False, indent=2)
        print(f"  {{split_name}}: {{len(split_items)}} items")

    n = len(items)
    manifest = {{
        "name": "{class_name}",
        "total": n,
        "splits": {{k: len(v) for k, v in splits.items()}},
        "ratios": list(ratios),
        "seed": seed,
    }}
    with open(output_dir / "split_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    items = generate_items()
    print(f"Generated {{len(items)}} items")
    script_dir = Path(__file__).resolve().parent
    split_and_save(items, script_dir)
'''.replace("{skill_name}", skill_name).replace("{class_name}", class_name)


def _gen_split_manifest(skill_name: str) -> str:
    class_name = _to_class_name(skill_name)
    return json.dumps({
        "name": class_name,
        "total": 0,
        "splits": {"train": 0, "val": 0, "test": 0},
        "ratios": [0.70, 0.15, 0.15],
        "seed": 42,
    }, indent=2)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _to_class_name(skill_name: str) -> str:
    """Convert skill name (dd-knowledge) to class prefix (DDKnowledge)."""
    parts = skill_name.split("-")
    return "".join(p.capitalize() for p in parts)


def _infer_task_types(skill_name: str) -> str:
    """Return a default task types list as a Python list literal string."""
    return '["default"]'


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate eval/ directory scaffold for a skill",
    )
    parser.add_argument("--skill", required=True, help="Path to skill directory (relative to repo root)")
    parser.add_argument(
        "--eval-type",
        choices=EVAL_TYPES,
        default="command_match",
        help="Evaluator template type (default: command_match)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing eval/ directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    skill_dir = (REPO_ROOT / args.skill).resolve()
    if not skill_dir.is_dir():
        print(f"Error: skill directory not found: {skill_dir}")
        sys.exit(1)

    # Read skill metadata
    meta_path = skill_dir / "_meta.json"
    skill_name = skill_dir.name
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        skill_name = meta.get("name", skill_name)

    eval_dir = skill_dir / "eval"

    if eval_dir.exists() and not args.force:
        print(f"Error: eval/ already exists: {eval_dir}")
        print("  Use --force to overwrite")
        sys.exit(1)

    # Read SKILL.md for prompt generation
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_content = ""
    if skill_md_path.exists():
        skill_md_content = skill_md_path.read_text(encoding="utf-8")

    # Define files to generate
    files: dict[str, str] = {
        "__init__.py": _gen_init(skill_name),
        "adapter.py": _gen_adapter(skill_name, args.eval_type),
        "dataloader.py": _gen_dataloader(skill_name),
        "rollout.py": _gen_rollout(skill_name, args.eval_type),
        "evaluator.py": _gen_evaluator(skill_name, args.eval_type),
        "reflect.py": _gen_reflect(),
        "prompts/rollout_system.md": _gen_rollout_prompt(skill_name, skill_md_content),
        "dataset/generate_training_data.py": _gen_dataset_generator(skill_name),
        "dataset/split_manifest.json": _gen_split_manifest(skill_name),
        "dataset/train/items.json": "[]",
        "dataset/val/items.json": "[]",
        "dataset/test/items.json": "[]",
    }

    if skill_md_path.exists():
        files["skills/initial.md"] = skill_md_content

    if args.dry_run:
        print(f"[dry-run] Would generate eval/ for {skill_name}:")
        print(f"  Skill dir:  {skill_dir}")
        print(f"  Eval dir:   {eval_dir}")
        print(f"  Eval type:  {args.eval_type}")
        print(f"  Files:")
        for path in sorted(files.keys()):
            print(f"    {path}")
        return

    # Create directories
    if eval_dir.exists() and args.force:
        shutil.rmtree(eval_dir)

    for subdir in ["prompts", "skills", "dataset/train", "dataset/val", "dataset/test"]:
        (eval_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Write files
    for rel_path, content in files.items():
        file_path = eval_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        print(f"  Created: eval/{rel_path}")

    # Update _meta.json optimization field
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        if "optimization" not in meta:
            meta["optimization"] = {"enabled": True}
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"  Updated: _meta.json (added optimization field)")

    print(f"\nDone. Next steps:")
    print(f"  1. Edit eval/evaluator.py to customize evaluation logic")
    print(f"  2. Edit eval/dataset/generate_training_data.py to add training items")
    print(f"  3. Run: python eval/dataset/generate_training_data.py")
    print(f"  4. Run: python scripts/optimize_skill.py --skill {args.skill}")


if __name__ == "__main__":
    main()
