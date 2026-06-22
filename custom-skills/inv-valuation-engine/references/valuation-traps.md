# 估值常见陷阱

## 数据层陷阱（inv-stock-data 负责校验，本技能负责使用侧防护）

- **Yahoo earningsGrowth 严重失真**：Yahoo Finance 的 `earningsGrowth` 是最近一个季度的 GAAP 同比增速，对持有大量股权投资的公司（如阿里巴巴、腾讯、美团）会产生极端值（实测出现过 -70.9%），因为投资公允价值变动会剧烈影响单季 GAAP 净利润。**绝对不能将此字段直接用作"未来 2-3 年利润增速假设"**。正确做法：用 Normalized/Non-GAAP 净利润的多年复合增速，或手动从年度财报计算。若脚本自动输出了基于此字段的增速假设，必须在最终报告中明确修正并说明原因。
- **Forward PE口径不一致**：Yahoo Finance 对港股互联网公司的 `forwardPE` 可能基于 Non-GAAP 口径，与 TTM PE（GAAP）不可直接比较。必须做增速常识校验。
- **A+H 双上市 Forward PE 失真**：福耀玻璃等 A+H 双上市公司的 Yahoo Forward PE 可能基于 Non-GAAP/调整后 EPS（剔除汇兑损失等一次性项），而 Trailing PE 基于 GAAP（含汇兑损失），导致隐含增速虚高（实测福耀出现过隐含33%增速，实际一致预期增速仅4-5%）。校验方法：用一致预期 EPS 手算 Forward PE = 当前价/一致预期EPS，与 Yahoo Forward PE 对比；若差异大，以手算为准并标注口径差异。
- **inv-stock-data snapshot 对美股/港股可能返回空**：`cs_stock_info.py snapshot` 对部分美股/港股可能返回"所有数据源均不可用"，但 `financial` 子命令仍可工作。降级方案：用 inv-stock-data `financials` 子命令获取财务三表数据，再按本技能框架手动计算。
- **财务数据年份排序陷阱**：`cs_stock_info.py all` 返回的 `financials` 子命令数据（利润表/资产负债表/现金流量表）按**最新年份在前**排列（如 2025→2024→2023→2022）。在用循环计算 YoY 增速时，若误按返回顺序遍历，可能出现负增长假象。实测案例：药明生物(02269.HK)首次计算时因排序错误输出了"2024营收同比-14.3%"（实际应为+9.6%）。**正确做法**：先按日期正序排列再计算 YoY，或在代码中显式标注年份标签，计算完成后做常识校验。修复代码模板：
  ```python
  years = sorted(data['financials']['income_stmt'].keys())  # 正序
  for i in range(1, len(years)):
      curr = data['financials']['income_stmt'][years[i]]
      prev = data['financials']['income_stmt'][years[i-1]]
      yoy = (curr - prev) / abs(prev) * 100
      print(f"{years[i]} vs {years[i-1]}: {yoy:+.1f}%")
  ```

## 估值层陷阱（本技能负责）

- **历史PE分位失真**：若历史区间包含异常利润年份（如腾讯2022-2023年受反垄断+投资减值影响利润骤降），PE分位会被扭曲。此时应优先看3年分位或剔除异常年份，并在报告中说明。
- **5年PE分位 vs 3年PE分位**：5年区间若包含极端事件（如2022年中概股暴跌、META从$384跌至$89），分位参考价值下降。应同时报告3年和5年分位，并说明选取依据。52周位置是更可靠的近期估值水平参考——当5年分位>70%但52周位置<40%时，优先采信52周位置
- **AI CapEx 暴增期 FCF 失真**：互联网平台在 AI 投资周期中 CapEx 可跳升至营收 35%+（如 META 2025），导致 FCF/NI 下降。此时 FCF 下降不代表质量恶化，而是投资型支出。应区分维持型 CapEx 与投资型 CapEx，用「经营现金流 - 维持型 CapEx」估算可持续 FCF
- **Normalized Income 增速失真**：当对比基期含一次性投资收益/减值时，Normalized NI 同比增速可能为负但实际经营在改善（如 META 2024→2025 Normalized NI -4.4% 但 Operating Income +20%）。应优先用 Operating Income 增速作为核心增长指标

## 脚本输出陷阱

- **uv run 首次超时**：`uv run scripts/valuation_snapshot.py` 首次运行需下载依赖，可能超时300秒+。降级方案：inv-stock-data `financials` 子命令获取财务三表数据，手动按框架计算。
- **valuation_report.py 增速假设需人工校验**：该脚本可能将 Yahoo 的 `earningsGrowth` 直接填入"未来增速假设"和"核心假设"，导致输出荒谬结论（如"增速维持在 -70.9%"）。运行脚本后，必须检查增速假设是否合理；若不合理，手动替换为基于 Normalized 净利润或一致预期的增速，并在报告中标注修正。
- **valuation_report.py 数据不足时输出极简报告**：当底层 inv-stock-data 数据源大面积失败（如 AkShare hist 返回空、Yahoo 限流），脚本可能仅输出"事件层=0.0→合理"的极简结论，几乎无参考价值。**应对**：若报告仅含1-2个指标且无PE/PB分位、无增速假设、无安全边际计算，应视为脚本失败，降级为手动按本技能估值框架计算，不得将极简结论作为五档判断依据。

## 运行脚本后必做检查清单

1. 检查"未来增速假设"是否等于 `earningsGrowth` 字段——若是，需人工校验合理性
2. 对科技股，增速假设若>40%或<-30%，极可能是 GAAP 单季失真，必须替换为一致预期或自建假设
3. 检查 PEG 计算：PEG = 前瞻PE / 增速假设。若增速假设失真，PEG 随之失真，需重新手算
4. 检查"核心假设"第一节——若写的是"未来2-3年利润增速大致维持在 X% 附近"，而 X% 来自 `earningsGrowth`，必须修正
5. 最终报告中必须标注："脚本原始增速假设为 X%，已修正为 Y%，原因..."

## 极端降级场景

- **美股/港股 inv-stock-data snapshot 大量 data_gaps 时手动补全**：当 `valuation_snapshot.py` 对美股/港股返回 `data_gaps` 列表超过5项（尤其是 `high_52w`、`low_52w`、`analyst_target_price`、`freeCashflow`、`enterpriseValue` 等关键字段缺失），不要直接输出结论。降级补全流程见 `references/us-hk-data-workaround.md`，含 inv-stock-data financials 子命令、手动计算脚本两条补全链路。
- **全端点 blackout（极端情况）**：当 yfinance 所有端点（info/financials/balance_sheet/cash_flow）均因 SSL/RateLimit/Consent 循环失败，且 Playwright 也无法抓取时，要尽可能利用 `inv-stock-data snapshot` 剩余基础字段，然后降级到 **本地研报 PDF 提取 + 手动估值**。具体步骤见 `references/us-hk-data-workaround.md` 「D. 全端点 blackout」章节。关键原则：利润口径必须统一为 Non-GAAP，与 Yahoo GAAP PE 做差异标注；手动计算后必须与 snapshot 中的 `trailing_pe` 做口径校验。
