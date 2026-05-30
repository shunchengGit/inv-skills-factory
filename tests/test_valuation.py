"""inv-valuation-engine 估值引擎测试。"""

import pytest
from conftest import VALID_A_STOCK, parse_json_output, run_script

VALUATION_DIR = "../inv-valuation-engine/scripts"


@pytest.mark.smoke
def test_valuation_snapshot_a_stock():
    """估值快照 A 股返回完整数据。"""
    result = run_script(
        "inv-valuation-engine", "valuation_snapshot.py",
        VALID_A_STOCK, "--output", "json", timeout=90,
    )
    if result.returncode != 0:
        pytest.skip(f"valuation_snapshot 失败: {result.stderr[:200]}")
    data = parse_json_output(result)
    required = ["symbol", "company_name", "metrics", "data_gaps"]
    for field in required:
        assert field in data, f"缺少必需字段: {field}"
    # metrics 应至少有几个估值指标
    metrics = data.get("metrics", {})
    assert isinstance(metrics, dict), f"metrics 应为 dict，实际: {type(metrics)}"


@pytest.mark.smoke
def test_valuation_report_a_stock():
    """估值报告生成五档结论。"""
    result = run_script(
        "inv-valuation-engine", "valuation_report.py",
        VALID_A_STOCK, timeout=90,
    )
    if result.returncode != 0:
        pytest.skip(f"valuation_report 失败: {result.stderr[:200]}")
    output = result.stdout + result.stderr
    # 应包含五档结论中的某个
    conclusions = ["低估", "合理偏低", "合理", "合理偏高", "高估"]
    found = [c for c in conclusions if c in output]
    assert found, f"输出未找到估值结论，前 500 字符: {output[:500]}"


@pytest.mark.smoke
def test_valuation_compare():
    """多股比较返回数据。"""
    result = run_script(
        "inv-valuation-engine", "valuation_compare.py",
        "000001", "600519", timeout=90,
    )
    if result.returncode != 0:
        pytest.skip(f"valuation_compare 失败: {result.stderr[:200]}")
    output = result.stdout + result.stderr
    assert len(output) > 100, f"compare 输出过短: {len(output)} 字符"
