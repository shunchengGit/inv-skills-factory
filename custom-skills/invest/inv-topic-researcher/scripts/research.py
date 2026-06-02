#!/usr/bin/env python3
from __future__ import annotations

"""投资主题研究自动化：搜索 → 去重 → 抓取。

将搜索结果中未入库的 URL 逐个抓取为 Markdown，Agent 负责分析分类和存储。

用法:
  uv run custom-skills/invest/inv-topic-researcher/scripts/research.py <topic>
  uv run custom-skills/invest/inv-topic-researcher/scripts/research.py <topic> --max 5
  uv run custom-skills/invest/inv-topic-researcher/scripts/research.py <topic> --urls <url1> <url2>  # 跳过搜索
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
from proxy import detect_proxy

SEARXNG_URL = "http://127.0.0.1:3671/search"
FIRECRAWL_URL = "http://localhost:3672/v1/scrape"
PWIGHT_SCRIPT = str(Path(__file__).resolve().parents[3] / "inv-web-crawler" / "scripts" / "pwright_scrape.py")
KM_INIT_SCRIPT = str(Path(__file__).resolve().parents[3] / "general" / "gen-knowledge-curator" / "scripts" / "km_init.py")

UA = "inv-topic-researcher/1.0"


def search(query: str, limit: int = 10) -> list[dict]:
    """SearXNG 搜索，返回 [{title, url, content}, ...]。"""
    params = urllib.parse.urlencode({"q": query, "format": "json", "categories": "general"})
    req = urllib.request.Request(f"{SEARXNG_URL}?{params}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        return [{"error": f"搜索失败: {e}"}]

    results = []
    for item in data.get("results", [])[:limit]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        })
    return results


def get_known_urls() -> set[str]:
    """从知识库 Index 提取已导入的所有 URL。"""
    import subprocess
    r = subprocess.run(
        ["uv", "run", KM_INIT_SCRIPT],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        print(f"⚠ km_init 失败: {r.stderr[:200]}", file=sys.stderr)
        return set()

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return set()

    urls = set()
    for entries in data.get("index", {}).get("categories", {}).values():
        for entry in entries:
            if entry.get("url"):
                urls.add(entry["url"])
    return urls


def scrape_firecrawl(url: str) -> dict | None:
    """Firecrawl 抓取，返回 {title, content, source} 或 None。"""
    import requests
    try:
        r = requests.post(
            FIRECRAWL_URL,
            json={"url": url},
            headers={"User-Agent": UA},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        data = r.json().get("data", {})
        content = data.get("markdown") or data.get("content", "")
        title = data.get("metadata", {}).get("title", "")
        if not content or len(content) < 500:
            return None
        if any(kw in content for kw in ("Just a moment", "Checking your browser", "请稍候")):
            return None
        return {"title": title, "content": content, "source": "firecrawl"}
    except Exception:
        return None


def scrape_firecrawl_batch(urls: list[str]) -> list[dict | None]:
    """批量 Firecrawl 抓取，返回 [{title, content, source} 或 None, ...]。"""
    import requests
    results = []
    for url in urls:
        try:
            r = requests.post(
                FIRECRAWL_URL,
                json={"url": url},
                headers={"User-Agent": UA},
                timeout=30,
            )
            if r.status_code != 200:
                results.append(None)
                continue
            data = r.json().get("data", {})
            content = data.get("markdown") or data.get("content", "")
            title = data.get("metadata", {}).get("title", "")
            if not content or len(content) < 500:
                results.append(None)
                continue
            if any(kw in content for kw in ("Just a moment", "Checking your browser", "请稍候")):
                results.append(None)
                continue
            results.append({"title": title, "content": content, "source": "firecrawl"})
        except Exception:
            results.append(None)
    return results


def scrape_pwright(url: str) -> dict | None:
    """Playwright 兜底抓取，返回 {title, content, source} 或 None。"""
    import subprocess
    try:
        r = subprocess.run(
            ["uv", "run", PWIGHT_SCRIPT, "scrape", url, "--wait", "3000"],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        if not data.get("success"):
            return None
        md = data.get("markdown", "")
        if not md or len(md.strip()) < 100:
            return None
        return {"title": data.get("title", ""), "content": md.strip(), "source": "pwright"}
    except Exception:
        return None


def scrape_url(url: str) -> dict | None:
    """Firecrawl → pwright 降级抓取。"""
    result = scrape_firecrawl(url)
    if result:
        return result
    return scrape_pwright(url)


def main():
    parser = argparse.ArgumentParser(description="投资主题研究：搜索 → 去重 → 抓取")
    parser.add_argument("topic", help="研究主题")
    parser.add_argument("--max", type=int, default=10, dest="limit", help="最大搜索/抓取数")
    parser.add_argument("--urls", nargs="*", help="跳过搜索，直接抓取指定 URL")
    args = parser.parse_args()

    # 1. 获取 URL 列表
    if args.urls:
        candidates = [{"title": "", "url": u, "content": ""} for u in args.urls]
        print(f"# 直接抓取 {len(candidates)} 个 URL", file=sys.stderr)
    else:
        print(f"# 搜索: {args.topic}", file=sys.stderr)
        candidates = search(args.topic, limit=args.limit)
        if not candidates:
            print(json.dumps({"error": "搜索无结果"}))
            sys.exit(1)
        if "error" in candidates[0]:
            print(json.dumps({"error": candidates[0]["error"]}))
            sys.exit(1)
        print(f"# 搜索命中: {len(candidates)} 篇", file=sys.stderr)

    # 2. 去重
    known = get_known_urls()
    new_items = [c for c in candidates if c["url"] not in known]
    skipped = len(candidates) - len(new_items)
    print(f"# 去重: {skipped} 篇已导入, {len(new_items)} 篇待抓取", file=sys.stderr)

    if not new_items:
        print(json.dumps({"status": "no_new_content", "total": len(candidates), "skipped": skipped}))
        return

    # 3. 逐条抓取（支持批量并发）
    results = []
    batch_size = 3  # 并发数
    for i in range(0, len(new_items), batch_size):
        batch = new_items[i:i+batch_size]
        print(f"# [{i+1}/{len(new_items)}] 批量抓取 {len(batch)} 个 URL", file=sys.stderr)
        
        # 先批量尝试 Firecrawl
        urls = [item["url"] for item in batch]
        batch_results = scrape_firecrawl_batch(urls)
        
        for j, (item, scraped) in enumerate(zip(batch, batch_results)):
            url = item["url"]
            if scraped:
                scraped["url"] = url
                scraped["status"] = "success"
                results.append(scraped)
                print(f"#   ✓ {len(scraped['content'])} chars ({scraped['source']})", file=sys.stderr)
            else:
                # Firecrawl 失败，降级到 pwright
                print(f"#   → Firecrawl 失败，降级 pwright: {url[:80]}", file=sys.stderr)
                scraped = scrape_pwright(url)
                if scraped:
                    scraped["url"] = url
                    scraped["status"] = "success"
                    results.append(scraped)
                    print(f"#   ✓ {len(scraped['content'])} chars ({scraped['source']})", file=sys.stderr)
                else:
                    results.append({"url": url, "status": "failed", "reason": "scrape_failed"})
                    print(f"#   ✗ 抓取失败", file=sys.stderr)
        
        time.sleep(1)  # 礼貌间隔

    imported = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")

    output = {
        "topic": args.topic,
        "total": len(candidates),
        "skipped": skipped,
        "imported": imported,
        "failed": failed,
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
