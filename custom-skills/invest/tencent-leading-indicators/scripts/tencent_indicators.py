#!/usr/bin/env python3
"""腾讯控股前置指标快照生成器。

用法:
  python tencent_indicators.py              # JSON 数据快照
  python tencent_indicators.py --output text  # 文本摘要
"""

import argparse
import json
import sys
from pathlib import Path

# ── 引入共享框架 ─────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from indicators.builder import build_snapshot, render_text_snapshot, fetch_all_concurrent

from indicators_config import INDICATORS
from game_ranking_fetch import fetch_game_rankings
from southbound_flow_fetch import fetch_southbound_flow


def _fetch_macro_retail_sales():
    """从东方财富宏观数据中心获取社零增速。"""
    import requests

    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "columns": "REPORT_DATE,TIME,RETAIL_TOTAL,RETAIL_TOTAL_SAME,RETAIL_TOTAL_SEQUENTIAL,"
                   "RETAIL_TOTAL_ACCUMULATE,RETAIL_ACCUMULATE_SAME",
        "pageNumber": "1",
        "pageSize": "12",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": "RPT_ECONOMY_TOTAL_RETAIL",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") and data["result"].get("data"):
            return data["result"]["data"]
    except Exception:
        pass
    return []


def _register_fetchers() -> dict:
    """注册所有脚本可获取的指标 fetcher。"""
    return {
        "retail_sales": _fetch_macro_retail_sales,
        "top_games_ranking": fetch_game_rankings,
        "southbound_flow": fetch_southbound_flow,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="腾讯前置指标数据快照")
    parser.add_argument("--output", choices=["json", "text"], default="json")
    args = parser.parse_args()

    # 注册 fetcher 并并发获取
    fetchers = _register_fetchers()
    results, errors = fetch_all_concurrent(fetchers, max_workers=3)

    # 构建快照
    snapshot = build_snapshot(INDICATORS, fetch_results=results, fetch_errors=errors)

    # 输出
    if args.output == "json":
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_text_snapshot(snapshot))

    return 0


if __name__ == "__main__":
    sys.exit(main())