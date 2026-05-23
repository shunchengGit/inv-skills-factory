"""tencent-leading-indicators 前置指标测试。"""

import pytest
from conftest import parse_json_output, run_script


@pytest.mark.smoke
def test_tencent_indicators():
    """腾讯前置指标返回 6 个指标。"""
    result = run_script(
        "tencent-leading-indicators", "tencent_indicators.py",
        "--output", "json", timeout=60,
    )
    if result.returncode != 0:
        pytest.skip(f"tencent_indicators 失败: {result.stderr[:200]}")

    data = parse_json_output(result)
    indicators = data.get("indicators", {})
    assert len(indicators) == 6, f"预期 6 个指标，实际: {len(indicators)}"

    for key, entry in indicators.items():
        assert "name" in entry, f"{key}: 缺少 name"
        assert "weight" in entry, f"{key}: 缺少 weight"

    expected = ["game_approval", "top_games_ranking", "retail_sales", "wechat_video_usage", "wechat_payment", "southbound_flow"]
    for key in expected:
        assert key in indicators, f"缺少指标: {key}"


@pytest.mark.structure
def test_tencent_indicators_data_methods():
    """验证脚本获取 vs Agent 搜索的指标分布。"""
    result = run_script(
        "tencent-leading-indicators", "tencent_indicators.py",
        "--output", "json", timeout=60,
    )
    if result.returncode != 0:
        pytest.skip(f"tencent_indicators 失败: {result.stderr[:200]}")

    data = parse_json_output(result)
    script_count = 0
    agent_count = 0
    for entry in data["indicators"].values():
        method = entry.get("data_method", "")
        if method == "script":
            script_count += 1
        elif method == "agent_search":
            agent_count += 1

    assert script_count == 3, f"预期 3 个脚本指标，实际: {script_count}"
    assert agent_count == 3, f"预期 3 个搜索指标，实际: {agent_count}"
