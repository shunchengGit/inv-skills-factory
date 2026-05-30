#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "akshare>=1.14.0",
#   "yfinance>=0.2.31",
#   "pandas>=2.0.0",
#   "requests>=2.28.0",
# ]
# ///
"""个股信息查询工具 — 支持 A 股 / ETF / 港股 / 美股。

用法:
  uv run cs_stock_info.py snapshot  600519
  uv run cs_stock_info.py daily     600519
  uv run cs_stock_info.py profile   600519
  uv run cs_stock_info.py financial 600519
  uv run cs_stock_info.py description 600519
  uv run cs_stock_info.py announcements 600519
  uv run cs_stock_info.py relations  600519
  uv run cs_stock_info.py snapshot  510300    # ETF
  uv run cs_stock_info.py snapshot  00700     # 港股
  uv run cs_stock_info.py snapshot  AAPL      # 美股
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ── 代理管理（共享模块）──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from proxy import setup_proxy_env, clear_proxy_env, restore_proxy_env

# ── 同级模块导入 ────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from market import parse_symbol
from render import print_text
from commands import (
    cmd_snapshot_a, cmd_snapshot_etf, cmd_snapshot_yahoo,
    cmd_daily, cmd_profile, cmd_financial, cmd_financials,
    cmd_description, cmd_announcements, cmd_index_daily, cmd_relations,
    cmd_all,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="个股信息查询工具")
    parser.add_argument("command", choices=[
        "snapshot", "daily", "index-daily", "profile", "financial", "financials",
        "all", "description", "announcements", "relations",
    ])
    parser.add_argument("symbol", help="股票代码")
    parser.add_argument("--output", choices=["json", "text"], default="json")
    parser.add_argument("--proxy", default=None,
                        help="手动指定代理地址，如 http://127.0.0.1:7890（覆盖自动检测）")
    args = parser.parse_args()

    code, market = parse_symbol(args.symbol)

    # ── 代理策略：美港股确保代理，A 股/ETF 清除代理 ──
    needs_yahoo = market in ("hk", "us")
    proxy_ok = True
    if needs_yahoo:
        proxy_ok = setup_proxy_env(override=args.proxy)
    else:
        clear_proxy_env()

    # 将代理状态注入最后的 payload，供 agent 感知
    def _inject_proxy_note(payload: dict) -> dict:
        if not isinstance(payload, dict):
            return payload
        notes = payload.get("notes") or payload.get("_notes") or []
        if isinstance(notes, str):
            notes = [notes] if notes else []
        if needs_yahoo and not proxy_ok:
            notes.insert(0, "[代理缺失] 未检测到代理，Yahoo Finance 请求大概率限流。请设置 HTTPS_PROXY 后重试")
        elif needs_yahoo and proxy_ok:
            has_data = bool(
                payload.get("price") or
                (isinstance(payload.get("fundamentals"), dict) and any(payload["fundamentals"].values())) or
                (isinstance(payload.get("daily"), list) and len(payload.get("daily", [])) > 0)
            )
            if not has_data:
                notes.append("[代理已设但Yahoo为空] HTTPS_PROXY 已设置但请求仍返回空数据。可能原因：代理节点被限流/Clash 未开系统代理/Yahoo 全局限流。尝试切换节点或等待数分钟后重试")
        payload["_proxy_ok"] = proxy_ok
        if notes:
            payload["_notes"] = notes
        return payload

    try:
        if args.command == "snapshot":
            if market == "a":
                payload = cmd_snapshot_a(code)
            elif market == "etf":
                payload = cmd_snapshot_etf(code)
            else:
                payload = cmd_snapshot_yahoo(code, market)
        elif args.command == "daily":
            payload = cmd_daily(code, market)
        elif args.command == "index-daily":
            payload = cmd_index_daily(args.symbol)
        elif args.command == "profile":
            payload = cmd_profile(code, market)
        elif args.command == "financial":
            payload = cmd_financial(code, market)
        elif args.command == "financials":
            payload = cmd_financials(code, market)
        elif args.command == "all":
            payload = cmd_all(code, market)
        elif args.command == "description":
            payload = cmd_description(code)
        elif args.command == "announcements":
            payload = cmd_announcements(code)
        elif args.command == "relations":
            payload = cmd_relations(code)
        else:
            payload = {"error": f"未知命令: {args.command}"}
    finally:
        if not needs_yahoo:
            restore_proxy_env()

    payload = _inject_proxy_note(payload)
    if args.output == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(print_text(payload))

    return 0


if __name__ == "__main__":
    sys.exit(main())