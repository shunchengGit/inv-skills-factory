#!/usr/bin/env python3
"""
手动估值计算脚本 — 用于 cs-stock / yfinance 数据缺口时的补全验证

使用场景：
  1. cs-stock snapshot 返回大量 data_gaps
  2. yfinance info() / recommendations() 因 SSL/限流失败
  3. 需要从 yfinance financials DataFrame 手动计算核心估值指标
  4. 快速三场景估值（悲观/基准/乐观）

依赖：pandas（可选，用于读取 yfinance financials DataFrame）
运行方式：
  python3 valuation_manual_compute.py --ticker PDD --price 98.78 --fx 7.15
  或作为模块导入：from valuation_manual_compute import ValuationEngine
"""

from __future__ import annotations
import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FinancialSnapshot:
    """用户可直接填入的财务快照"""
    price_usd: float
    diluted_shares_b: float           # 亿 ADS
    fx_rate: float = 7.15             # RMB/USD
    # 利润表
    total_revenue: Optional[float] = None      # 亿 RMB
    gross_profit: Optional[float] = None       # 亿 RMB
    operating_income: Optional[float] = None   # 亿 RMB
    net_income_gaap: Optional[float] = None    # 亿 RMB
    net_income_nongaap: Optional[float] = None # 亿 RMB
    diluted_eps_rmb: Optional[float] = None    # RMB/ADS
    # 资产负债表
    stockholders_equity: Optional[float] = None  # 亿 RMB
    stockholders_equity_prev: Optional[float] = None  # 亿 RMB
    total_debt: Optional[float] = None         # 亿 RMB
    total_cash: Optional[float] = None         # 亿 RMB
    short_term_investments: Optional[float] = None  # 亿 RMB
    # 现金流量表
    free_cash_flow: Optional[float] = None     # 亿 RMB
    capital_expenditure: Optional[float] = None  # 亿 RMB
    # 外部一致预期
    analyst_eps_fy1_rmb: Optional[float] = None   # RMB/ADS
    analyst_revenue_fy1_b: Optional[float] = None  # 亿 RMB


@dataclass
class ValuationResult:
    """估值计算结果"""
    pe_ttm_gaap: Optional[float] = None
    pe_ttm_nongaap: Optional[float] = None
    forward_pe_analyst: Optional[float] = None
    pb: Optional[float] = None
    ps_ttm: Optional[float] = None
    price_to_fcf: Optional[float] = None
    roe_pct: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    net_margin_pct: Optional[float] = None
    cash_to_mcap_pct: Optional[float] = None
    market_cap_usd_b: Optional[float] = None
    scenarios: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class ValuationEngine:
    """估值计算引擎"""

    def __init__(self, snap: FinancialSnapshot):
        self.snap = snap
        self.res = ValuationResult()

    def compute(self) -> ValuationResult:
        s = self.snap
        r = self.res

        # 市值
        if s.price_usd and s.diluted_shares_b:
            r.market_cap_usd_b = s.price_usd * s.diluted_shares_b
        else:
            r.warnings.append("缺少 price_usd 或 diluted_shares_b，市值无法计算")

        # PE TTM (GAAP)
        if s.net_income_gaap and s.diluted_shares_b and s.fx_rate:
            eps_usd = (s.net_income_gaap / s.diluted_shares_b) / s.fx_rate
            r.pe_ttm_gaap = s.price_usd / eps_usd
        else:
            r.warnings.append("缺少 GAAP 净利润，无法计算 TTM PE(GAAP)")

        # PE TTM (Non-GAAP)
        if s.net_income_nongaap and s.diluted_shares_b and s.fx_rate:
            eps_usd = (s.net_income_nongaap / s.diluted_shares_b) / s.fx_rate
            r.pe_ttm_nongaap = s.price_usd / eps_usd
        else:
            r.warnings.append("缺少 Non-GAAP 净利润，无法计算 TTM PE(Non-GAAP)")

        # Forward PE (基于分析师 EPS 预期)
        if s.analyst_eps_fy1_rmb and s.diluted_shares_b and s.fx_rate:
            # 注意：部分数据源的 analyst_eps 是 "每ADS的RMB"，部分是 "每股的RMB"
            eps_usd = s.analyst_eps_fy1_rmb / s.fx_rate
            r.forward_pe_analyst = s.price_usd / eps_usd
        else:
            r.warnings.append("缺少分析师 FY1 EPS 预期，无法计算 Forward PE")

        # PB
        if s.stockholders_equity and s.diluted_shares_b and s.fx_rate:
            bvps_usd = (s.stockholders_equity / s.diluted_shares_b) / s.fx_rate
            r.pb = s.price_usd / bvps_usd
        else:
            r.warnings.append("缺少股东权益，无法计算 PB")

        # PS TTM
        if s.total_revenue and r.market_cap_usd_b and s.fx_rate:
            revenue_usd_b = s.total_revenue / s.fx_rate
            r.ps_ttm = r.market_cap_usd_b / revenue_usd_b
        else:
            r.warnings.append("缺少营收，无法计算 PS")

        # Price/FCF
        if s.free_cash_flow and r.market_cap_usd_b and s.fx_rate:
            fcf_usd_b = s.free_cash_flow / s.fx_rate
            r.price_to_fcf = r.market_cap_usd_b / fcf_usd_b
        else:
            r.warnings.append("缺少自由现金流，无法计算 Price/FCF")

        # ROE
        if s.net_income_gaap and s.stockholders_equity:
            if s.stockholders_equity_prev:
                avg_equity = (s.stockholders_equity + s.stockholders_equity_prev) / 2
            else:
                avg_equity = s.stockholders_equity
                r.warnings.append("缺少上期股东权益，ROE 使用单期数据")
            r.roe_pct = (s.net_income_gaap / avg_equity) * 100
        else:
            r.warnings.append("缺少净利润或股东权益，无法计算 ROE")

        # 利润率
        if s.total_revenue:
            if s.gross_profit:
                r.gross_margin_pct = (s.gross_profit / s.total_revenue) * 100
            if s.operating_income:
                r.operating_margin_pct = (s.operating_income / s.total_revenue) * 100
            if s.net_income_gaap:
                r.net_margin_pct = (s.net_income_gaap / s.total_revenue) * 100
        else:
            r.warnings.append("缺少营收，无法计算利润率")

        # 现金占比
        cash = (s.total_cash or 0) + (s.short_term_investments or 0)
        if cash and r.market_cap_usd_b and s.fx_rate:
            cash_usd_b = cash / s.fx_rate
            r.cash_to_mcap_pct = (cash_usd_b / r.market_cap_usd_b) * 100
        else:
            r.warnings.append("缺少现金数据，无法计算现金占比")

        return r

    def compute_scenarios(
        self,
        scenarios: list[tuple[str, float, float]],
    ) -> list[dict]:
        """
        三场景估值计算
        参数: [(name, fy1_profit_rmb_b, pe_multiple), ...]
        """
        s = self.snap
        results = []
        for name, profit, pe in scenarios:
            if not s.diluted_shares_b or not s.fx_rate:
                results.append({
                    "scenario": name,
                    "error": "缺少基础数据，无法计算"
                })
                continue
            eps_usd = (profit / s.diluted_shares_b) / s.fx_rate
            target = eps_usd * pe
            upside = (target / s.price_usd - 1) * 100 if s.price_usd else None
            results.append({
                "scenario": name,
                "fy1_profit_rmb_b": profit,
                "fy1_eps_usd": round(eps_usd, 2),
                "pe_multiple": pe,
                "target_usd": round(target, 0),
                "upside_pct": round(upside, 0) if upside is not None else None,
            })
        self.res.scenarios = results
        return results

    def report(self) -> str:
        r = self.res
        lines = []
        lines.append("───────────────────────────────────────────")
        lines.append("估值快照")
        lines.append("───────────────────────────────────────────")
        lines.append(f"市值:           {r.market_cap_usd_b:.0f}亿 USD" if r.market_cap_usd_b else "市值:           缺少数据")
        lines.append(f"PE (TTM, GAAP):   {r.pe_ttm_gaap:.1f}x" if r.pe_ttm_gaap else "PE (TTM, GAAP):   缺少数据")
        lines.append(f"PE (TTM, Non-GAAP): {r.pe_ttm_nongaap:.1f}x" if r.pe_ttm_nongaap else "PE (TTM, Non-GAAP): 缺少数据")
        lines.append(f"Forward PE:       {r.forward_pe_analyst:.1f}x" if r.forward_pe_analyst else "Forward PE:       缺少数据")
        lines.append(f"PB:               {r.pb:.2f}x" if r.pb else "PB:               缺少数据")
        lines.append(f"PS (TTM):         {r.ps_ttm:.1f}x" if r.ps_ttm else "PS (TTM):         缺少数据")
        lines.append(f"Price/FCF:        {r.price_to_fcf:.1f}x" if r.price_to_fcf else "Price/FCF:        缺少数据")
        lines.append(f"ROE:              {r.roe_pct:.1f}%" if r.roe_pct else "ROE:              缺少数据")
        lines.append(f"毛利率:           {r.gross_margin_pct:.1f}%" if r.gross_margin_pct else "毛利率:           缺少数据")
        lines.append(f"经营利润率:       {r.operating_margin_pct:.1f}%" if r.operating_margin_pct else "经营利润率:       缺少数据")
        lines.append(f"净利润率:         {r.net_margin_pct:.1f}%" if r.net_margin_pct else "净利润率:         缺少数据")
        lines.append(f"现金占市值比:     {r.cash_to_mcap_pct:.0f}%" if r.cash_to_mcap_pct else "现金占市值比:     缺少数据")

        if r.scenarios:
            lines.append("")
            lines.append("三场景估值")
            lines.append("───────────────────────────────────────────")
            for sc in r.scenarios:
                if "error" in sc:
                    lines.append(f"{sc['scenario']}: {sc['error']}")
                else:
                    lines.append(
                        f"{sc['scenario']}: FY1利润={sc['fy1_profit_rmb_b']:.0f}亿, "
                        f"EPS={sc['fy1_eps_usd']:.2f}USD, "
                        f"PE={sc['pe_multiple']}x, "
                        f"目标价={sc['target_usd']:.0f}USD, "
                        f"上行空间={sc['upside_pct']:+.0f}%"
                    )

        if r.warnings:
            lines.append("")
            lines.append("警告")
            lines.append("───────────────────────────────────────────")
            for w in r.warnings:
                lines.append(f"• {w}")

        return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="手动估值计算脚本")
    p.add_argument("--price", type=float, required=True, help="当前股价 USD")
    p.add_argument("--shares", type=float, required=True, help="沾薄ADS总股本 (亿)")
    p.add_argument("--fx", type=float, default=7.15, help="人民币/美元汇率")
    p.add_argument("--ni-gaap", type=float, help="GAAP 净利润 (亿RMB)")
    p.add_argument("--ni-nongaap", type=float, help="Non-GAAP 净利润 (亿RMB)")
    p.add_argument("--eps-fy1", type=float, help="分析师 FY1 EPS (每ADS的RMB)")
    p.add_argument("--equity", type=float, help="股东权益 (亿RMB)")
    p.add_argument("--equity-prev", type=float, help="上期股东权益 (亿RMB)")
    p.add_argument("--revenue", type=float, help="营收 (亿RMB)")
    p.add_argument("--gross-profit", type=float, help="毛利 (亿RMB)")
    p.add_argument("--op-income", type=float, help="经营利润 (亿RMB)")
    p.add_argument("--fcf", type=float, help="自由现金流 (亿RMB)")
    p.add_argument("--cash", type=float, help="现金 (亿RMB)")
    p.add_argument("--investments", type=float, help="短期投资 (亿RMB)")
    p.add_argument("--debt", type=float, help="总债务 (亿RMB)")
    p.add_argument("--scenario-profit", type=str, help="三场景利润,格式: 悲观,1127,8|基准,1300,10|乐观,1500,12")
    p.add_argument("--json", action="store_true", help="输出 JSON 格式")
    return p.parse_args()


def main():
    args = parse_args()

    snap = FinancialSnapshot(
        price_usd=args.price,
        diluted_shares_b=args.shares,
        fx_rate=args.fx,
        net_income_gaap=args.ni_gaap,
        net_income_nongaap=args.ni_nongaap,
        analyst_eps_fy1_rmb=args.eps_fy1,
        stockholders_equity=args.equity,
        stockholders_equity_prev=args.equity_prev,
        total_revenue=args.revenue,
        gross_profit=args.gross_profit,
        operating_income=args.op_income,
        free_cash_flow=args.fcf,
        total_cash=args.cash,
        short_term_investments=args.investments,
        total_debt=args.debt,
    )

    engine = ValuationEngine(snap)
    engine.compute()

    if args.scenario_profit:
        scenarios = []
        for part in args.scenario_profit.split("|"):
            name, profit, pe = part.split(",")
            scenarios.append((name, float(profit), float(pe)))
        engine.compute_scenarios(scenarios)

    if args.json:
        out = {
            "price_usd": args.price,
            "fx_rate": args.fx,
            "market_cap_usd_b": engine.res.market_cap_usd_b,
            "pe_ttm_gaap": engine.res.pe_ttm_gaap,
            "pe_ttm_nongaap": engine.res.pe_ttm_nongaap,
            "forward_pe": engine.res.forward_pe_analyst,
            "pb": engine.res.pb,
            "ps_ttm": engine.res.ps_ttm,
            "price_to_fcf": engine.res.price_to_fcf,
            "roe_pct": engine.res.roe_pct,
            "gross_margin_pct": engine.res.gross_margin_pct,
            "operating_margin_pct": engine.res.operating_margin_pct,
            "net_margin_pct": engine.res.net_margin_pct,
            "cash_to_mcap_pct": engine.res.cash_to_mcap_pct,
            "scenarios": engine.res.scenarios,
            "warnings": engine.res.warnings,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(engine.report())


if __name__ == "__main__":
    main()
