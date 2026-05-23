# yfinance 高级用法速查（港股/美股深度分析）

> 适用场景：当 `cs_stock_info.py` snapshot/daily/financial 等 CLI 子命令返回不全或触发限流时，直接用 Python `yfinance` API 获取深度数据。

## 1. 环境准备

```bash
# 港股/美股必须设置代理
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890

python3 -c "import yfinance as yf; ..."
```

## 2. ticker.info — 基本面全景

获取字典后，按分析维度提取关键字段：

| 维度 | 推荐字段 | 说明 |
|------|----------|------|
| **行情** | `currentPrice`, `fiftyTwoWeekHigh`, `fiftyTwoWeekLow`, `fiftyDayAverage`, `twoHundredDayAverage` | 当前价、52周高低、均线 |
| **估值** | `trailingPE`, `forwardPE`, `priceToBook`, `priceToSalesTrailing12Months`, `enterpriseToEbitda`, `enterpriseToRevenue` | TTM/前瞻倍数 |
| **质量** | `returnOnEquity`, `returnOnAssets`, `grossMargins`, `operatingMargins`, `profitMargins`, `ebitdaMargins` | ROE/ROA/利润率 |
| **成长** | `revenueGrowth`, `earningsGrowth`, `earningsQuarterlyGrowth` | 增速（注意是YoY） |
| **资本结构** | `totalDebt`, `totalCash`, `debtToEquity`, `currentRatio`, `quickRatio` | 负债与流动性 |
| **股东回报** | `dividendRate`, `dividendYield`, `payoutRatio`, `trailingEps`, `forwardEps` | 分红与EPS |
| **分析师** | `targetMeanPrice`, `targetMedianPrice`, `targetHighPrice`, `targetLowPrice`, `recommendationKey`, `numberOfAnalystOpinions` | 共识目标价与评级 |
| **风险** | `beta` | 系统性风险 |

**注意**：
- `dividendYield` 返回的是小数（如 0.0112 = 1.12%），输出前需 ×100。
- 港股 `info` 中 `marketCap` 单位是**标的币种**（港股为 HKD），但 `totalRevenue`/`netIncome` 等可能为**人民币**（取决于公司披露币种），做市值/收入比时必须统一币种。
- 部分字段可能为 `None`，需做防御性处理。

## 3. ticker.history — K线与历史价格

```python
# 日线（默认）
hist = ticker.history(period='1y')  # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max

# 月线（用于历史估值区间回溯）
hist_monthly = ticker.history(period='5y', interval='1mo')
# interval 可选: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo

# 计算 52 周位置
price = hist['Close'].iloc[-1]
high_52w = hist['High'].max()
low_52w = hist['Low'].min()
position = (price - low_52w) / (high_52w - low_52w)
```

## 4. ticker.income_stmt / balance_sheet / cash_flow — 完整财报

```python
income = ticker.income_stmt   # 利润表（年度，最近5年）
bs = ticker.balance_sheet     # 资产负债表
 cf = ticker.cash_flow       # 现金流量表
```

**返回格式**：DataFrame，列为日期（如 `2025-12-31`），行为科目。

**港股常用科目映射**：

| 分析目的 | 推荐字段（income_stmt） |
|----------|------------------------|
| 核心利润 | `Net Income From Continuing Operation Net Minority Interest` |
| 正常化利润 | `Normalized Income` |
| 收入 | `Total Revenue` 或 `Operating Revenue` |
| 成本 | `Reconciled Cost Of Revenue` |
| 折旧 | `Reconciled Depreciation` |
| EBIT | `EBIT` |
| EBITDA | `EBITDA` / `Normalized EBITDA` |

| 分析目的 | 推荐字段（balance_sheet） |
|----------|------------------------|
| 股东权益 | `Stockholders Equity` |
| 有形净资产 | `Tangible Book Value` |
| 总负债 | `Total Debt` |
| 净负债 | `Net Debt` |
| 现金 | `Cash And Cash Equivalents`（如存在）或从 cash_flow 的 `End Cash Position` 反推 |

| 分析目的 | 推荐字段（cash_flow） |
|----------|------------------------|
| 自由现金流 | `Free Cash Flow` |
| 资本开支 | `Capital Expenditure` |
| 回购 | `Repurchase Of Capital Stock` |
| 分红 | `Cash Dividends Paid` / `Common Stock Dividend Paid` |
| 融资现金流 | `Financing Cash Flow` |

**口径警告**：
- Yahoo 财报数据为**GAAP/IFRS 混合口径**，与报表原文可能有差异（尤其「特别项目」`Total Unusual Items`）。
- 腾讯等港股公司披露币种为**人民币**，但 Yahoo 可能统一转换为**标的交易币种**（HKD），需核对数量级。
- `Normalized Income` 已做特别项目调整，比 GAAP 净利润更适合估值。

## 5. 数据校验要点

拉取 yfinance 财报后，必须做以下校验：

1. **币种一致性**：`marketCap`（HKD）vs `totalRevenue`（可能是 CNY），不能直接相除。
2. **时间对齐**：`income_stmt` 列为年末日期，但 "TTM" 指标（如 `trailingPE`）基于滚动12个月。跨年度比较时注意口径。
3. **异常项目**：检查 `Total Unusual Items` 是否显著，若显著则优先用 `Normalized Income`。
4. **净利润 vs FCF**：`profitMargins` 应与 `Free Cash Flow / Total Revenue` 大致同方向，若背离很大需查 `Capital Expenditure` 是否异常。
5. **PE 双向校验**：`currentPrice / trailingEps` 应与 `trailingPE` 基本一致（误差 <5%），否则有币种或口径问题。

## 6. 限流与降级

- `income_stmt` / `balance_sheet` / `cash_flow` 调用的是 Yahoo 财报 API，与 `history`/`info` 端点独立。
- 若财报 API 返回空，等待 2-3 分钟后重试，或换代理端口。
- **关键降级规则**：当 `info()` 和 `recommendations()` 均因 SSL 错误或限流失败时（实测常见），`financials` 端点往往仍然可用。此时应优先用 `income_stmt` / `balance_sheet` / `cash_flow` 提取所有可能的财务数据，再结合 browser 直抓 Yahoo Finance 分析页面补全分析师预期，最后手动计算估值指标。
- 终极降级：用内置搜索功能搜索公司 IR 网站下载 PDF 年报，走 OCR 技能提取。
