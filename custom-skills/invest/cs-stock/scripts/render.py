"""文本渲染 — 按 _command 字段分派渲染函数。"""

from __future__ import annotations

import json

from utils import _fmt_pct, _fmt_num


def print_text(payload: dict) -> str:
    """根据 payload 的 _command 字段分派渲染。"""
    cmd = payload.get("_command", "")
    renderer = _RENDERERS.get(cmd)
    if renderer:
        return renderer(payload)
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _render_snapshot_a(p: dict) -> str:
    lines = [f"# {p.get('name', '')} ({p.get('code', '')}) 快照", ""]

    # 公司概况
    desc = p.get("description")
    if desc:
        lines.append(f"## 公司概况")
        lines.append(desc[:500])
        lines.append("")

    # 估值
    val = p.get("valuation") or {}
    if val:
        lines.append("## 估值")
        if val.get("pe_ttm"):
            lines.append(f"- PE(TTM): {val['pe_ttm']}")
        if val.get("pe_static"):
            lines.append(f"- PE(静态): {val['pe_static']}")
        if val.get("pb"):
            lines.append(f"- PB: {val['pb']}")
        if val.get("pcr"):
            lines.append(f"- PCR: {val['pcr']}")
        if val.get("total_mv"):
            lines.append(f"- 总市值: {val['total_mv']}")
        lines.append("")

    # 财务指标
    fin = p.get("financial")
    if fin:
        lines.append("## 主要财务指标")
        for key, label in [
            ("营业总收入", "营业总收入"), ("净利润", "净利润"),
            ("营业总收入同比增长", "营收同比"), ("净利润同比增长", "净利同比"),
            ("毛利率", "毛利率"), ("净利率", "净利率"),
            ("净资产收益率", "ROE"),
        ]:
            if key in fin and fin[key] is not None:
                lines.append(f"- {label}: {fin[key]}")
        lines.append("")

    # 日K线
    daily = p.get("daily", [])
    if daily:
        lines.append("## 近5日行情")
        for d in daily:
            date = d.get("日期") or d.get("date", "")
            close = d.get("收盘") or d.get("close", "")
            vol = d.get("成交量") or d.get("volume", "")
            lines.append(f"- {date}: 收盘 {close}, 成交量 {vol}")
        lines.append("")

    # notes
    notes = p.get("_notes", [])
    if notes:
        lines.append("## 备注")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines)


def _render_snapshot_etf(p: dict) -> str:
    lines = [f"# {p.get('name', '')} ({p.get('code', '')}) ETF快照", ""]
    cat = p.get("category", "")
    if cat:
        lines.append(f"类型: {cat}")
        lines.append("")

    # NAV 与折溢价
    nav = p.get("nav")
    if nav and nav.get("latest") is not None:
        premium = nav.get("premium_pct")
        label = nav.get("premium_label", "平价")
        lines.append("## 净值与折溢价")
        lines.append(f"- 单位净值: {nav['latest']:.4f} ({nav.get('date', '')})")
        if nav.get("acc_nav") is not None:
            lines.append(f"- 累计净值: {nav['acc_nav']:.4f}")
        if premium is not None:
            lines.append(f"- 折溢价: {premium*100:+.2f}% ({label})")
        lines.append("")
    elif nav is None:
        lines.append("## 净值与折溢价")
        lines.append("- 净值数据暂不可用")
        lines.append("")

    daily = p.get("daily", [])
    if daily:
        lines.append("## 近5日行情")
        for d in daily:
            date = d.get("日期") or d.get("date", "")
            close = d.get("收盘") or d.get("close", "")
            lines.append(f"- {date}: 收盘 {close}")
        lines.append("")

    return "\n".join(lines)


def _render_snapshot_yahoo(p: dict) -> str:
    market_label = "港股" if p.get("market") == "hk" else "美股"
    lines = [f"# {p.get('name', '')} ({p.get('code', '')}) {market_label}快照", ""]

    price = p.get("price")
    currency = p.get("currency", "")
    if price is not None:
        lines.append(f"当前价: {price} {currency}")
    change = p.get("change_pct")
    if change is not None:
        lines.append(f"涨跌幅: {_fmt_pct(change)}")
    sector = p.get("sector")
    if sector:
        lines.append(f"行业: {sector}")
    industry = p.get("industry")
    if industry:
        lines.append(f"细分: {industry}")
    lines.append("")

    fund = p.get("fundamentals")
    if fund:
        lines.append("## 基本面")
        if fund.get("pe_trailing"):
            lines.append(f"- PE(Trailing): {fund['pe_trailing']:.2f}")
        if fund.get("pe_forward"):
            lines.append(f"- PE(Forward): {fund['pe_forward']:.2f}")
        if fund.get("pb"):
            lines.append(f"- PB: {fund['pb']:.2f}")
        if fund.get("market_cap"):
            lines.append(f"- 市值: {_fmt_num(fund['market_cap'], 0)}")
        if fund.get("dividend_yield"):
            lines.append(f"- 股息率: {_fmt_pct(fund['dividend_yield'] * 100)}")
        if fund.get("roe"):
            lines.append(f"- ROE: {_fmt_pct(fund['roe'] * 100)}")
        if fund.get("gross_margins"):
            lines.append(f"- 毛利率: {_fmt_pct(fund['gross_margins'] * 100)}")
        if fund.get("profit_margins"):
            lines.append(f"- 净利率: {_fmt_pct(fund['profit_margins'] * 100)}")
        if fund.get("revenue_growth"):
            lines.append(f"- 营收增速: {_fmt_pct(fund['revenue_growth'] * 100)}")
        if fund.get("earnings_growth"):
            lines.append(f"- 盈利增速: {_fmt_pct(fund['earnings_growth'] * 100)}")
        lines.append("")

    daily = p.get("daily", [])
    if daily:
        lines.append("## 近5日行情")
        for d in daily:
            date = str(d.get("Date") or d.get("date", ""))[:10]
            close = d.get("Close") or d.get("close", "")
            lines.append(f"- {date}: 收盘 {close}")
        lines.append("")

    notes = p.get("_notes", [])
    if notes:
        lines.append("## 备注")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines)


def _render_daily_a(p: dict) -> str:
    lines = [f"# {p.get('name', '')} ({p.get('code', '')}) 日K线", ""]
    daily = p.get("daily", [])
    for d in daily:
        date = d.get("日期") or d.get("date", "")
        open_ = d.get("开盘") or d.get("open", "")
        close = d.get("收盘") or d.get("close", "")
        high = d.get("最高") or d.get("high", "")
        low = d.get("最低") or d.get("low", "")
        vol = d.get("成交量") or d.get("volume", "")
        lines.append(f"- {date}: 开{open_} 高{high} 低{low} 收{close} 量{vol}")
    return "\n".join(lines)


def _render_daily_yahoo(p: dict) -> str:
    market_label = "港股" if p.get("market") == "hk" else "美股"
    lines = [f"# {p.get('code', '')} {market_label}日K线", ""]
    daily = p.get("daily", [])
    for d in daily:
        date = str(d.get("Date", ""))[:10]
        open_ = d.get("Open", "")
        close = d.get("Close", "")
        high = d.get("High", "")
        low = d.get("Low", "")
        vol = d.get("Volume", "")
        lines.append(f"- {date}: 开{open_} 高{high} 低{low} 收{close} 量{vol}")
    return "\n".join(lines)


def _render_profile_a(p: dict) -> str:
    lines = [f"# {p.get('name', '')} ({p.get('code', '')}) 基本信息", ""]
    desc = p.get("description")
    if desc:
        lines.append("## 公司概况")
        lines.append(desc[:500])
        lines.append("")
    else:
        lines.append("公司概况: 未获取到")
        lines.append("")
    return "\n".join(lines)


def _render_profile_etf(p: dict) -> str:
    lines = [f"# {p.get('name', '')} ({p.get('code', '')}) ETF信息", ""]
    cat = p.get("category", "")
    if cat:
        lines.append(f"类型: {cat}")
    return "\n".join(lines)


def _render_profile_yahoo(p: dict) -> str:
    market_label = "港股" if p.get("market") == "hk" else "美股"
    lines = [f"# {p.get('name', '')} ({p.get('code', '')}) {market_label}基本信息", ""]
    sector = p.get("sector")
    if sector:
        lines.append(f"行业: {sector}")
    industry = p.get("industry")
    if industry:
        lines.append(f"细分: {industry}")
    desc = p.get("description")
    if desc:
        lines.append("")
        lines.append("## 公司概况")
        lines.append(desc[:1000])
    website = p.get("website")
    if website:
        lines.append(f"\n官网: {website}")
    employees = p.get("employees")
    if employees:
        lines.append(f"员工数: {employees:,}")
    notes = p.get("_notes", [])
    if notes:
        lines.append("")
        for n in notes:
            lines.append(f"- {n}")
    return "\n".join(lines)


def _render_financial(p: dict) -> str:
    lines = [f"# {p.get('code', '')} 财务指标", ""]
    ths = p.get("ths_financial")
    if ths:
        lines.append("## 同花顺主要指标")
        for key, val in list(ths.items())[:20]:
            if val is not None:
                lines.append(f"- {key}: {val}")
        lines.append("")
    sina = p.get("sina_financial")
    if sina:
        lines.append("## 新浪财务数据")
        for key, val in list(sina.items())[:15]:
            if val is not None:
                lines.append(f"- {key}: {val}")
        lines.append("")
    return "\n".join(lines)


def _render_description(p: dict) -> str:
    lines = [f"# {p.get('code', '')} 公司概况", ""]
    desc = p.get("description")
    if desc:
        lines.append(desc)
    else:
        lines.append("未获取到公司概况信息")
    return "\n".join(lines)


def _render_announcements(p: dict) -> str:
    lines = [f"# {p.get('code', '')} 最新公告", ""]
    anns = p.get("announcements", [])
    if not anns:
        lines.append("暂无公告数据")
    for a in anns:
        title = a.get("标题") or a.get("title", "")
        date = a.get("公告日期") or a.get("date", "")
        lines.append(f"- [{date}] {title}")
    return "\n".join(lines)


def _render_relations(p: dict) -> str:
    lines = [f"# {p.get('code', '')} 关联个股", ""]
    rels = p.get("relations", [])
    if not rels:
        lines.append("暂无关联数据")
    for r in rels:
        code_val = r.get("代码") or r.get("code", "")
        name = r.get("名称") or r.get("name", "")
        lines.append(f"- {code_val} {name}")
    return "\n".join(lines)


# 渲染分派表
_RENDERERS = {
    "snapshot_a": _render_snapshot_a,
    "snapshot_etf": _render_snapshot_etf,
    "snapshot_yahoo": _render_snapshot_yahoo,
    "daily_a": _render_daily_a,
    "daily_yahoo": _render_daily_yahoo,
    "profile_a": _render_profile_a,
    "profile_etf": _render_profile_etf,
    "profile_yahoo": _render_profile_yahoo,
    "financial": _render_financial,
    "description": _render_description,
    "announcements": _render_announcements,
    "relations": _render_relations,
}
