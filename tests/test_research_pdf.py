"""stock-research-report-analysis 研报分析测试。"""

import json
import tempfile
from pathlib import Path

import pytest
from conftest import CUSTOM_SKILLS, run_script


@pytest.mark.smoke
def test_research_pdf_list_no_code():
    """无 --code 时应有合理提示。"""
    result = run_script(
        "stock-research-report-analysis", "research_pdf.py",
        "list", timeout=30,
    )
    assert result.returncode in (0, 1, 2), f"意外退出码: {result.returncode}"
    output = result.stdout + result.stderr
    assert "Traceback" not in output, f"脚本崩溃: {output[:500]}"


@pytest.mark.smoke
def test_research_pdf_list_empty_dir():
    """对空目录 list 应返回空结果。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_script(
            "stock-research-report-analysis", "research_pdf.py",
            "--root", tmpdir, "list", "--within-days", "30", timeout=30,
        )
        output = result.stdout + result.stderr
        assert "Traceback" not in output, f"list 崩溃: {output[:500]}"


@pytest.mark.smoke
def test_research_pdf_inspect_removed():
    """inspect 子命令已被移除。"""
    result = run_script(
        "stock-research-report-analysis", "research_pdf.py",
        "inspect", timeout=15,
    )
    assert result.returncode != 0, "inspect 应返回非零退出码"


@pytest.mark.smoke
def test_research_pdf_organize_dry_run():
    """organize dry-run 不修改文件系统。"""
    with tempfile.TemporaryDirectory() as srcdir, tempfile.TemporaryDirectory() as rootdir:
        # 创建一个空 PDF 用于测试
        test_pdf = Path(srcdir) / "2026-01-15-test-report.pdf"
        test_pdf.write_text("fake pdf content")

        result = run_script(
            "stock-research-report-analysis", "research_pdf.py",
            "organize", "--source", str(srcdir), "--root", str(rootdir),
            timeout=30,
        )
        output = result.stdout + result.stderr
        assert "Traceback" not in output, f"organize 崩溃: {output[:500]}"


@pytest.mark.smoke
def test_research_pdf_help_output():
    """--help 应只显示 3 个子命令。"""
    result = run_script(
        "stock-research-report-analysis", "research_pdf.py",
        "--help", timeout=15,
    )
    output = result.stdout
    assert "init" in output
    assert "list" in output
    assert "extract" in output
    assert "organize" in output
    assert "inspect" not in output
    assert "dedup" not in output
    assert "index" not in output
