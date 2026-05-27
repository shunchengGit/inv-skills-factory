#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "playwright>=1.40.0",
#   "html2text>=2024.2.26",
# ]
# ///
"""Playwright 无头浏览器抓取，替代 browser_navigate。

Firecrawl adapter 用 requests.get 无法渲染 JS，导致 Investopedia、Yahoo Finance 等
SPA/JS 重度页面返回空内容或 Cloudflare 拦截页。本脚本用 Playwright chromium 解决。

与 Firecrawl adapter 的区别：
- JS 渲染：Chromium 执行 JavaScript，SPA 页面可正常抓取
- 智能正文：自动检测 main/article 等语义标签，过滤导航和页脚噪音
- 代理集成：通过 _shared/proxy 自动检测 Clash 代理

用法:
  uv run custom-skills/cs-crawl/scripts/pwright_scrape.py scrape <url>
  uv run custom-skills/cs-crawl/scripts/pwright_scrape.py scrape <url> --selector article
  uv run custom-skills/cs-crawl/scripts/pwright_scrape.py scrape <url> --wait 5000
  uv run custom-skills/cs-crawl/scripts/pwright_scrape.py text <url>
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from proxy import detect_proxy

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 正文选择器优先级（与 Firecrawl adapter 一致）
_CONTENT_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    ".post-content",
    ".article-content",
    ".content",
    "#content",
    "#main",
    ".markdown-body",
]


def _check_playwright() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _extract_main_html(page) -> str:
    """智能提取正文 HTML，优先匹配语义标签，回退全页。"""
    for sel in _CONTENT_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el:
                html = el.inner_html()
                if len(html) > 200:
                    return html
        except Exception:
            continue
    return page.content()


def scrape_url(
    url: str,
    *,
    selector: str | None = None,
    wait_ms: int = 3000,
    wait_until: str = "domcontentloaded",
    max_chars: int = 60000,
) -> dict:
    """用 Playwright 抓取 URL，返回 markdown 内容。

    Args:
        url: 目标 URL
        selector: CSS 选择器，只提取匹配元素（覆盖默认智能提取）
        wait_ms: 页面加载后额外等待毫秒数（等 JS 渲染完成）
        wait_until: Playwright wait_until 策略
        max_chars: markdown 输出最大字符数

    Returns:
        {"success": bool, "url": str, "title": str, "markdown": str, "error": str|None}
    """
    if not _check_playwright():
        return {
            "success": False,
            "url": url,
            "title": None,
            "markdown": None,
            "error": "playwright 未安装。请运行: uv run playwright install chromium",
        }

    from playwright.sync_api import sync_playwright

    proxy_url = detect_proxy()
    launch_opts: dict = {"headless": True}
    if proxy_url:
        launch_opts["proxy"] = {"server": proxy_url}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_opts)
            context = browser.new_context(
                user_agent=_UA,
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            page.goto(url, wait_until=wait_until, timeout=30000)
            page.wait_for_timeout(wait_ms)

            title = page.title()

            if selector:
                try:
                    el = page.query_selector(selector)
                    html = el.inner_html() if el else page.content()
                except Exception:
                    html = page.content()
            else:
                html = _extract_main_html(page)

            browser.close()

        md = _html_to_md(html)
        if len(md) > max_chars:
            md = md[:max_chars] + "\n\n... (truncated)"

        return {
            "success": True,
            "url": url,
            "title": title,
            "markdown": md,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "url": url,
            "title": None,
            "markdown": None,
            "error": str(e)[:500],
        }


def extract_text(url: str, *, wait_ms: int = 3000) -> dict:
    """用 Playwright 抓取 URL，返回纯文本（inner_text），不做 markdown 转换。

    比 scrape_url 更快，适合只需要文本内容的场景。
    智能提取正文区域文本，过滤导航噪音。
    """
    if not _check_playwright():
        return {
            "success": False,
            "url": url,
            "text": None,
            "error": "playwright 未安装。请运行: uv run playwright install chromium",
        }

    from playwright.sync_api import sync_playwright

    proxy_url = detect_proxy()
    launch_opts: dict = {"headless": True}
    if proxy_url:
        launch_opts["proxy"] = {"server": proxy_url}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_opts)
            context = browser.new_context(
                user_agent=_UA,
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(wait_ms)

            title = page.title()

            # 智能提取正文文本
            text = None
            for sel in _CONTENT_SELECTORS:
                try:
                    el = page.query_selector(sel)
                    if el:
                        t = el.inner_text()
                        if len(t) > 200:
                            text = t
                            break
                except Exception:
                    continue
            if text is None:
                text = page.inner_text("body")

            browser.close()

        if len(text) > 60000:
            text = text[:60000] + "\n\n... (truncated)"

        return {
            "success": True,
            "url": url,
            "title": title,
            "text": text,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "url": url,
            "text": None,
            "error": str(e)[:500],
        }


def _html_to_md(html: str) -> str:
    """HTML → Markdown，与 Firecrawl adapter 保持一致的转换逻辑。"""
    import html2text

    h = html2text.HTML2Text()
    h.ignore_images = True
    h.ignore_links = False
    h.body_width = 0
    return h.handle(html)


def main():
    parser = argparse.ArgumentParser(description="Playwright 无头浏览器抓取")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scrape = sub.add_parser("scrape", help="抓取 URL → Markdown")
    p_scrape.add_argument("url")
    p_scrape.add_argument("--selector", help="CSS 选择器，只提取匹配元素")
    p_scrape.add_argument("--wait", type=int, default=3000, help="页面加载后额外等待毫秒数")
    p_scrape.add_argument("--wait-until", default="domcontentloaded",
                           choices=["domcontentloaded", "load", "networkidle"])

    p_text = sub.add_parser("text", help="抓取 URL → 纯文本")
    p_text.add_argument("url")
    p_text.add_argument("--wait", type=int, default=3000, help="页面加载后额外等待毫秒数")

    args = parser.parse_args()

    if args.command == "scrape":
        result = scrape_url(
            args.url,
            selector=args.selector,
            wait_ms=args.wait,
            wait_until=args.wait_until,
        )
    elif args.command == "text":
        result = extract_text(args.url, wait_ms=args.wait)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
