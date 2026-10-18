# 美股/港股估值数据缺口补全指南

> 适用场景：`valuation_snapshot.py` 对美股/港股返回大量 `data_gaps`（Yahoo 限流、SSL、代理不稳定）。
>
> 边界：所有行情与财务数据只经 `inv-stock-data` 取得，不在本技能或会话里直接 `import yfinance`、`pip install` 或写死代理端口；代理由 `_shared/proxy.py` 自动探测，失败时才用 `--proxy` 手动指定。知识库 PDF 只用 curator 的只读入口。

路径中 `{baseDir}` = 本技能目录，`{stockDir}` = `{baseDir}/../inv-stock-data`，`{researchDir}` = `{baseDir}/../inv-knowledge-curator`。

## 快速判断

先读 `data_gaps` 的 `scope`：`background` 不阻止已核验主估值；未标 scope 或 `core` 的缺口才需要补全。以下字段缺失较多时进入降级链路：

- `high_52w`、`low_52w`、`position_in_52w_range_pct`
- `analyst_target_price`、`analyst_count`
- `freeCashflow`、`enterpriseValue`、`evToEbitda`
- `operatingMargins`、`debtToEquity`

美股/港股与 A 股/ETF 不在同一批处理混跑；连续 Yahoo 请求优先用合并命令 `all`，并限流重试。

## 降级链路（按顺序）

### A. 财务三表：`financials`

Yahoo `info`（quoteSummary）端点常因 SSL 先失败，而三表与历史价格走不同端点，通常仍可用：

```bash
uv run {stockDir}/scripts/cs_stock_info.py financials 0700.HK --output json
```

返回 `income_stmt`、`balance_sheet`、`cash_flow`。字段映射：

| 目标字段 | income_stmt 行 | balance_sheet 行 | cash_flow 行 | 计算方式 |
|----------|---------------|------------------|--------------|----------|
| trailing_pe | Net Income | — | — | price / (Net Income / Diluted Shares)，币种先统一 |
| pb | — | Stockholders Equity | — | price / (Equity / Diluted Shares)，币种先统一 |
| market_cap | — | — | — | price × Diluted Shares |
| roe_pct | Net Income | Stockholders Equity | — | NI / Avg(Equity_t, Equity_t-1) × 100 |
| gross_margin_pct | Gross Profit / Total Revenue | — | — | ×100 |
| operating_margin_pct | Operating Income / Total Revenue | — | — | ×100 |
| net_margin_pct | Net Income / Total Revenue | — | — | ×100 |
| free_cash_flow | — | — | Free Cash Flow | 原值；SBC、租赁口径另核 |
| total_cash | — | Cash Cash Equivalents And Short Term Investments | — | 原值 |
| total_debt | — | Total Debt | — | 原值 |
| shares_outstanding | Diluted Average Shares | — | — | ADR 须换算为每 ADR 股数 |

注意：
- 中概 ADR（如 PDD、BABA）财报币种通常为人民币，价格为美元；PE/PB/市值须先统一币种，并核对 ADR 比例。
- 三表列为日期，取最近一期时按列名而非整数位置定位。
- Yahoo `debtToEquity` 是百分比，不是倍数；stock-data 已输出 `debt_to_equity_ratio`，优先用它。

### B. 价格区间：`daily`

52 周高低与价格位置用日线自行计算，不依赖 `info`：

```bash
uv run {stockDir}/scripts/cs_stock_info.py daily 0700.HK --period 1y --output json
```

取 High 最大值与 Low 最小值。价格位置只描述历史背景，不是估值分位，不映射动作。

### C. 港股/美股实时行情：QQ Finance

Yahoo 全局限流且 snapshot 对港股返回空或严重缺失时，按 `inv-stock-data/references/qq-finance-realtime-api.md` 使用 `qt.gtimg.cn` 补报价、PE、PB、市值和 52 周高低。该源无需代理，但不含 FCF、EV/EBITDA 和分析师目标价；PB 净资产口径可能与 Yahoo 不同，须标注来源。

### D. 稍后重试 `info`

`info` 的 SSL 失败通常是临时的。完成 A–C 后间隔几分钟再运行一次 `snapshot` 或 `all`，补 forwardPE、targetMeanPrice 等只在 `info` 中提供的字段；仍失败则保留缺口。

### E. 全端点失败：快照锚定 + 研报原文

触发特征：`financial` / `profile` 返回 Yahoo 不可用，A–D 均失败，仅剩 snapshot 基础字段（price、daily、pe_trailing、pb、部分 fundamentals）。

1. **用 snapshot 锚定基础事实**：price、currency、sector、daily 及剩余 fundamentals。snapshot 的 `earnings_growth` 对互联网平台常基于 GAAP 单季数据，失真严重，不得直接当增速假设。
2. **从知识库原文提取财务假设**：先 `/km_search` 定位研报，再只读读取：

   ```bash
   uv run {researchDir}/scripts/km_import.py read --file <res/下PDF绝对路径> --pages first-n --first-n 10
   ```

   `--pages edges` 只读首尾页，可识别报告但不足以核验中段表格。提取 Non-GAAP 净利润及增速、一致预期 EPS、分部估值、目标价与其倍数/汇率/摊薄股数假设、关键经营指标，并记录路径、页码和数值。扫描件交 OCR 技能（如 `document-ocr`）。不得调用 `km_import store|res` 写库。
3. **手工计算诊断倍数**：调整后 PE、Forward PE、PEG（用 Non-GAAP 增速）、价格区间位置等，可用 `{baseDir}/scripts/valuation_manual_compute.py` 或会话内算式，输入须逐项标来源。
4. **三情景交主估值协议**：情景必须按 `references/scoring-rules.md` 由经营路径、资本需求、现金分配和退出估值构建，每情景写证伪条件；不得用“卖方利润下限/中位/上限 × 固定 8/10/12 倍 PE”拼三情景，也不得只靠降低退出倍数制造悲观。需要逐年现金流 IRR 或目标回报反推价时交 `inv-value-return`。

## 校验与标注

- **口径一致性**：snapshot `pe_trailing` 通常是 GAAP，手工调整 PE 是 Non-GAAP，必须并列并注明来源，例如“Yahoo PE TTM 10.2x（GAAP）；调整后 9.1x（Non-GAAP，来源：某券商某日研报第 N 页）”。
- **汇率**：不同研报汇率假设不同时，统一为当前汇率或逐一注明。
- **股数**：利润与股数口径一致（普通股 vs ADS），ADR 比例逐项核对。
- **缺失标注**：报告中列明哪些字段来自 snapshot、financials、daily、QQ Finance、研报原文，哪些仍缺失，以及对结论的影响；字段为 None 时标缺口，不用猜测补齐。

## 常见问题

- **YFRateLimitError / 代理不稳定**：交给 stock-data 的自动探测；仍失败时用 `--proxy` 手动指定后重试，或等待几分钟。
- **SSL / Connection reset**：通常只影响 `info`，按 A→B→C→D 顺序降级。
- **Consent 页面循环**：不要用浏览器抓 Yahoo，直接走 C 或 E。
