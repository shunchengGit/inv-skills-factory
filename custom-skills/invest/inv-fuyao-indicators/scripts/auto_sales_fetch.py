#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "playwright>=1.40.0",
# ]
# ///
"""乘联会汽车销量数据获取。

使用 Playwright 无头浏览器访问乘联会网站提取月度汽车销量数据。
策略：首页提取预测/月度分析文章链接 → 进入文章详情页 → 解析销量数据。

返回结构包含 parse_status 和 raw_text，供 LLM 在正则失败时自行提取。
"""

import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))
from pwright import launch_browser

CPCA_HOME = "https://www.cpcaauto.com/"
CPCA_NEWSLIST = "https://www.cpcaauto.com/newslist.php?types=csjd"


def fetch_auto_sales(max_retries: int = 2, raw_only: bool = False) -> dict:
    """获取最近数月乘用车销量数据。

    Args:
        max_retries: Playwright 抓取重试次数
        raw_only: True 时跳过正则解析，只返回 raw_text 供 LLM 提取

    返回 {
        "latest_month": "2026年4月",
        "retail_sales": 185.0,
        "yoy_change": 0.065,
        "mom_change": -0.03,
        "wholesale_sales": 192.0,
        "nev_penetration": 60.6,
        "parse_status": "success" | "partial" | "failed",
        "raw_text": "...",
        "source": "cpca",
        "fetched_at": "...",
    }
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            raw_text, result = _do_fetch_auto_sales(raw_only=raw_only)
            if raw_only:
                return {
                    "raw_text": raw_text,
                    "parse_status": "raw_only",
                    "source": "cpca",
                    "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
                }
            if not result.get("error"):
                if result.get("parse_status") != "success":
                    result["raw_text"] = raw_text
                return result
            last_error = result.get("error")
        except Exception as e:
            last_error = str(e)[:200]

    return {
        "error": f"乘联会数据获取失败（重试{max_retries}次）: {last_error}",
        "source": "cpca",
        "parse_status": "failed",
    }


def _do_fetch_auto_sales(raw_only: bool = False) -> tuple[str, dict]:
    """实际执行 Playwright 抓取逻辑。

    返回 (raw_text, parsed_result)。
    """
    pw, browser, context, page = launch_browser()

    try:
        # Step 1: 从首页获取文章链接
        article_urls = _find_article_urls(page)

        # Step 2: 依次访问文章，解析销量数据
        all_text = ""
        for url in article_urls[:3]:
            try:
                page.goto(url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)
                all_text += page.inner_text("body") + "\n\n"
            except Exception:
                continue

        # 也把首页文本加入（首页摘要本身可能含关键数据）
        page.goto(CPCA_HOME, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        all_text = page.inner_text("body") + "\n\n" + all_text
    finally:
        browser.close()
        pw.stop()

    if raw_only:
        return all_text, {}

    parsed = _parse_sales_data(all_text)
    return all_text, parsed


def _find_article_urls(page) -> list[str]:
    """从乘联会首页/资讯列表页找到销量相关文章链接。"""
    urls = []

    # 先看首页
    page.goto(CPCA_HOME, wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(2000)

    links = page.query_selector_all("a")
    keywords = ["预测", "月度", "月报", "市场分析", "零售", "产销"]
    for link in links:
        try:
            text = link.inner_text()
            href = link.get_attribute("href") or ""
            if any(kw in text for kw in keywords) and href:
                if href.startswith("http"):
                    urls.append(href)
                elif href.startswith("/"):
                    urls.append(f"https://www.cpcaauto.com{href}")
                elif not href.startswith("#"):
                    urls.append(f"https://www.cpcaauto.com/{href}")
        except Exception:
            continue

    # 再看资讯列表页
    try:
        page.goto(CPCA_NEWSLIST, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        links = page.query_selector_all("a")
        for link in links:
            try:
                text = link.inner_text()
                href = link.get_attribute("href") or ""
                if any(kw in text for kw in keywords) and href:
                    if href.startswith("http"):
                        urls.append(href)
                    elif href.startswith("/"):
                        urls.append(f"https://www.cpcaauto.com{href}")
                    elif not href.startswith("#"):
                        urls.append(f"https://www.cpcaauto.com/{href}")
            except Exception:
                continue
    except Exception:
        pass

    # 去重，保持顺序
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def _parse_sales_data(text: str) -> dict:
    """从乘联会页面文本中解析销量数据和新能源渗透率。"""
    result = {
        "latest_month": None,
        "retail_sales": None,
        "yoy_change": None,
        "mom_change": None,
        "wholesale_sales": None,
        "nev_penetration": None,
        "nev_penetration_trend": None,
        "history": [],
        "source": "cpca",
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    # 匹配月份
    month_pattern = r"(\d{4})年(\d{1,2})月"
    month_m = re.search(month_pattern, text)
    if month_m:
        result["latest_month"] = f"{month_m.group(1)}年{month_m.group(2)}月"

    # 匹配零售销量
    retail_patterns = [
        r"狭义乘用车零售[预计约]*?(\d+\.?\d*)\s*万辆",
        r"乘用车零售[预计约]*?(\d+\.?\d*)\s*万辆",
        r"零售销量[为预计约]*?(\d+\.?\d*)\s*万辆",
        r"零售[预计约]*?(\d+\.?\d*)\s*万辆",
    ]
    for pat in retail_patterns:
        m = re.search(pat, text)
        if m:
            result["retail_sales"] = float(m.group(1))
            break

    # 匹配批发销量
    wholesale_patterns = [
        r"乘用车批发[预计约]*?(\d+\.?\d*)\s*万辆",
        r"批发销量[为预计约]*?(\d+\.?\d*)\s*万辆",
        r"批发[预计约]*?(\d+\.?\d*)\s*万辆",
    ]
    for pat in wholesale_patterns:
        m = re.search(pat, text)
        if m:
            result["wholesale_sales"] = float(m.group(1))
            break

    # 匹配同比变化
    yoy_patterns = [
        (r"同比下降(\d+\.?\d*)%", -1),
        (r"同比[减少]降(\d+\.?\d*)%", -1),
        (r"同比增长(\d+\.?\d*)%", 1),
        (r"同比[为约]?(-?\d+\.?\d*)%", None),
    ]
    for pat, sign in yoy_patterns:
        m = re.search(pat, text)
        if m:
            val = float(m.group(1)) / 100
            if sign is not None:
                val = abs(val) * sign
            result["yoy_change"] = round(val, 4)
            break

    # 匹配环比变化
    mom_patterns = [
        (r"环比下降(\d+\.?\d*)%", -1),
        (r"环比[减少]降(\d+\.?\d*)%", -1),
        (r"环比增长(\d+\.?\d*)%", 1),
        (r"环比[为约]?(-?\d+\.?\d*)%", None),
    ]
    for pat, sign in mom_patterns:
        m = re.search(pat, text)
        if m:
            val = float(m.group(1)) / 100
            if sign is not None:
                val = abs(val) * sign
            result["mom_change"] = round(val, 4)
            break

    # 匹配新能源渗透率
    nev_patterns = [
        r"新能源[车]?渗透率[为约达]?(\d+\.?\d*)%",
        r"新能源[车]?零售渗透率[为约达]?(\d+\.?\d*)%",
        r"新能源[车]?批发渗透率[为约达]?(\d+\.?\d*)%",
        r"渗透率[为约达]?(\d+\.?\d*)%",
    ]
    for pat in nev_patterns:
        m = re.search(pat, text)
        if m:
            result["nev_penetration"] = float(m.group(1))
            break

    # 如果没有直接匹配到渗透率，从"新能源预计XX万辆"和零售销量计算
    if result["nev_penetration"] is None:
        nev_sales_match = re.search(r"新能源[预计约]*?(\d+\.?\d*)\s*万辆", text)
        if nev_sales_match and result["retail_sales"] and result["retail_sales"] > 0:
            nev_sales = float(nev_sales_match.group(1))
            result["nev_penetration"] = round(nev_sales / result["retail_sales"] * 100, 1)

    # 判断解析状态
    has_key_data = result["retail_sales"] is not None and result["latest_month"] is not None
    has_any_data = result["retail_sales"] is not None or result["latest_month"] is not None

    if has_key_data:
        result["parse_status"] = "success"
    elif has_any_data:
        result["parse_status"] = "partial"
        result["error"] = "正则仅提取到部分数据，建议使用 raw_text 由 LLM 提取"
    else:
        result["parse_status"] = "failed"
        result["error"] = "未能从乘联会页面解析出销量数据，页面结构可能已变化"

    return result
