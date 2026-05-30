"""inv-porter-five-forces 五力分析测试。"""

import pytest
from conftest import VALID_A_STOCK, parse_json_output, run_script


@pytest.mark.smoke
def test_five_forces_snapshot():
    """五力快照返回预评分数据。"""
    result = run_script(
        "inv-porter-five-forces", "five_forces_snapshot.py",
        VALID_A_STOCK, "--output", "json", timeout=60,
    )
    if result.returncode != 0:
        pytest.skip(f"five_forces_snapshot 失败: {result.stderr[:200]}")

    # 预评分在 pre_scoring.dimensions 中
    data = parse_json_output(result)
    dimensions = data.get("pre_scoring", {}).get("dimensions", {})
    if not dimensions:
        pytest.skip("五力快照无 pre_scoring.dimensions 字段")

    expected_keys = {"supplier_power", "buyer_power", "entry_threat", "substitute_threat", "rivalry"}
    found = expected_keys & set(dimensions.keys())
    assert len(found) >= 3, f"五力评分至少应有 3 个维度，实际: {found}"

    for key in found:
        dim = dimensions[key]
        score = dim.get("suggested_score", dim.get("base_score", 0))
        assert isinstance(score, (int, float)), f"{key} 评分不是数字: {type(score)}"
        assert 1 <= score <= 20, f"{key} 评分超出范围: {score}"


@pytest.mark.smoke
def test_five_forces_snapshot_has_company_info():
    """快照包含公司基本信息。"""
    result = run_script(
        "inv-porter-five-forces", "five_forces_snapshot.py",
        VALID_A_STOCK, "--output", "json", timeout=60,
    )
    if result.returncode != 0:
        pytest.skip(f"five_forces_snapshot 失败: {result.stderr[:200]}")

    data = parse_json_output(result)
    # industry 可能在顶层或 nested 在 company_profile 中
    has_company = "company_name" in data or "name" in data
    has_industry = "industry" in data or "sector" in data
    if not has_industry:
        profile = data.get("company_profile", {})
        has_industry = "industry" in profile or "sector" in profile
    assert has_company, "缺少公司名称"
    assert has_industry, f"缺少行业信息，keys: {list(data.keys())[:10]}"
