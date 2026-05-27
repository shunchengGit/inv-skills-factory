"""港股通南向资金流向。

数据源：akshare stock_hsgt_fund_flow_summary_em（日度）+ stock_hsgt_hist_em（历史）
"""

import datetime

import pandas as pd


def _safe_ak(fn, *args, **kwargs):
    """安全调用 akshare，失败返回 None。"""
    try:
        import akshare as ak
        return getattr(ak, fn)(*args, **kwargs)
    except Exception:
        return None


def fetch_southbound_flow(days: int = 5) -> dict:
    """获取港股通南向资金流向（沪+深合计）。

    返回 {
        "latest_date": "2026-05-04",
        "daily_net_flow": 121.92,        # 当日净买入（亿港元）
        "n_day_net_flow": 350.5,         # N日累计净买入
        "n_day_avg": 70.1,               # N日均值
        "history": [...],                # 最近N日明细
        "source": "akshare_hsgt",
        "parse_status": "success" | "failed",
        "fetched_at": "...",
    }
    """
    result = {
        "latest_date": None,
        "daily_net_flow": None,
        "n_day_net_flow": None,
        "n_day_avg": None,
        "history": [],
        "source": "akshare_hsgt",
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    try:
        import akshare as ak

        # 1. 日度汇总（沪深港股通分别统计）
        summary = _safe_ak("stock_hsgt_fund_flow_summary_em")
        if summary is None or summary.empty:
            result["parse_status"] = "failed"
            result["error"] = "stock_hsgt_fund_flow_summary_em 返回空"
            return result

        # 筛选南向（港股通沪 + 港股通深）
        south = summary[summary["资金方向"] == "南向"]
        if south.empty:
            result["parse_status"] = "failed"
            result["error"] = "未找到南向数据"
            return result

        # 取最新交易日
        latest_date = south["交易日"].max()
        latest_rows = south[south["交易日"] == latest_date]
        daily_total = latest_rows["成交净买额"].sum()
        result["latest_date"] = str(latest_date)
        result["daily_net_flow"] = round(float(daily_total), 2)

        # 2. 历史序列（最近 N 日）
        # 港股通沪
        df_sh = _safe_ak("stock_hsgt_hist_em", symbol="港股通沪")
        # 港股通深
        df_sz = _safe_ak("stock_hsgt_hist_em", symbol="港股通深")

        if df_sh is not None and not df_sh.empty and df_sz is not None and not df_sz.empty:
            sh_cols = df_sh[["日期", "当日成交净买额"]].copy()
            sh_cols.columns = ["date", "sh_net"]
            sz_cols = df_sz[["日期", "当日成交净买额"]].copy()
            sz_cols.columns = ["date", "sz_net"]

            merged = pd.merge(sh_cols, sz_cols, on="date", how="outer")
            merged = merged.sort_values("date", ascending=False)
            merged["total_net"] = merged["sh_net"].fillna(0) + merged["sz_net"].fillna(0)

            for _, r in merged.head(days).iterrows():
                result["history"].append({
                    "date": str(r["date"]),
                    "sh_net": round(float(r["sh_net"]), 2) if pd.notna(r["sh_net"]) else None,
                    "sz_net": round(float(r["sz_net"]), 2) if pd.notna(r["sz_net"]) else None,
                    "total_net": round(float(r["total_net"]), 2),
                })

            recent_flows = [h["total_net"] for h in result["history"][:days] if h["total_net"] is not None]
            if recent_flows:
                result["n_day_net_flow"] = round(sum(recent_flows), 2)
                result["n_day_avg"] = round(sum(recent_flows) / len(recent_flows), 2)

        result["parse_status"] = "success"

    except Exception as e:
        result["parse_status"] = "failed"
        result["error"] = str(e)[:200]

    return result
