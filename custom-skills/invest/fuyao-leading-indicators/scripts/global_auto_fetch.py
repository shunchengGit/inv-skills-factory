"""海外汽车销量数据获取。

US：FRED CSV（Total Vehicle Sales，免费，无需 API Key）
EU：搜索 ACEA 月度新闻稿（无稳定免费 API，标记 search_required）

FRED 系列：TOTALSA = Total Vehicle Sales (millions, SAAR)
"""

import datetime
import re

import requests

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

HEADERS = {
    "User-Agent": "curl/8.0",  # FRED's Akamai CDN seems to prefer simple UAs
    "Accept": "text/csv,application/csv,*/*",
}


def _parse_fred_csv(text: str) -> list[dict]:
    """解析 FRED CSV：observation_date, value。"""
    rows = []
    for line in text.strip().split("\n"):
        if line.startswith("observation_date") or not line.strip():
            continue
        parts = line.split(",")
        if len(parts) >= 2:
            try:
                date_str = parts[0].strip()
                val = float(parts[1].strip())
                # 格式：YYYY-MM-DD → YYYY年M月
                date_parts = date_str.split("-")
                if len(date_parts) >= 2:
                    month_label = f"{date_parts[0]}年{int(date_parts[1])}月"
                else:
                    month_label = date_str
                rows.append({
                    "date": date_str,
                    "label": month_label,
                    "value": val,
                })
            except (ValueError, IndexError):
                continue
    return rows


def _comma(value: float) -> str:
    """格式化大数字。"""
    if value >= 1000:
        return f"{value:,.0f}"
    return f"{value:.2f}"


def _fred_session():
    """创建不走代理的 FRED 专用 session。"""
    s = requests.Session()
    s.trust_env = False  # 不走系统代理，FRED 需直连
    s.headers.update(HEADERS)
    return s


def fetch_us_auto_sales(months: int = 12) -> dict:
    """获取美国汽车销量（FRED TOTALSA）。

    TOTALSA = Total Vehicle Sales, millions, seasonally adjusted annual rate (SAAR).
    如 15.95 表示年化 1595 万辆。

    返回 {
        "latest_month": "2026年4月",
        "sales_saar": 16.85,      # 百万辆（年化）
        "mom_change": 0.03,       # 环比
        "yoy_change": 0.05,       # 同比
        "history": [...],
        "source": "fred",
        "parse_status": "success" | "failed",
        "fetched_at": "...",
    }
    """
    result = {
        "latest_month": None,
        "sales_saar": None,
        "unit": "百万辆（SAAR年化）",
        "mom_change": None,
        "yoy_change": None,
        "history": [],
        "source": "fred_total_sa",
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    try:
        today = datetime.date.today()
        start = today.replace(year=today.year - 2)
        params = {
            "id": "TOTALSA",
            "cosd": start.strftime("%Y-%m-%d"),
            "coed": today.strftime("%Y-%m-%d"),
        }
        # FRED 网络有时不稳定，最多重试 2 次
        session = _fred_session()
        resp = None
        last_error = None
        for _ in range(3):
            try:
                resp = session.get(FRED_CSV, params=params, timeout=30)
                resp.raise_for_status()
                break
            except Exception as e:
                last_error = e
                continue
        if resp is None:
            raise last_error or RuntimeError("FRED 请求失败")
        rows = _parse_fred_csv(resp.text)

        if rows:
            # 按日期降序
            rows.sort(key=lambda x: x["date"], reverse=True)
            result["history"] = rows[:months]

            latest = rows[0]
            result["latest_month"] = latest["label"]
            result["sales_saar"] = latest["value"]

            # 环比（前一月）
            if len(rows) >= 2:
                prev = rows[1]
                if prev["value"] and prev["value"] > 0:
                    result["mom_change"] = round(
                        (latest["value"] - prev["value"]) / prev["value"], 4
                    )

            # 同比（去年同期）
            yoy_candidates = [
                r for r in rows
                if r["date"][:7] == latest["date"][:4] + "-" + latest["date"][5:7]
                and r["date"][:7] != latest["date"][:7]
            ]
            if not yoy_candidates:
                yoy_candidates = [
                    r for r in rows
                    if r["date"][5:7] == latest["date"][5:7]
                    and r["date"][:4] != latest["date"][:4]
                ]
            if yoy_candidates:
                yoy = yoy_candidates[0]
                if yoy["value"] and yoy["value"] > 0:
                    result["yoy_change"] = round(
                        (latest["value"] - yoy["value"]) / yoy["value"], 4
                    )

            result["parse_status"] = "success"
        else:
            result["parse_status"] = "failed"
            result["error"] = "FRED CSV 返回空数据"

    except Exception as e:
        result["parse_status"] = "failed"
        result["error"] = str(e)[:200]

    return result


def fetch_eu_auto_sales() -> dict:
    """获取欧洲汽车销量。

    ACEA（欧洲汽车制造商协会）每月发布新车注册数据，但无稳定免费 API。
    当前标记为 agent_required，由 Agent 搜索 ACEA 月度新闻稿补充。
    """
    return {
        "parse_status": "agent_required",
        "source": "acea",
        "note": "ACEA 月度新车注册数据无稳定免费 API。Agent 搜索'ACEA new car registrations monthly 2026'或'欧洲汽车销量 月度 ACEA'获取",
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
