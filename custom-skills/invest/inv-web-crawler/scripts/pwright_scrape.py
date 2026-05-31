#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "playwright>=1.40.0",
#   "html2text>=2024.2.26",
# ]
# ///
"""Playwright 无头浏览器抓取 CLI。

Firecrawl adapter 用 requests.get 无法渲染 JS，导致 Investopedia、Yahoo Finance 等
SPA/JS 重度页面返回空内容或 Cloudflare 拦截页。本脚本用 Playwright chromium 解决。

核心逻辑由 base-pwright 提供，本脚本仅为 CLI 适配层。

用法:
  uv run custom-skills/invest/inv-web-crawler/scripts/pwright_scrape.py scrape <url>
  uv run custom-skills/invest/inv-web-crawler/scripts/pwright_scrape.py scrape <url> --selector article
  uv run custom-skills/invest/inv-web-crawler/scripts/pwright_scrape.py scrape <url> --wait 5000
  uv run custom-skills/invest/inv-web-crawler/scripts/pwright_scrape.py text <url>
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from pwright import scrape_url, extract_text


def main():
    parser = argparse.ArgumentParser(description="Playwright 无头浏览器抓取")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape", help="抓取 URL → Markdown")
    p_scrape.add_argument("url")
    p_scrape.add_argument("--selector", help="CSS 选择器，只提取匹配元素")
    p_scrape.add_argument("--wait", type=int, default=3000, help="页面加载后额外等待毫秒数")
    p_scrape.add_argument("--wait-until", default="domcontentloaded",
                           choices=["domcontentloaded", "load", "networkidle"])
    p_scrape.add_argument("--proxy", help="代理地址")

    p_text = sub.add_parser("text", help="抓取 URL → 纯文本")
    p_text.add_argument("url")
    p_text.add_argument("--wait", type=int, default=3000, help="页面加载后额外等待毫秒数")
    p_text.add_argument("--proxy", help="代理地址")

    args = parser.parse_args()

    if args.command == "scrape":
        result = scrape_url(
            args.url,
            selector=args.selector,
            wait_ms=args.wait,
            wait_until=args.wait_until,
            proxy=args.proxy,
        )
    elif args.command == "text":
        result = extract_text(args.url, wait_ms=args.wait, proxy=args.proxy)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
