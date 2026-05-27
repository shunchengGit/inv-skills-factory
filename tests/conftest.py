"""共享 fixtures 和辅助函数。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CUSTOM_SKILLS = REPO_ROOT / "custom-skills"

# 已知可用的测试代码
VALID_A_STOCK = "000001"
VALID_HK_STOCK = "0700.HK"
VALID_US_STOCK = "AAPL"


def _find_skill_dir(skill_name: str) -> Path:
    """在 custom-skills/ 下递归查找技能目录（支持 invest/<name> 等嵌套结构）。"""
    for root, dirs, _ in os.walk(CUSTOM_SKILLS):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        root_path = Path(root)
        if root_path.name == skill_name and (root_path / "SKILL.md").exists():
            return root_path
    raise FileNotFoundError(f"技能目录未找到: {skill_name}")


def run_script(skill_name: str, script_name: str, *args, timeout: int = 60, env: dict | None = None) -> subprocess.CompletedProcess:
    """通过 uv run 执行技能脚本，返回 CompletedProcess。"""
    skill_dir = _find_skill_dir(skill_name)
    script_path = skill_dir / "scripts" / script_name
    cmd = ["uv", "run", str(script_path), *args]

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(skill_dir),
        env=run_env,
    )


def parse_json_output(result: subprocess.CompletedProcess) -> dict:
    """从脚本输出中提取 JSON（跳过 stderr）。"""
    stdout = result.stdout.strip()
    if not stdout:
        # 有时 JSON 混在 stderr 中
        combined = result.stderr + result.stdout
        # 找第一个 { 和最后一个 }
        start = combined.find("{")
        end = combined.rfind("}")
        if start >= 0 and end > start:
            return json.loads(combined[start:end + 1])
        raise ValueError("输出中未找到 JSON")
    return json.loads(stdout)


def assert_valid_json_output(data: dict, required_fields: list[str]):
    """校验 JSON 输出包含必需字段。"""
    for field in required_fields:
        assert field in data, f"缺少必需字段: {field}"


@pytest.fixture
def repo_root():
    return REPO_ROOT
