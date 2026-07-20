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
from proxy import setup_proxy_env

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


def execute_command(
    command: str,
    symbol: str,
    *,
    proxy: str | None = None,
    period: str = "1y",
    limit: int | None = None,
) -> dict:
    """执行命令并返回 investment-data-contracts v1 envelope。"""
    code, market = parse_symbol(symbol)

    needs_yahoo = market in ("hk", "us")
    proxy_ok = True
    if needs_yahoo:
        proxy_ok = setup_proxy_env(override=proxy)

    try:
        if command == "snapshot":
            if market == "a":
                payload = cmd_snapshot_a(code, raw_symbol=symbol)
            elif market == "etf":
                payload = cmd_snapshot_etf(code, raw_symbol=symbol)
            else:
                payload = cmd_snapshot_yahoo(code, market, raw_symbol=symbol)
        elif command == "daily":
            payload = cmd_daily(code, market, period=period, limit=limit, raw_symbol=symbol)
        elif command == "index-daily":
            payload = cmd_index_daily(symbol, period=period, limit=limit)
        elif command == "profile":
            payload = cmd_profile(code, market, raw_symbol=symbol)
        elif command == "financial":
            payload = cmd_financial(code, market, raw_symbol=symbol)
        elif command == "financials":
            payload = cmd_financials(code, market, raw_symbol=symbol)
        elif command == "all":
            payload = cmd_all(code, market, raw_symbol=symbol)
        elif command == "description":
            payload = cmd_description(code, raw_symbol=symbol)
        elif command == "announcements":
            payload = cmd_announcements(code, raw_symbol=symbol)
        elif command == "relations":
            payload = cmd_relations(code, raw_symbol=symbol)
        else:
            raise ValueError(f"未知命令: {command}")
    except Exception as exc:
        from data_contract import make_envelope, make_gap, make_source, make_symbol
        payload = make_envelope(
            command,
            "failed",
            make_symbol(symbol, code, market),
            {},
            sources=[make_source("command", "failed", reason=str(exc)[:200])],
            gaps=[make_gap("command_failed", "data", str(exc)[:200], retryable=False)],
        )

    return _inject_proxy_note(payload, needs_yahoo, proxy_ok)


def _inject_proxy_note(payload: dict, needs_yahoo: bool, proxy_ok: bool) -> dict:
    """将代理诊断加入 v1 notes/gaps，不再创建私有顶层字段。"""
    if not isinstance(payload, dict):
        return payload
    notes = payload.setdefault("notes", [])
    if needs_yahoo and not proxy_ok:
        notes.insert(0, "[代理缺失] 未检测到代理，Yahoo Finance 请求可能限流。请设置 HTTPS_PROXY 后重试")
        payload.setdefault("sources", []).append({
            "name": "proxy",
            "status": "failed",
            "fallback": False,
            "reason": "未检测到 Yahoo 所需代理",
        })
        if payload.get("status") != "ok":
            payload.setdefault("gaps", []).append({
                "code": "proxy_unavailable",
                "field": "sources.yahoo",
                "reason": "未检测到 Yahoo 所需代理",
                "retryable": True,
            })
    elif needs_yahoo and proxy_ok and payload.get("status") == "failed":
        notes.append("[代理已设但数据为空] 可能是代理节点或 Yahoo 限流，请切换节点或稍后重试")
    return payload


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
    parser.add_argument("--period", choices=["1mo", "1y", "5y", "max"], default="1y",
                        help="daily/index-daily 请求窗口")
    parser.add_argument("--limit", type=int, default=None,
                        help="daily/index-daily 最多返回的最近观测数")
    args = parser.parse_args()

    payload = execute_command(
        args.command,
        args.symbol,
        proxy=args.proxy,
        period=args.period,
        limit=args.limit,
    )

    if args.output == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(print_text(payload))

    return 1 if payload.get("status") == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())