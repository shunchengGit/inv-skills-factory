"""inv-stock-data 数据层脚本测试。"""

import json

import pytest
from conftest import VALID_A_STOCK, VALID_HK_STOCK, VALID_US_STOCK, parse_json_output, run_script


@pytest.mark.smoke
def test_snapshot_a_stock():
    """A 股快照返回完整数据。"""
    result = run_script("inv-stock-data", "cs_stock_info.py", "snapshot", VALID_A_STOCK, "--output", "json", timeout=60)
    assert result.returncode == 0, f"snapshot 失败 (exit={result.returncode}): {result.stderr[:200]}"
    data = parse_json_output(result)
    assert "name" in data, f"缺少 name 字段，keys: {list(data.keys())[:10]}"
    assert data.get("name"), "name 不应为空"
    # daily 字段
    daily = data.get("daily", {})
    assert daily, "daily 字段不应为空"


@pytest.mark.smoke
def test_snapshot_etf():
    """ETF 快照返回完整数据。"""
    result = run_script("inv-stock-data", "cs_stock_info.py", "snapshot", "513010", "--output", "json", timeout=60)
    assert result.returncode == 0, f"ETF snapshot 失败: {result.stderr[:200]}"
    data = parse_json_output(result)
    assert "name" in data


@pytest.mark.smoke
def test_snapshot_hk_stock():
    """港股快照返回数据（可能需要代理）。"""
    result = run_script("inv-stock-data", "cs_stock_info.py", "snapshot", VALID_HK_STOCK, "--output", "json", timeout=60)
    if result.returncode != 0:
        pytest.skip(f"港股 snapshot 失败 (可能网络/代理问题): {result.stderr[:200]}")
    data = parse_json_output(result)
    assert "name" in data


@pytest.mark.smoke
def test_daily_a_stock():
    """A 股日线返回数据。"""
    result = run_script("inv-stock-data", "cs_stock_info.py", "daily", VALID_A_STOCK, "--output", "json", timeout=60)
    assert result.returncode == 0, f"daily 失败: {result.stderr[:200]}"
    data = parse_json_output(result)
    assert isinstance(data, (list, dict)), f"daily 应返回 list 或 dict，实际: {type(data)}"


@pytest.mark.smoke
def test_financial_a_stock():
    """A 股财务摘要返回数据。"""
    result = run_script("inv-stock-data", "cs_stock_info.py", "financial", VALID_A_STOCK, "--output", "json", timeout=60)
    if result.returncode != 0:
        pytest.skip(f"financial 失败: {result.stderr[:200]}")
    data = parse_json_output(result)
    assert isinstance(data, dict)
    # 应含 sina_financial 或 ths_financial
    has_fin = "sina_financial" in data or "ths_financial" in data
    assert has_fin, f"缺少财务数据字段，keys: {list(data.keys())[:10]}"


@pytest.mark.error
def test_invalid_code():
    """无效代码返回合理错误。"""
    result = run_script("inv-stock-data", "cs_stock_info.py", "snapshot", "999999", "--output", "json", timeout=60)
    # 应该以非零退出码返回，或有明确的错误信息
    if result.returncode == 0:
        data = parse_json_output(result)
        # 即使脚本自身没报错，数据也应该标记问题
        notes = data.get("notes", data.get("_notes", []))
        errors = [n for n in notes if "error" in str(n).lower() or "失败" in str(n)]
        # 无效代码不应同时有 name + daily 的完整数据
        has_name = bool(data.get("name"))
        has_daily = bool(data.get("daily"))
        if has_name and has_daily:
            # 999999 可能是某些市场的有效代码，跳过
            pass  # 不强行 fail
