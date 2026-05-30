#!/usr/bin/env python3
"""福耀玻璃前置指标快照生成器。

用法:
  python fuyao_indicators.py --output json|text [--skip-auto] [--raw-cpca]
"""

import argparse
import json
import sys
from pathlib import Path

# ── 引入共享框架 ─────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from indicators.builder import build_snapshot, render_text_snapshot, fetch_all_concurrent

from indicators_config import INDICATORS
from eastmoney_fetch import fetch_cpca_retail
from auto_sales_fetch import fetch_auto_sales
from global_auto_fetch import fetch_us_auto_sales


def _register_fetchers(skip_auto: bool = False) -> dict:
    """注册所有脚本可获取的指标 fetcher。"""
    fetchers = {}

    if not skip_auto:
        fetchers["auto_sales"] = fetch_auto_sales

    fetchers["us_auto_sales"] = fetch_us_auto_sales

    # CPCA 零售（eastmoney 抓取，可能返回 partial）
    fetchers["cpca_retail"] = fetch_cpca_retail

    return fetchers


def main():
    parser = argparse.ArgumentParser(description="福耀玻璃前置指标快照")
    parser.add_argument("--output", choices=["json", "text"], default="json",
                        help="输出格式（默认 json）")
    parser.add_argument("--skip-auto", action="store_true",
                        help="跳过汽车销量自动获取（使用 agent 搜索）")
    parser.add_argument("--raw-cpca", action="store_true",
                        help="CPCA 数据仅返回原始文本（不自动解析）")
    args = parser.parse_args()

    # 注册 fetcher 并并发获取
    fetchers = _register_fetchers(skip_auto=args.skip_auto)
    results, errors = fetch_all_concurrent(fetchers, max_workers=3)

    # 如果 --raw-cpca，修改 cpca_retail 结果
    if args.raw_cpca and "cpca_retail" in results:
        r = results["cpca_retail"]
        if r.get("data_quality") == "complete" and "raw_text" not in r:
            r["raw_text"] = r.get("parsed_text", "")

    # 构建快照
    snapshot = build_snapshot(INDICATORS, fetch_results=results, fetch_errors=errors)

    # 输出
    if args.output == "json":
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print(render_text_snapshot(snapshot))


if __name__ == "__main__":
    main()
