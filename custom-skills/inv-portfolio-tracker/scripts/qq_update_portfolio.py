#!/usr/bin/env python3
"""
QQ Finance 持仓更新脚本
读取 PORTFOLIO.md，通过 QQ Finance API 获取实时行情，计算并输出更新后的持仓数据。

用法:
  python update_portfolio.py                    # 输出更新后的持仓（stdout）
  python update_portfolio.py --write             # 直接写回 PORTFOLIO.md
  python update_portfolio.py --json              # JSON 格式输出
  python update_portfolio.py --check             # 仅检查数据可用性
"""

import re
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("需要安装 requests: pip install requests", file=sys.stderr)
    sys.exit(1)

# ========== 配置 ==========
PORTFOLIO_PATH = Path.home() / ".hermes" / "memories" / "PORTFOLIO.md"
USER_PATH = Path.home() / ".hermes" / "memories" / "USER.md"

# QQ Finance 市场前缀映射
MARKET_PREFIX = {
    "A": "sh",      # A股上证默认 sh，深证需手动 sz
    "HK": "hk",
    "US": "us",
}

# 深圳股票代码前缀（需用 sz 而非 sh）
SZ_PREFIXES = ("000", "001", "002", "003", "004", "300", "301")

# 字段索引（已验证）
FIELD_MAP = {
    "A": {   # market=1, 88 fields
        "price": 3, "prev_close": 4, "change_pct": 32,
        "day_high": 33, "day_low": 34,
        "year_high": 47, "year_low": 48,
        "pe_ttm": 52, "pe_static": 53,
    },
    "HK": {  # market=100, 78 fields
        "price": 3, "prev_close": 4, "change_pct": 32,
        "day_high": 33, "day_low": 34,
        "pe": 39,
        "high_52w": 48, "low_52w": 49,
    },
    "US": {  # market=200, 71 fields
        "price": 3, "prev_close": 4, "change_pct": 32,
        "day_high": 33, "day_low": 34,
        "pe": 39,
        "high_52w": 48, "low_52w": 49,
    },
}


def load_constraints() -> dict:
    """从 USER.md 读取组合约束；缺失时回退到当前默认。"""
    constraints = {
        "max_single_pct": 40,
        "max_sector_pct": 55,
        "min_cash_pct": 2,
        "cash_target_low": 5,
        "cash_target_high": 10,
    }
    if not USER_PATH.exists():
        return constraints

    content = USER_PATH.read_text(encoding="utf-8")
    m = re.search(r"单只股票仓位上限[:：]\s*`?<=?\s*([\d.]+)%?", content)
    if m:
        constraints["max_single_pct"] = float(m.group(1))
    m = re.search(r"单一行业集中度[:：]\s*`?<=?\s*([\d.]+)%?", content)
    if m:
        constraints["max_sector_pct"] = float(m.group(1))
    m = re.search(r"现金[^\n]*?>=\s*([\d.]+)%", content)
    if m:
        constraints["min_cash_pct"] = float(m.group(1))
    m = re.search(r"([\d.]+)\s*-\s*([\d.]+)%", content)
    if m:
        constraints["cash_target_low"] = float(m.group(1))
        constraints["cash_target_high"] = float(m.group(2))
    return constraints


def get_qq_code(code: str, market: str) -> str:
    """将持仓代码转为 QQ Finance 查询代码"""
    code = code.replace(".HK", "").replace(".SS", "").replace(".SZ", "")
    if market == "A":
        if code.startswith(SZ_PREFIXES):
            return f"sz{code}"
        return f"sh{code}"
    elif market == "HK":
        # 港股需要 5 位代码
        return f"hk{int(code):05d}"
    elif market == "US":
        return f"us{code}"
    return code


def parse_portfolio(filepath: Path) -> dict:
    """解析 PORTFOLIO.md，提取持仓配置和元数据"""
    if not filepath.exists():
        raise FileNotFoundError(f"PORTFOLIO.md 不存在: {filepath}")

    content = filepath.read_text(encoding="utf-8")

    # 提取汇率
    usd_cny = 6.77
    hkd_cny = 0.863
    m = re.search(r"USD/CNY\s*=\s*([\d.]+)", content)
    if m:
        usd_cny = float(m.group(1))
    m = re.search(r"HKD/CNY\s*=\s*([\d.]+)", content)
    if m:
        hkd_cny = float(m.group(1))

    # 提取现金（支持负数）
    cash_hkd = 0
    cash_cny = 0
    cash_usd = 0
    m = re.search(r"港币现金.*?(-?[\d,]+)\s*HKD", content)
    if m:
        cash_hkd = float(m.group(1).replace(",", ""))
    m = re.search(r"人民币现金.*?([\d.]+)万?\s*CNY", content)
    if m:
        cash_cny = float(m.group(1))
        if "万" in content[m.start():m.end()]:
            cash_cny *= 10000
    m = re.search(r"美元现金.*?([\d,]+)", content)
    if m:
        cash_usd = float(m.group(1).replace(",", ""))

    # 提取持仓表行（适配双竖线 || 格式）
    holdings = []
    in_table = False
    for line in content.split("\n"):
        if "标的 |" in line and "代码 |" in line:
            in_table = True
            continue
        if in_table and "---|---" in line:
            continue
        if in_table and ("现金" in line and ("—" in line or "CNY" in line)):
            in_table = False
            continue

        if in_table and "|" in line:
            # 去掉行首连续的 |，然后按 | 分割
            cleaned = re.sub(r'^\|+', '', line)
            parts = [p.strip() for p in cleaned.split("|")]
            # 过滤空字符串
            parts = [p for p in parts if p]

            if len(parts) >= 10 and parts[0] not in ("标的", "—"):
                try:
                    # 字段索引: 0=标的, 1=代码, 2=市场, 3=板块, 4=股数, 5=价格, 6=币种, 7=市值, 8=仓位, 9=PE, 10=52w位, 11=风险, 12=备注
                    name = parts[0].replace("**", "").strip()
                    code = parts[1].replace("**", "").strip()
                    market = parts[2].replace("**", "").strip()
                    sector = parts[3].replace("**", "").strip()
                    shares_str = parts[4].replace("**", "").replace("*", "").replace(",", "").replace("HK$", "").replace("$", "").strip()
                    shares = float(shares_str) if shares_str else 0
                    risk = parts[11] if len(parts) > 11 else ""
                    notes = parts[12] if len(parts) > 12 else ""
                    holdings.append({
                        "name": name,
                        "code": code,
                        "market": market,
                        "sector": sector,
                        "shares": shares,
                        "risk": risk,
                        "notes": notes,
                    })
                except (ValueError, IndexError) as e:
                    pass

    return {
        "usd_cny": usd_cny,
        "hkd_cny": hkd_cny,
        "cash_hkd": cash_hkd,
        "cash_cny": cash_cny,
        "cash_usd": cash_usd,
        "holdings": holdings,
        "raw_content": content,
    }


def fetch_qq_data(holdings: list) -> dict:
    """通过 QQ Finance API 批量获取行情"""
    qq_codes = []
    for h in holdings:
        qq_codes.append(get_qq_code(h["code"], h["market"]))

    url = "https://qt.gtimg.cn/q=" + ",".join(qq_codes)
    resp = requests.get(url, timeout=15)
    resp.encoding = "gb2312"
    text = resp.text

    results = {}
    for line in text.strip().split(";"):
        line = line.strip()
        if not line or "=\"" not in line:
            continue
        var_name, data = line.split("=\"")
        name_key = var_name.replace("v_", "")
        fields = data.split("~")

        # 匹配到持仓
        for h in holdings:
            qq_code = get_qq_code(h["code"], h["market"])
            if name_key == qq_code or name_key.endswith(qq_code):
                market = h["market"]
                fm = FIELD_MAP[market]
                try:
                    price = float(fields[fm["price"]])
                    prev_close = float(fields[fm["prev_close"]])
                    change_pct = float(fields[fm["change_pct"]])

                    if market == "A":
                        high_52w = float(fields[fm["year_high"]]) if fields[fm["year_high"]] else 0
                        low_52w = float(fields[fm["year_low"]]) if fields[fm["year_low"]] else 0
                        pe_static = float(fields[fm["pe_static"]]) if len(fields) > fm["pe_static"] and fields[fm["pe_static"]] else None
                        pe_ttm = float(fields[fm["pe_ttm"]]) if len(fields) > fm["pe_ttm"] and fields[fm["pe_ttm"]] else None
                        source_note = "年内高/低"
                    else:
                        high_52w = float(fields[fm["high_52w"]]) if fields[fm["high_52w"]] else 0
                        low_52w = float(fields[fm["low_52w"]]) if fields[fm["low_52w"]] else 0
                        pe = float(fields[fm["pe"]]) if len(fields) > fm["pe"] and fields[fm["pe"]] else None
                        pe_static = None
                        pe_ttm = pe
                        source_note = "52周"

                    # 52周位置
                    if high_52w > low_52w > 0:
                        pos_52w = round((price - low_52w) / (high_52w - low_52w) * 100)
                    else:
                        pos_52w = 0

                    results[h["name"]] = {
                        "price": price,
                        "prev_close": prev_close,
                        "change_pct": change_pct,
                        "high_52w": high_52w,
                        "low_52w": low_52w,
                        "pos_52w": pos_52w,
                        "pe_static": pe_static,
                        "pe_ttm": pe_ttm,
                        "source_note": source_note,
                    }
                except (ValueError, IndexError) as e:
                    print(f"⚠️ 解析 {h['name']} 失败: {e}", file=sys.stderr)
                    results[h["name"]] = None
                break

    return results


def calculate(portfolio: dict, market_data: dict) -> dict:
    """计算市值、仓位、行业集中度"""
    usd_cny = portfolio["usd_cny"]
    hkd_cny = portfolio["hkd_cny"]

    results = []
    for h in portfolio["holdings"]:
        md = market_data.get(h["name"])
        if md is None:
            continue

        # 市值（万CNY）
        if h["market"] == "A":
            value = h["shares"] * md["price"] / 10000
        elif h["market"] == "HK":
            value = h["shares"] * md["price"] * hkd_cny / 10000
        elif h["market"] == "US":
            value = h["shares"] * md["price"] * usd_cny / 10000
        else:
            value = 0

        results.append({**h, **md, "value_wan": round(value, 2)})

    # 现金
    cash_value = (
        portfolio["cash_hkd"] * hkd_cny / 10000
        + portfolio["cash_cny"] / 10000
        + portfolio["cash_usd"] * usd_cny / 10000
    )

    total_stock = sum(r["value_wan"] for r in results)
    total_assets = total_stock + cash_value

    # 仓位%
    for r in results:
        r["position_pct"] = round(r["value_wan"] / total_assets * 100, 1)

    # 行业集中度
    sector_map = {
        "半导体/电子制造": ["半导体制造", "杠杆ETF/半导体", "ETF/科创板"],
        "软件/互联网平台": ["互联网平台", "软件与服务", "ETF/科技指数"],
        "汽车零部件": ["汽车零部件"],
    }

    sectors = {}
    for sector_name, sector_tags in sector_map.items():
        pct = sum(r["position_pct"] for r in results if r["sector"] in sector_tags)
        sectors[sector_name] = round(pct, 1)

    return {
        "holdings": results,
        "total_assets": round(total_assets, 2),
        "total_stock": round(total_stock, 2),
        "cash_value": round(cash_value, 2),
        "cash_pct": round(cash_value / total_assets * 100, 1),
        "sectors": sectors,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def format_pe(holding: dict) -> str:
    """格式化 PE 显示"""
    pe_s = holding.get("pe_static")
    pe_t = holding.get("pe_ttm")
    if pe_s and pe_t:
        return f"{pe_s}(静)/{pe_t}(TTM)"
    elif pe_s:
        return f"{pe_s}(静)"
    elif pe_t:
        return f"{pe_t}(TTM)"
    return "—"


def generate_portfolio_md(calc: dict, portfolio: dict, constraints=None) -> str:
    constraints = constraints or load_constraints()
    """生成更新后的 PORTFOLIO.md 当前持仓部分"""
    lines = []
    lines.append("## 当前持仓\n")
    lines.append(f"- **行情数据截至**：{calc['timestamp']}（QQ Finance 实时行情）")
    lines.append("- **数据来源**：QQ Finance API（qt.gtimg.cn）")
    lines.append(f"- **汇率**：USD/CNY={portfolio['usd_cny']}，HKD/CNY={portfolio['hkd_cny']}")
    lines.append(f"- **总资产**：**{calc['total_assets']} 万元**")
    lines.append(f"- **现金**：**{calc['cash_value']} 万元（{calc['cash_pct']}%）**")
    # 港币现金支持负数显示
    hkd_cash = portfolio['cash_hkd']
    hkd_cny_val = hkd_cash * portfolio['hkd_cny'] / 10000
    lines.append(f"  - 港币现金：**{int(hkd_cash):,} HKD**（约 **{hkd_cny_val:.2f}万 CNY**）")
    lines.append(f"  - 人民币现金：**{portfolio['cash_cny'] / 10000:.2f}万 CNY**")
    lines.append(f"  - 美元现金：**{int(portfolio['cash_usd'])}**")
    lines.append(f"- **现金建议区间**：{constraints['cash_target_low']:.0f}-{constraints['cash_target_high']:.0f}% {'✅ 合理区间' if constraints['cash_target_low'] <= calc['cash_pct'] <= constraints['cash_target_high'] else '⚠️ 需调整'}\n")

    # 表头
    lines.append("| 标的 | 代码 | 市场 | 板块 | 股数 | 价格 | 币种 | 市值(万CNY) | 仓位 | PE | 52w位 | 核心风险 | 备注 |")
    lines.append("|------|------|------|------|------|------|------|------------|------|-----|-------|---------|------|")

    for r in calc["holdings"]:
        price_str = f"**{r['price']}**"
        value_str = f"**{r['value_wan']}**"
        pct_str = f"**{r['position_pct']}%**"
        pe_str = format_pe(r)
        pos_str = f"{r['pos_52w']}%"
        change_str = f"{r['change_pct']:+.2f}%"

        if r["market"] == "HK":
            currency = "HKD"
            price_display = f"**HK${r['price']}**"
        elif r["market"] == "US":
            currency = "USD"
            price_display = f"**${r['price']}**"
        else:
            currency = "CNY"
            price_display = price_str

        # 52周位置标注
        if r["pos_52w"] >= 90:
            pos_tag = "🔴"
        elif r["pos_52w"] >= 70:
            pos_tag = "🟡"
        else:
            pos_tag = ""

        notes = f"{calc['timestamp'].split()[0]} {'盘中' if 'US' in r['market'] else '收盘'}{change_str}；{r['source_note']}:{r['low_52w']}-{r['high_52w']}"

        shares_display = f"**{int(r['shares']):,}**" if r['shares'] == int(r['shares']) else f"**{r['shares']}**"

        lines.append(
            f"| {r['name']} | {r['code']} | {r['market']} | {r['sector']} | "
            f"{shares_display} | {price_display} | {currency} | "
            f"{value_str} | {pct_str} | {pe_str} | "
            f"{pos_str}{pos_tag} | {r['risk']} | {notes} |"
        )

    # 现金行
    cash_pct_str = f"**{calc['cash_pct']}%**"
    lines.append(
        f"| 现金 | — | — | — | — | — | CNY | "
        f"**{calc['cash_value']}** | {cash_pct_str} | — | — | — | "
        f"{'✅' + format(constraints['cash_target_low'], '.0f') + '-' + format(constraints['cash_target_high'], '.0f') + '%合理区间' if constraints['cash_target_low'] <= calc['cash_pct'] <= constraints['cash_target_high'] else '⚠️需调整'} |"
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="QQ Finance 持仓更新")
    parser.add_argument("--write", action="store_true", help="写回 PORTFOLIO.md")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--check", action="store_true", help="仅检查数据可用性")
    parser.add_argument("--portfolio", type=str, default=str(PORTFOLIO_PATH), help="PORTFOLIO.md 路径")
    args = parser.parse_args()

    portfolio_path = Path(args.portfolio)

    # 1. 解析持仓
    try:
        portfolio = parse_portfolio(portfolio_path)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    if not portfolio["holdings"]:
        print("❌ 未解析到任何持仓", file=sys.stderr)
        sys.exit(1)

    print(f"📊 解析到 {len(portfolio['holdings'])} 个持仓标的", file=sys.stderr)

    # 2. 获取行情
    print("📡 拉取 QQ Finance 行情...", file=sys.stderr)
    market_data = fetch_qq_data(portfolio["holdings"])

    # 检查数据完整性
    missing = [h["name"] for h in portfolio["holdings"] if market_data.get(h["name"]) is None]
    if missing:
        print(f"⚠️ 以下标的数据缺失: {', '.join(missing)}", file=sys.stderr)

    if args.check:
        for name, md in market_data.items():
            if md:
                print(f"✅ {name}: {md['price']} (PE={format_pe(md)}, 52w位={md['pos_52w']}%)")
            else:
                print(f"❌ {name}: 数据缺失")
        return

    # 3. 计算
    calc = calculate(portfolio, market_data)

    # 4. 输出 / 写回
    if args.write:
        # 生成内容并写回 PORTFOLIO.md
        constraints = load_constraints()
        md_content = generate_portfolio_md(calc, portfolio, constraints)
        original = portfolio_path.read_text(encoding="utf-8")
        
        # 替换「当前持仓」section
        section_start = original.find("## 当前持仓")
        if section_start == -1:
            print("❌ 未找到「当前持仓」section", file=sys.stderr)
            sys.exit(1)
        sep = original.find("\n---\n", section_start + 10)
        next_section = original.find("\n## ", section_start + 10)
        if sep != -1 and (next_section == -1 or sep < next_section):
            header_end = original.find("\n", section_start)
            body = md_content.replace("## 当前持仓\n\n", "", 1)
            updated = original[:header_end + 1] + body + "\n" + original[sep:]
        else:
            updated = original[:section_start] + md_content + "\n" + original[next_section:]
        
        # 替换「纪律检查」
        disc_start = updated.find("## 纪律检查")
        disc_end = updated.find("\n## ", disc_start + 10) if disc_start != -1 else -1
        if disc_end == -1 and disc_start != -1:
            disc_end = updated.find("\n---\n", disc_start + 10)
        if disc_start != -1 and disc_end != -1:
            disc_lines = ["## 纪律检查\n"]
            max_pos = max(calc["holdings"], key=lambda x: x["position_pct"])
            disc_lines.append(f"- 单只上限 `<= {constraints['max_single_pct']:.0f}%`：{max_pos['name']} {max_pos['position_pct']}% {'✅' if max_pos['position_pct'] <= constraints['max_single_pct'] else '❌超限'}")
            disc_lines.append(f"- 现金 `>= {constraints['min_cash_pct']:.0f}%`：**当前 {calc['cash_pct']}%，{'%s-%s%%合理区间' % (constraints['cash_target_low'], constraints['cash_target_high']) if constraints['cash_target_low'] <= calc['cash_pct'] <= constraints['cash_target_high'] else '⚠️需调整'}** {'✅' if calc['cash_pct'] >= constraints['min_cash_pct'] else '❌不足'}")
            disc_lines.append(f"- 行业集中度 `<= {constraints['max_sector_pct']:.0f}%`：")
            for sector_name, pct in calc["sectors"].items():
                disc_lines.append(f"  - {sector_name}：**{pct}%** {'✅' if pct <= constraints['max_sector_pct'] else '❌超限'}")
            updated = updated[:disc_start] + "\n".join(disc_lines) + "\n" + updated[disc_end:]
        
        # 替换「数据缺口说明」
        gap_start = updated.find("## 数据缺口说明")
        gap_end = updated.find("\n## ", gap_start + 10) if gap_start != -1 else -1
        if gap_end == -1 and gap_start != -1:
            gap_end = updated.find("\n---\n", gap_start + 10)
        if gap_end == -1 and gap_start != -1:
            gap_end = len(updated)
        if gap_start != -1:
            gap_lines = ["## 数据缺口说明\n"]
            for r in calc["holdings"]:
                pe_str = format_pe(r)
                market_status = "盘中" if r["market"] == "US" else "收盘"
                gap_lines.append(
                    f"- **{r['name']} {r['code']}**：{calc['timestamp'].split()[0]} {market_status} "
                    f"{r['price']}（{r['change_pct']:+.2f}%）；PE={pe_str}；"
                    f"{r['source_note']}位{r['pos_52w']}%（{r['low_52w']}-{r['high_52w']}）；"
                    f"仓位{r['position_pct']}%"
                )
            updated = updated[:gap_start] + "\n".join(gap_lines) + "\n" + updated[gap_end:]
        
        # 更新时间戳
        updated = re.sub(r"\*\*行情数据截至\*\*：[^\n]+", f"**行情数据截至**：{calc['timestamp']}（QQ Finance）", updated)
        updated = re.sub(r"\*\*数据来源\*\*：[^\n]+", f"**数据来源**：QQ Finance API（qt.gtimg.cn）", updated)
        
        portfolio_path.write_text(updated, encoding="utf-8")
        print(f"✅ 已更新 {portfolio_path}", file=sys.stderr)
        print(f"   总资产: {calc['total_assets']}万 | 现金: {calc['cash_value']}万({calc['cash_pct']}%)", file=sys.stderr)
        for r in calc["holdings"]:
            print(f"   {r['name']}: {int(r['shares'])}股 × {r['price']} = {r['value_wan']}万 ({r['change_pct']:+.2f}%) | PE={format_pe(r)} | 52w位={r['pos_52w']}%", file=sys.stderr)
        return

    if args.json:
        print(json.dumps(calc, ensure_ascii=False, indent=2))
    else:
        constraints = load_constraints()
        md_content = generate_portfolio_md(calc, portfolio, constraints)
        print(md_content)

        # 行业集中度
        print("\n## 行业集中度")
        for sector_name, pct in calc["sectors"].items():
            print(f"- {sector_name}：**{pct}%**")

        # 纪律检查
        print("\n## 纪律检查")
        max_pos = max(calc["holdings"], key=lambda x: x["position_pct"])
        print(f"- 单只上限 <={constraints['max_single_pct']:.0f}%：{max_pos['name']} {max_pos['position_pct']}% {'✅' if max_pos['position_pct'] <= constraints['max_single_pct'] else '⚠️超限'}")
        print(f"- 现金 >={constraints['min_cash_pct']:.0f}%：{calc['cash_pct']}% {'✅' if calc['cash_pct'] >= constraints['min_cash_pct'] else '⚠️不足'}")
        for sector_name, pct in calc["sectors"].items():
            print(f"- {sector_name} <={constraints['max_sector_pct']:.0f}%：{pct}% {'✅' if pct <= constraints['max_sector_pct'] else '⚠️超限'}")


if __name__ == "__main__":
    main()
