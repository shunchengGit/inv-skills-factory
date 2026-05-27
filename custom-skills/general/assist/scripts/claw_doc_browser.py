#!/usr/bin/env python3
"""Playwright-based doc scraper. Fetches page text, saves to ddcursor/<title>/content.raw.txt."""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(2)


def sanitize_filename(name: str) -> str:
    """Replace illegal filename chars with '-', collapse runs."""
    name = name.strip()
    if not name:
        return "untitled"
    name = re.sub(r'[\\/:*?"<>|\t\n\r]+', "-", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.strip("-").strip()
    return name or "untitled"


def wechat_extract(page) -> str:
    """Extract WeChat article body from #js_content, truncating trailing fluff."""
    try:
        el = page.wait_for_selector("#js_content", timeout=10_000)
    except PWTimeoutError:
        return ""

    # Try to drop operational blocks at the end
    try:
        page.evaluate("""
            const root = document.querySelector('#js_content');
            if (!root) return;
            const cutAfter = root.querySelector('#js_pc_report_section, #js_PC_share_section');
            if (cutAfter) {
                let node = cutAfter;
                while (node) {
                    const next = node.nextSibling;
                    node.remove();
                    node = next;
                }
            }
            const wecomLinks = root.querySelectorAll('[id^="wecom_imagekey"]');
            wecomLinks.forEach(n => n.remove());
        """)
    except Exception:
        pass

    text = el.inner_text()
    if not text:
        return ""

    # Truncate after known tail patterns for WeChat
    tail_markers = [
        "阅读",  # "阅读 1000" etc
        "阅读原文",
        "阅读全文",
        "赞",
        "分享",
        "收藏",
        "点赞",
        "在看",
    ]
    lines = text.split("\n")
    cutoff = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if any(stripped.startswith(m) for m in tail_markers):
            cutoff = i
            break
    if cutoff is not None and cutoff > 0:
        lines = lines[:cutoff]
        text = "\n".join(lines)

    return text.strip()


def fetch_and_save(url: str, args) -> int:
    outdir = Path(args.outdir) if args.outdir else Path(os.getcwd()) / "ddcursor"
    outdir.mkdir(parents=True, exist_ok=True)

    storage_path = None
    if args.storage_state:
        storage_path = args.storage_state
    else:
        default_storage = Path.home() / ".ddcursor" / ".storage_state.json"
        if default_storage.exists():
            storage_path = str(default_storage)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        context_kwargs = {}
        if storage_path and os.path.exists(storage_path):
            context_kwargs["storage_state"] = storage_path
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as e:
            print(f"Navigation failed: {e}", file=sys.stderr)
            browser.close()
            return 1

        # Additional wait
        wait_ms = args.wait_ms or 2000
        page.wait_for_timeout(wait_ms)

        title = page.title()
        # Determine if WeChat
        is_wechat = "mp.weixin.qq.com" in urlparse(url).netloc

        if is_wechat:
            body = wechat_extract(page)
        else:
            body = page.inner_text("body")

        # Ensure login if needed (login page detection)
        if args.ensure_login and not args.no_ensure_login:
            login_indicators = ["登录", "sign in", "log in", "请登录", "Sign In", "Log In"]
            body_lower = body[:500].lower() if body else ""
            is_login_page = any(ind.lower() in body_lower for ind in login_indicators)
            if is_login_page and not args.headed:
                print("Login page detected in headless mode. Use --headed to log in.", file=sys.stderr)
                browser.close()
                return 3
            elif is_login_page and args.headed:
                print("Login page detected. Please log in, then press Enter...", file=sys.stderr)
                input()
                page.wait_for_timeout(2000)
                if is_wechat:
                    body = wechat_extract(page)
                else:
                    body = page.inner_text("body")

        # Check body empty
        if not body or not body.strip():
            print("Extracted body is empty.", file=sys.stderr)
            browser.close()
            return 4

        # Save
        dirname = sanitize_filename(title)
        target_dir = outdir / dirname
        target_dir.mkdir(parents=True, exist_ok=True)
        outfile = target_dir / "content.raw.txt"
        outfile.write_text(body.strip() + "\n", encoding="utf-8")

        # Save storage if requested
        if args.save_storage:
            save_path = args.save_storage
            if save_path == "default":
                default_dir = Path.home() / ".ddcursor"
                default_dir.mkdir(parents=True, exist_ok=True)
                save_path = str(default_dir / ".storage_state.json")
            context.storage_state(path=save_path)

        browser.close()

    abs_path = outfile.resolve()
    print(str(abs_path), file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Playwright doc scraper")
    parser.add_argument("--url", required=True, help="Page URL to fetch")
    parser.add_argument("--headed", action="store_true", help="Run browser visibly")
    parser.add_argument("--wait-ms", type=int, default=2000, help="Extra wait after load (ms)")
    parser.add_argument("--storage-state", help="Path to storage state JSON")
    parser.add_argument("--save-storage", help="Path to save storage state. Use 'default' for ~/.ddcursor/.storage_state.json")
    parser.add_argument("--no-ensure-login", action="store_true", help="Skip login-page detection")
    parser.add_argument("--login-wait-s", type=int, default=0, help="Extra wait for manual login (seconds)")
    parser.add_argument("--ensure-login", action="store_true", default=True, help="Detect and handle login pages (default: on)")
    parser.add_argument("--outdir", help="Output directory (default: ./ddcursor)")
    args = parser.parse_args()

    rc = fetch_and_save(args.url, args)
    sys.exit(rc)


if __name__ == "__main__":
    main()
