#!/usr/bin/env python3
"""Run SkillOpt optimization on a DDHarnessFactory skill.

Usage:
    python scripts/optimize_skill.py --skill harnesses/common/skills/dd-knowledge
    python scripts/optimize_skill.py --skill harnesses/common/skills/dd-knowledge --dry-run
    python scripts/optimize_skill.py --skill harnesses/common/skills/dd-knowledge --cfg-options num_epochs=2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def _load_env() -> None:
    """Load .env from repo root into os.environ (if not already set)."""
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^export\s+([A-Za-z_]\w*)=(.*)$", line)
            if not m:
                continue
            key, val = m.group(1), m.group(2)
            # Don't override existing env vars
            if key not in os.environ:
                os.environ[key] = val


# Auto-load .env on import
_load_env()


def _skillopt_python(skillopt_path: Path) -> str:
    """Return the Python executable to use for SkillOpt scripts.

    Prefers SkillOpt's own .venv (which has all dependencies installed),
    falls back to the current interpreter.
    """
    for candidate in [
        skillopt_path / ".venv" / "bin" / "python",
        skillopt_path / ".venv" / "bin" / "python3",
        skillopt_path / "venv" / "bin" / "python",
        skillopt_path / "venv" / "bin" / "python3",
    ]:
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def run_eval_only(
    args,
    skill_dir: Path,
    skill_name: str,
    skill_md_path: Path,
    dataset_dir: Path,
    eval_dir: Path,
    skillopt_path: Path,
    eval_only_script: Path,
    base_config: Path,
) -> None:
    """Score the current SKILL.md against the dataset via SkillOpt eval_only.py.

    Produces a per-task_type breakdown by post-processing predictions/results.jsonl.
    """
    # Derive model deployment names from env vars
    optimizer_model = os.environ.get("OPTIMIZER_DEPLOYMENT", "")
    target_model = os.environ.get("TARGET_DEPLOYMENT", "")

    # Config defaults from env vars
    reasoning_effort = os.environ.get("SKILLOPT_REASONING_EFFORT", "medium")
    target_backend = os.environ.get("SKILLOPT_TARGET_BACKEND", "openai_chat")
    optimizer_backend = os.environ.get("SKILLOPT_OPTIMIZER_BACKEND", "openai_chat")
    workers = os.environ.get("SKILLOPT_WORKERS", "4")
    max_tokens = os.environ.get("SKILLOPT_MAX_COMPLETION_TOKENS", "4096")

    # Generate minimal config (eval-only doesn't need optimizer params)
    config_lines = [
        f"_base_: {base_config}",
        "",
        "model:",
        f"  reasoning_effort: {reasoning_effort}",
        f"  target_backend: {target_backend}",
        f"  optimizer_backend: {optimizer_backend}",
    ]
    if optimizer_model:
        config_lines.append(f"  optimizer: {optimizer_model}")
    if target_model:
        config_lines.append(f"  target: {target_model}")
    config_lines += [
        "",
        "evaluation:",
        "  test_env_num: 0",
        "",
        "env:",
        f"  name: {skill_name}",
        f"  skill_init: {skill_md_path}",
        "  split_mode: split_dir",
        f"  split_dir: {dataset_dir}",
        "  data_path: ''",
        "  split_output_dir: ''",
        "  max_turns: 1",
        f"  max_completion_tokens: {max_tokens}",
        f"  workers: {workers}",
        "  limit: 0",
    ]
    config_content = "\n".join(config_lines)
    config_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False,
        prefix=f"skillopt_eval_{skill_name}_",
    )
    config_file.write(config_content)
    config_file.close()

    out_root = skillopt_path / "outputs" / f"eval_{skill_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    cmd = [
        _skillopt_python(skillopt_path),
        str(eval_only_script),
        "--config", config_file.name,
        "--skill", str(skill_md_path),
        "--split", args.split,
        "--out_root", str(out_root),
        "--external-env-path", str(eval_dir),
    ]
    if args.cfg_options:
        cmd.extend(["--cfg-options"] + args.cfg_options)

    if args.dry_run:
        print("[dry-run] Eval-only preview:")
        print(f"  Skill:      {skill_md_path}")
        print(f"  Dataset:    {dataset_dir}")
        print(f"  Split:      {args.split}")
        print(f"  Out root:   {out_root}")
        print(f"  Command:    {' '.join(cmd)}")
        print()
        print("--- Config ---")
        print(config_content)
        os.unlink(config_file.name)
        return

    print(f"Running eval-only on {skill_name} (split={args.split})...")
    result = subprocess.run(cmd, cwd=str(skillopt_path))
    os.unlink(config_file.name)

    if result.returncode != 0:
        print(f"Eval-only failed with return code {result.returncode}")
        sys.exit(1)

    # Load summary + per-item results, compute per-task_type breakdown
    summary_path = out_root / "eval_summary.json"
    results_path = out_root / "results.jsonl"

    print(f"\n{'='*60}")
    if summary_path.is_file():
        with open(summary_path) as f:
            summary = json.load(f)
        print(f"  Overall: hard={summary.get('hard', 0):.4f}  soft={summary.get('soft', 0):.4f}  (n={summary.get('n_items', 0)})")

    if results_path.is_file():
        per_type: dict[str, dict[str, float]] = {}
        with open(results_path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tt = r.get("task_type") or "unknown"
                bucket = per_type.setdefault(tt, {"n": 0, "hard": 0.0, "soft": 0.0})
                bucket["n"] += 1
                bucket["hard"] += float(r.get("hard", 0) or 0)
                bucket["soft"] += float(r.get("soft", 0) or 0)
        if per_type:
            print(f"\n  Per task_type:")
            print(f"  {'task_type':<24} {'n':>4} {'hard':>8} {'soft':>8}")
            print(f"  {'-'*24} {'-'*4} {'-'*8} {'-'*8}")
            for tt in sorted(per_type, key=lambda x: -per_type[x]["n"]):
                b = per_type[tt]
                n = b["n"]
                print(f"  {tt:<24} {n:>4} {b['hard']/n:>8.4f} {b['soft']/n:>8.4f}")
    print(f"{'='*60}")
    print(f"Output: {out_root}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SkillOpt optimization on a DDHarnessFactory skill",
    )
    parser.add_argument("--skill", required=True, help="Path to skill directory")
    parser.add_argument(
        "--skillopt-path",
        default="SkillOpt",
        help="Path to SkillOpt directory (default: SkillOpt)",
    )
    parser.add_argument(
        "--cfg-options",
        nargs="+",
        default=[],
        help="Override SkillOpt config: key=value pairs",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Score current SKILL.md against the dataset, no training/optimization",
    )
    parser.add_argument(
        "--split",
        default="test",
        choices=["train", "val", "test", "all"],
        help="Which split to evaluate in --eval-only mode (default: test)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    args = parser.parse_args()

    # ── Resolve and validate paths ──────────────────────────────────────────
    skill_dir = (REPO_ROOT / args.skill).resolve()
    if not skill_dir.is_dir():
        print(f"Error: skill directory not found: {skill_dir}")
        sys.exit(1)

    eval_dir = skill_dir / "eval"
    if not eval_dir.is_dir():
        print(f"Error: skill has no eval/ directory: {eval_dir}")
        sys.exit(1)

    if not (eval_dir / "adapter.py").is_file():
        print(f"Error: no adapter.py in eval/: {eval_dir}")
        sys.exit(1)

    # Read _meta.json
    meta_path = skill_dir / "_meta.json"
    meta: dict = {}
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)

    skill_name = meta.get("name", skill_dir.name)
    skill_md_path = skill_dir / "SKILL.md"
    dataset_dir = eval_dir / "dataset"

    skillopt_path = (REPO_ROOT / args.skillopt_path).resolve()
    train_script = skillopt_path / "scripts" / "train.py"
    eval_only_script = skillopt_path / "scripts" / "eval_only.py"
    base_config = skillopt_path / "configs" / "_base_" / "default.yaml"

    if args.eval_only:
        if not eval_only_script.is_file():
            print(f"Error: SkillOpt eval_only.py not found: {eval_only_script}")
            sys.exit(1)
        run_eval_only(
            args=args,
            skill_dir=skill_dir,
            skill_name=skill_name,
            skill_md_path=skill_md_path,
            dataset_dir=dataset_dir,
            eval_dir=eval_dir,
            skillopt_path=skillopt_path,
            eval_only_script=eval_only_script,
            base_config=base_config,
        )
        return

    if not train_script.is_file():
        print(f"Error: SkillOpt train.py not found: {train_script}")
        sys.exit(1)

    # Derive model deployment names from env vars
    optimizer_model = os.environ.get("OPTIMIZER_DEPLOYMENT", "")
    target_model = os.environ.get("TARGET_DEPLOYMENT", "")

    # Config defaults from env vars
    reasoning_effort = os.environ.get("SKILLOPT_REASONING_EFFORT", "medium")
    target_backend = os.environ.get("SKILLOPT_TARGET_BACKEND", "openai_chat")
    optimizer_backend = os.environ.get("SKILLOPT_OPTIMIZER_BACKEND", "openai_chat")
    workers = os.environ.get("SKILLOPT_WORKERS", "4")
    max_tokens = os.environ.get("SKILLOPT_MAX_COMPLETION_TOKENS", "4096")
    batch_size = os.environ.get("SKILLOPT_BATCH_SIZE", "10")
    learning_rate = os.environ.get("SKILLOPT_LEARNING_RATE", "3")

    # ── Generate config YAML ────────────────────────────────────────────────
    config_lines = [
        f"_base_: {base_config}",
        "",
        "model:",
        f"  reasoning_effort: {reasoning_effort}",
        f"  target_backend: {target_backend}",
        f"  optimizer_backend: {optimizer_backend}",
    ]
    if optimizer_model:
        config_lines.append(f"  optimizer: {optimizer_model}")
    if target_model:
        config_lines.append(f"  target: {target_model}")
    config_lines += [
        "",
        "train:",
        "  train_size: 0",
        f"  batch_size: {batch_size}",
        "",
        "gradient:",
        "  minibatch_size: 5",
        "  merge_batch_size: 5",
        "",
        "optimizer:",
        f"  learning_rate: {learning_rate}",
        "",
        "evaluation:",
        "  sel_env_num: 0",
        "  test_env_num: 0",
        "",
        "env:",
        f"  name: {skill_name}",
        f"  skill_init: {skill_md_path}",
        "  split_mode: split_dir",
        f"  split_dir: {dataset_dir}",
        "  data_path: ''",
        "  split_output_dir: ''",
        "  max_turns: 1",
        f"  max_completion_tokens: {max_tokens}",
        f"  workers: {workers}",
        "  limit: 0",
    ]

    config_content = "\n".join(config_lines)
    config_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        prefix=f"skillopt_{skill_name}_",
    )
    config_file.write(config_content)
    config_file.close()

    # ── Build command ───────────────────────────────────────────────────────
    cmd = [
        _skillopt_python(skillopt_path),
        str(train_script),
        "--config",
        config_file.name,
        "--external-env-path",
        str(eval_dir),
    ]
    if args.cfg_options:
        cmd.extend(["--cfg-options"] + args.cfg_options)

    if args.dry_run:
        print("[dry-run] Skill optimization preview:")
        print(f"  Skill:      {skill_dir}")
        print(f"  Eval dir:   {eval_dir}")
        print(f"  Config:     {config_file.name}")
        print(f"  Output dir: {skillopt_path / 'outputs'}")
        print(f"  Command:    {' '.join(cmd)}")
        print()
        print("--- Config content ---")
        print(config_content)
        return

    # ── Execute SkillOpt training ───────────────────────────────────────────
    print(f"Running SkillOpt optimization for {skill_name}...")
    result = subprocess.run(cmd, cwd=str(skillopt_path))

    if result.returncode != 0:
        print(f"SkillOpt training failed with return code {result.returncode}")
        sys.exit(1)

    # ── Find and apply best_skill.md ────────────────────────────────────────
    outputs_dir = skillopt_path / "outputs"
    output_dirs = sorted(
        [
            d
            for d in outputs_dir.iterdir()
            if d.is_dir() and d.name.startswith(f"skillopt_{skill_name}")
        ],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    best_skill_path: Path | None = None
    latest_output_dir: Path | None = None
    if output_dirs:
        latest_output_dir = output_dirs[0]
        candidate = latest_output_dir / "best_skill.md"
        if candidate.is_file():
            best_skill_path = candidate

    if best_skill_path and best_skill_path.is_file():
        # Direct replacement of SKILL.md
        new_skill = best_skill_path.read_text(encoding="utf-8")
        skill_md_path.write_text(new_skill, encoding="utf-8")
        print(f"Updated {skill_md_path} with optimized skill")

        # Update _meta.json optimization tracking
        meta.setdefault("optimization", {})
        meta["optimization"]["last_run"] = datetime.now(timezone.utc).isoformat()
        meta["optimization"]["run_count"] = meta["optimization"].get("run_count", 0) + 1
        meta["optimization"]["output_dir"] = str(latest_output_dir)

        # Read summary if available
        summary_path = latest_output_dir / "summary.json"
        if summary_path.is_file():
            with open(summary_path) as f:
                summary = json.load(f)
            meta["optimization"]["best_hard"] = summary.get("best_selection_hard")
            meta["optimization"]["best_step"] = summary.get("best_step")

        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Updated {meta_path} with optimization tracking")
    else:
        print("Warning: best_skill.md not found in output directory")
        print(f"  Checked: {outputs_dir}")

    # Cleanup temp config
    os.unlink(config_file.name)


if __name__ == "__main__":
    main()
