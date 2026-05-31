"""Playwright 无头浏览器抓取核心模块。

供所有需要 JS 渲染抓取的技能脚本调用。

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "base" / "base-pwright" / "scripts"))
  from pwright import scrape_url, extract_text, launch_browser
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[4] / "scripts"))
from proxy import detect_proxy as _detect_proxy  # noqa: E402

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

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


# ── 公开接口 ──────────────────────────────────────────────────


def launch_browser(
    proxy: str | None = None,
    user_agent: str | None = None,
    viewport: dict | None = None,
):
    """启动 Playwright 无头浏览器，返回 (playwright, browser, context, page)。

    caller 负责在完成后调用 browser.close() 和 pw.stop()。
    """
    from playwright.sync_api import sync_playwright

    _ensure_playwright()
    proxy_url = proxy or _detect_proxy()

    pw = sync_playwright().start()
    launch_opts: dict = {"headless": True}
    if proxy_url:
        launch_opts["proxy"] = {"server": proxy_url}

    browser = pw.chromium.launch(**launch_opts)
    context = browser.new_context(
        user_agent=user_agent or _UA,
        viewport=viewport or {"width": 1920, "height": 1080},
    )
    page = context.new_page()
    return pw, browser, context, page


def scrape_url(
    url: str,
    *,
    selector: str | None = None,
    wait_ms: int = 3000,
    wait_until: str = "domcontentloaded",
    max_chars: int = 60000,
    proxy: str | None = None,
) -> dict:
    """用 Playwright 抓取 URL，返回 markdown 内容。"""
    return _do_scrape(
        url, _extract_md, "markdown",
        selector=selector, wait_ms=wait_ms, wait_until=wait_until,
        max_chars=max_chars, proxy=proxy,
    )


def extract_text(
    url: str,
    *,
    wait_ms: int = 3000,
    proxy: str | None = None,
) -> dict:
    """用 Playwright 抓取 URL，返回纯文本（不做 markdown 转换）。"""
    return _do_scrape(
        url, _extract_txt, "text",
        wait_ms=wait_ms, wait_until="domcontentloaded", proxy=proxy,
    )


# ── 内部实现 ──────────────────────────────────────────────────


def _check_playwright() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _ensure_playwright():
    if not _check_playwright():
        raise RuntimeError("playwright 未安装。请运行: uv run playwright install chromium")


def _extract_main_html(page, selector: str | None = None) -> str:
    """智能提取正文 HTML，优先匹配语义标签，回退全页。"""
    if selector:
        try:
            el = page.query_selector(selector)
            if el:
                return el.inner_html()
        except Exception:
            pass
        return page.content()

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


def _extract_main_text(page) -> str:
    """智能提取正文纯文本，优先语义标签，回退 body.inner_text()。"""
    for sel in _CONTENT_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el:
                t = el.inner_text()
                if len(t) > 200:
                    return t
        except Exception:
            continue
    return page.inner_text("body")


def _html_to_markdown(html: str) -> str:
    import html2text
    h = html2text.HTML2Text()
    h.ignore_images = True
    h.ignore_links = False
    h.body_width = 0
    return h.handle(html)


def _do_scrape(
    url: str,
    extract_fn,
    result_key: str,
    *,
    selector: str | None = None,
    wait_ms: int = 3000,
    wait_until: str = "domcontentloaded",
    max_chars: int = 60000,
    proxy: str | None = None,
) -> dict:
    pw, browser, context, page = launch_browser(proxy=proxy)
    try:
        page.goto(url, wait_until=wait_until, timeout=30000)
        page.wait_for_timeout(wait_ms)
        title = page.title()
        content = extract_fn(page, selector)
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n... (truncated)"
        return {"success": True, "url": url, "title": title, result_key: content, "error": None}
    except Exception as e:
        return {"success": False, "url": url, "title": None, result_key: None, "error": str(e)[:500]}
    finally:
        browser.close()
        pw.stop()


def _extract_md(page, selector: str | None = None) -> str:
    return _html_to_markdown(_extract_main_html(page, selector=selector))


def _extract_txt(page, _selector: str | None = None) -> str:
    return _extract_main_text(page)
