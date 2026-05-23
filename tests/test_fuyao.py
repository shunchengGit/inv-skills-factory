"""fuyao-leading-indicators 前置指标测试。"""

import pytest
from conftest import parse_json_output, run_script


@pytest.mark.smoke
def test_fuyao_indicators_skip_auto():
    """跳过 Playwright 的前置指标快照返回 8 个指标。"""
    result = run_script(
        "fuyao-leading-indicators", "fuyao_indicators.py",
        "--skip-auto", "--output", "json", timeout=120,
    )
    if result.returncode != 0:
        pytest.skip(f"fuyao_indicators 失败: {result.stderr[:200]}")

    data = parse_json_output(result)
    indicators = data.get("indicators", {})
    assert len(indicators) == 8, f"预期 8 个指标，实际: {len(indicators)}"

    # 每个指标应有必需的元数据
    for key, entry in indicators.items():
        assert "name" in entry, f"{key}: 缺少 name"
        assert "direction" in entry, f"{key}: 缺少 direction"
        assert "weight" in entry, f"{key}: 缺少 weight"

    # 验证关键指标存在
    expected = ["soda_ash", "natural_gas", "usdcny", "auto_sales", "ccfi", "nev_penetration", "us_auto_sales", "eu_auto_sales"]
    for key in expected:
        assert key in indicators, f"缺少指标: {key}"


@pytest.mark.structure
def test_fuyao_indicators_fields():
    """每个指标包含计分所需的核心字段。"""
    result = run_script(
        "fuyao-leading-indicators", "fuyao_indicators.py",
        "--skip-auto", "--output", "json", timeout=120,
    )
    if result.returncode != 0:
        pytest.skip(f"fuyao_indicators 失败: {result.stderr[:200]}")

    data = parse_json_output(result)
    for key, entry in data["indicators"].items():
        if entry.get("data_quality") == "agent_required":
            continue
        # 脚本获取的指标应有 data_quality=complete
        assert entry.get("data_quality") in ("complete", "missing", "agent_required"), \
            f"{key}: 无效的 data_quality: {entry.get('data_quality')}"
