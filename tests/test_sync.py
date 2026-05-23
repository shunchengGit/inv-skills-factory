"""sync_skills.py 测试。"""

import json
import tempfile
from pathlib import Path

import pytest
from conftest import REPO_ROOT, run_script


def _run_sync(*args, timeout: int = 10):
    """在仓库根目录运行 sync_skills.py。"""
    import subprocess
    import os

    script = str(REPO_ROOT / "scripts" / "sync_skills.py")
    result = subprocess.run(
        ["python3", script, *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    return result


def test_sync_dry_run():
    """dry-run 不修改文件系统。"""
    result = _run_sync("--dry-run", timeout=30)
    assert result.returncode == 0, f"dry-run 失败: {result.stderr[:200]}"
    output = result.stdout
    assert "DRY RUN" in output or "预览" in output or "总计" in output, \
        f"输出缺少 dry-run 标识: {output[:300]}"


def test_sync_with_custom_config():
    """自定义配置文件应被正确读取。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_sub = Path(tmpdir) / "skills"
        skills_sub.mkdir()
        config_path = Path(tmpdir) / "custom_config.json"
        config_path.write_text(json.dumps({
            "agents": [{"name": "test-agent", "skills_dir": str(skills_sub), "enabled": True}]
        }))

        result = _run_sync("--config", str(config_path), "--dry-run", timeout=15)
        assert result.returncode == 0, f"自定义配置失败: {result.stderr[:200]}"
        assert "test-agent" in result.stdout, f"输出未包含 test-agent: {result.stdout[:300]}"


def test_sync_invalid_config():
    """无效配置文件应报错退出。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "invalid.json"
        config_path.write_text("{invalid json")

        result = _run_sync("--config", str(config_path), timeout=15)
        assert result.returncode != 0, "无效 JSON 应返回非零退出码"


def test_sync_missing_config():
    """不存在的配置文件应报错。"""
    result = _run_sync("--config", "/nonexistent/path/config.json", timeout=10)
    assert result.returncode != 0, "不存在的配置应返回非零退出码"
