# 美股/港股估值数据缺口手动补全指南

> 适用场景：`inv-stock-data` 或 `valuation_snapshot.py` 对美股/港股返回大量 `data_gaps`（Yahoo Finance 限流/代理不稳定）

## 快速判断

当 `valuation_snapshot.py --output json` 返回的 `data_gaps` 列表包含以下任何5项以上，必须手动补全：
- `high_52w`, `low_52w`, `position_in_52w_range_pct`
- `analyst_target_price`, `analyst_count`
- `freeCashflow`, `enterpriseValue`, `evToEbitda`
- `operatingMargins`, `debtToEquity`

## 降级步骤

### Step 1: 确保 yfinance 可用

```bash
# 检查是否已安装
python3 -c "import yfinance; print(yfinance.__version__)" 2>/dev/null || pip install yfinance

# 如果系统 Python 没有，用之前的 venv
/tmp/research-pdf-venv/bin/pip install yfinance 2>/dev/null || true
```

### Step 2: 用 yfinance 补全关键字段

```python
import yfinance as yf
import os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'

t = yf.Ticker('TSM')  # 替换为目标代码
info = t.info

# 必取字段列表
fields = [
    'enterpriseValue','totalDebt','totalCash','sharesOutstanding',
    'targetMeanPrice','targetHighPrice','targetLowPrice',
    'numberOfAnalystOpinions','beta','fiftyTwoWeekHigh','fiftyTwoWeekLow',
    'operatingMargins','debtToEquity','freeCashflow','evToEbitda',
    'trailingEps','forwardEps'
]
for f in fields:
    v = info.get(f)
    print(f'{f}: {v}')
```

### Step 3: 将补全数据填回原有框架

| 缺失字段 | yfinance 字段 | 备注 |
|---------|-------------|------|
| enterprise_value | `enterpriseValue` | 单位：美元 |
| total_debt | `totalDebt` | |
| total_cash | `totalCash` | |
| analyst_target_price | `targetMeanPrice` | |
| analyst_count | `numberOfAnalystOpinions` | |
| high_52w | `fiftyTwoWeekHigh` | |
| low_52w | `fiftyTwoWeekLow` | |
| operating_margin_pct | `operatingMargins` * 100 | 小数转百分比 |
| debt_to_equity | `debtToEquity` | |
| free_cash_flow | `freeCashflow` | |
| ev_ebitda | `evToEbitda` | |
| forward_eps | `forwardEps` | 用于验证前瞻PE |

### Step 4: 校验数据一致性

补全后必须做以下交叉校验：
1. 前瞻PE = 当前价 / TTM EPS，与脚本输出的 `trailing_pe` 对照
2. Forward PE = 当前价 / Forward EPS，与脚本输出的 `forward_pe` 对照
3. PEG = Forward PE / 增速假设，确保增速假设合理（不是 `earningsGrowth` 失真值）
4. EV/EBITDA 若获取到，与同行业标的对照

## 扩展降级：yfinance info/recommendations 端点故障时的替代链路

实际战斗中可能出现 `info()` 和 `recommendations()` 均因 SSL/限流失败，但 `financials` 端点仍然可用的情况（如本次 PDD 分析）。完整替代链路如下：

### A. inv-stock-data financials 子命令（优先）

当 `valuation_snapshot.py` 返回大量 data_gaps 时，先用 inv-stock-data 的 financials 子命令获取财务三表：

```bash
uv run {valuationDir}/../inv-stock-data/scripts/cs_stock_info.py financials 0700.HK --output json
```

返回 `income_stmt`、`balance_sheet`、`cash_flow` 三个表，字段映射与提取方式与 yfinance 相同（inv-stock-data 内部封装了 yfinance financials 端点）。

**关键字段提取映射**（从 financials 输出提取到 snapshot 字段）：

| 目标字段 | income_stmt 行 | balance_sheet 行 | cash_flow 行 | 计算方式 |
|----------|---------------|------------------|--------------|----------|
| trailing_pe | — | — | — | price / (Net Income / Diluted Shares) |
| forward_pe | — | — | — | price / (Broker FY1 EPS / fx) |
| pb | — | Stockholders Equity | — | price / (Equity / Diluted Shares / fx) |
| market_cap | — | — | — | price * Diluted Shares |
| roe_pct | Net Income | Stockholders Equity | — | NI / Avg(Equity_t, Equity_t-1) * 100 |
| gross_margin_pct | Gross Profit / Total Revenue | — | — | *100 |
| operating_margin_pct | Operating Income / Total Revenue | — | — | *100 |
| net_margin_pct | Net Income / Total Revenue | — | — | *100 |
| free_cash_flow | — | — | Free Cash Flow | 原始值 |
| total_cash | — | Cash Cash Equivalents And Short Term Investments | — | 原始值 |
| total_debt | — | Total Debt | — | 原始值 |
| shares_outstanding | — | — | — | Diluted Average Shares |

**注意**：Yahoo financials 单位通常为**人民币**（PDD 等中概股），市值计算需统一为美元或人民币。

**若 inv-stock-data financials 也失败**（info SSL + financials 同时不可用），才降级到手动计算。

### B. 手动计算校验脚本

当脚本和自动化均不可用时，用以下内联 Python 完成核心估值计算：

```python
price = 98.78           # USD 最新收盘价
shares_ads = 14.82      # 亿 ADS diluted
fx = 7.15               # RMB/USD
ni_2025 = 978.43        # 亿 RMB GAAP
ni_2025_ng = 1073       # 亿 RMB Non-GAAP（从研报提取）

# PE
eps_usd = (ni_2025 / shares_ads) / fx
pe = price / eps_usd

# Forward PE（用卖方或 Yahoo 预期）
eps_f26 = 82.08         # RMB/ADS from Yahoo consensus
fwd_pe = price / (eps_f26 / fx)

# PB
equity = 4133.85        # 亿 RMB
bvps_usd = (equity / shares_ads) / fx
pb = price / bvps_usd

# FCF
fcf = 1057.94           # 亿 RMB
p_fcf = (price * shares_ads) / (fcf / fx)

# ROE
roe = ni_2025 / ((equity + equity_prev) / 2) * 100

# 净现金占比
cash = cash_rmb / fx
pct = cash / (price * shares_ads) * 100

# 三场景估值
for scenario, profit_26, pe_mult in [
    ('悲观', 1127, 8),
    ('基准', 1300, 10),
    ('乐观', 1500, 12)
]:
    eps = (profit_26 / shares_ads) / fx
    target = eps * pe_mult
    upside = (target / price - 1) * 100
    print(f'{scenario}: Target={target:.0f}USD, Upside={upside:+.0f}%')
```

## E. 港股行情替代源：`qt.gtimg.cn`（腾讯行情接口）

当 Yahoo Finance 全局限流且 `cs_stock_info.py snapshot` 对港股返回空或严重缺失时，`qt.gtimg.cn` 是一个高可用、无需代理、无 API Key 的港股/美股行情源。

### 使用方式

```bash
# 批量获取港股行情（含PE、PB、52周高低位、市值等）
curl -s "https://qt.gtimg.cn/q=hk00700,hk03690,hk01024,hk09988" \
  | iconv -f gb2312 -t utf-8 2>/dev/null
```

返回字段说明（以 `v_hk00700` 为例）：
| 字段位置 | 含义 | 示例值 |
|----------|------|--------|
| 第3项 | 最新价 | `457.200` |
| 第4项 | 昨收 | `464.400` |
| 第5项 | 今开 | `462.000` |
| 第10项 | 最低价 | `457.200` |
| 第11项 | 成交量（股） | `32469707.0` |
| 第32项 | PE | `16.75` |
| 第33项 | ？？？ | — |
| 第34项 | PB | `4.535` |
| 第35项 | 市值（亿港元） | `41687.4578` |
| 第43项 | 52周最高 | `683.000` |
| 第44项 | 52周最低 | `457.200` |
| 第45项 | 涨跌幅 | `-1.55` |
| 第46项 | 总市值（港元） | `9117991636.00` |

**关键优势**：
- 无需代理（国内直连）
- 返回实时 PE、PB、52 周高低位、市值等关键估值字段
- 支持批量查询（逗号分隔多个代码）
- 美股代码前缀 `us`（如 `usBABA`、`usPDD`）

**注意事项**：
- 返回数据为 GB2312/GBK 编码，需 `iconv` 转 UTF-8
- 字段顺序固定，建议用 Python split 解析而非正则
- PB 口径与 Yahoo 可能不同（净资产计算时点差异），PE 通常一致
- 无 FCF、EV/EBITDA、分析师目标价等字段

**实战案例**（2026-05-12 腾讯 0700.HK）：
```bash
curl -s "https://qt.gtimg.cn/q=hk00700" | iconv -f gb2312 -t utf-8
# 返回：PE=16.75, PB=4.535, 市值=4.17万亿HKD, 52周高=683, 52周低=457.2
# 与 Yahoo Trailing PE 16.43 基本一致，PB 差异（Yahoo 3.11）来自净资产口径
```

---

## D. 全端点 blackout：连 yfinance financials 也失败时的兜底链路

### 触发特征
- `cs_stock_info.py financial` / `profile` 返回 `"Yahoo Finance 不可用"`
- 直接 `yfinance` 调用触发 `curl_cffi CurlError: Recv failure: Connection reset by peer` 或 SSL 握手失败
- Browser 访问 Yahoo Finance 陷入 consent 页面循环（如 `Dine privatlivsvalg`），无法提取数据
- 仅剩 `cs_stock_info.py snapshot` 能返回基础字段（price, daily, pe_trailing, pb, fundamentals 部分键）

### 兜底链路

#### 1. 用 snapshot 锚定基础事实
即使 snapshot 不完整，通常仍能拿到：
- `price`, `change_pct`, `currency`
- `sector`, `industry`
- `daily`（最近 5 日 K 线，含 52 周高低位代理）
- `fundamentals` 中的 `pe_trailing`, `pb`, `market_cap`, `roe`, `gross_margins`, `revenue_growth` 等

**关键检查**：snapshot 返回的 `earnings_growth` 对互联网平台公司（PDD、BABA、TCEHY 等）通常基于 GAAP 单季数据，严重失真。**不得直接填入增速假设**，需从研报提取 Normalized/Non-GAAP 增速。

#### 2. 从本地券商 PDF 提取核心财务假设
加载并遵循 `inv-research-analyzer/SKILL.md`，用 `research_pdf.py list --code {TICKER}` 定位近半年研报，然后 `extract` 获取：
- **Non-GAAP 净利润** 及增速（通常标注为"调整后"/"经调整"/"Non-GAAP"）
- **一致预期 EPS**（FY1/FY2，RMB 或 USD 口径）
- **SOTP 分部估值**（国内业务 PE + 海外业务 P/GMV 或 DCF）
- **目标价与假设**（估值倍数、汇率假设、摊薄股数）
- **关键经营指标**：毛利率、经营利润率、FCF、ROE、税率、汇兑损失说明

> 若 PDF 为扫描件（`inspect` 返回 `likely_scanned: true`），走 `pdf-ocr-skill` 或 `paddleocr-text-recognition` 提取。

#### 3. 手动估值计算（快照 + PDF 数据）

提取到以下字段后即可在 Python 中手算核心估值：

```python
price = 98.59           # USD，来自 snapshot
shares_diluted_b = 14.82 # 亿股 ADS diluted，来自研报或 Yahoo info（若可用）
fx = 7.15               # RMB/USD，研报常用假设

# 来自研报提取的 Non-GAAP 净利润（亿 RMB）
ni_2025_ng = 1073       # 2025 实际
ni_2026e_ng = 1330      # 2026E 中位数
ni_2027e_ng = 1600      # 2027E

# TTM PE（调整后）
eps_2025_usd = (ni_2025_ng / shares_diluted_b) / fx
pe_ttm_adj = price / eps_2025_usd

# Forward PE（调整后）
eps_2026e_usd = (ni_2026e_ng / shares_diluted_b) / fx
fwd_pe_adj = price / eps_2026e_usd

# PEG（用 Non-GAAP 增速，非 Yahoo earningsGrowth）
eps_growth_pct = (ni_2026e_ng / ni_2025_ng - 1) * 100  # 如 24%
peg = fwd_pe_adj / eps_growth_pct

# 52 周位置（用 snapshot daily 自行计算）
low_52w = 87.11
high_52w = 139.41
position_pct = (price - low_52w) / (high_52w - low_52w) * 100

# 三场景目标价（直接用研报一致预期利润 × 合理 PE）
for scenario, profit, pe_mult in [
    ('悲观', 1127, 8),   # 利润取卖方下限
    ('基准', 1330, 10),  # 利润取中位数
    ('乐观', 1560, 12),  # 利润取卖方上限
]:
    eps = (profit / shares_diluted_b) / fx
    target = eps * pe_mult
    upside = (target / price - 1) * 100
    print(f'{scenario}: Target=${target:.1f}, Upside={upside:+.0f}%')
```

#### 4. 校验与标注
- **口径一致性**：snapshot 的 `pe_trailing` 通常基于 GAAP；手动计算的 `pe_ttm_adj` 基于 Non-GAAP。**必须标注差异**，例如："Yahoo PE TTM 10.2x（GAAP）；调整后 9.1x（Non-GAAP，来源：华泰 2026-03-26）"
- **汇率校验**：若不同研报使用不同汇率（如 7.15 vs 7.25），统一为当前汇率或注明各研报的汇率假设
- **股数校验**：PDD 等中概股常用 ADS 股数；确保分子（利润）和分母（股数）口径一致（如利润是否按 ADS 折算）
- **缺失标注**：在最终报告中明确列出哪些字段来自 snapshot、哪些来自 PDF、哪些缺失，并说明对结论置信度的影响

## 常见问题

- **ModuleNotFoundError**: yfinance 未安装。用系统 Python 的 pip 安装，或复用之前的 venv。
- **YFRateLimitError**: 代理不稳定。切换代理端口（7890/7891/7897）或等待几分钟重试。
- **SSL / Connection reset**: `info()` 和 `recommendations()` 端点因 SSL 握手失败时，优先降级到 `financials` 端点。
- **全端点 blackout（SSL + 限流 + consent 循环）**: 按本文件「D. 全端点 blackout」链路执行：snapshot 锚定 → PDF 提取 → 手动计算。
- **字段为 None**: Yahoo 对该标的某些字段未提供。标注缺口，不能用 None 填充结论。

## F. info SSL 失败但 financials 正常（美股常见模式）

### 触发特征（2026-05 META 实测）
- `valuation_snapshot.py` 返回 33+ 项 data_gaps，几乎所有估值/质量字段为 null
- `t.info` 直接调用报 `curl_cffi.curl.CurlError: (35) Recv failure: Connection reset by peer`
- 但 `t.income_stmt`、`t.balance_sheet`、`t.cash_flow`、`t.history()` 全部正常返回

### 降级方案（三步补全，耗时约 30-60 秒）

**Step 1**：用 financials 三表计算所有质量指标
```python
inc = t.income_stmt    # Revenue, Gross Profit, Operating Income, Net Income, Normalized Income, EBITDA, Diluted Average Shares
bs = t.balance_sheet   # Common Stock Equity, Total Debt, Cash+STI
cf = t.cash_flow       # Free Cash Flow, Capital Expenditure, Repurchase Of Capital Stock, Cash Dividends Paid, Operating Cash Flow
```

**Step 2**：用 `t.history(period='5y', interval='1mo')` 计算 52 周位置和 5 年价格分位
```python
hist5y = t.history(period='5y', interval='1mo')
closes = hist5y['Close'].dropna()
current = closes.iloc[-1]
pct_5y = (closes < current).sum() / len(closes) * 100
hist1y = t.history(period='1y', interval='1d')
high_52w = hist1y['High'].max()
low_52w = hist1y['Low'].min()
position_52w = (current - low_52w) / (high_52w - low_52w) * 100
```

**Step 3**：等待 3-5 分钟后重试 `t.info` 获取快照字段
```python
# 通常在 financials 调用后等待几分钟，info 端点可恢复
info = t.info
# 获取: currentPrice, trailingPE, forwardPE, priceToBook, marketCap,
#       targetMeanPrice, fiftyTwoWeekHigh/Low, sharesOutstanding,
#       grossMargins, operatingMargins, returnOnEquity, freeCashflow 等
```

### 关键发现
- `info` 端点走 `v10/finance/quoteSummary`，与 financials/history 走不同 API 端点
- SSL 失败通常是临时性的，等待数分钟后可恢复
- financials 三表 + history 可覆盖 QARP 分析 90%+ 所需字段
- **注意**：financials 返回的 DataFrame 列为 Timestamp 类型，不能用整数索引 `df.loc['row', 0]`，必须用 `df.loc['row', df.columns[0]]` 或 `df.loc['row', timestamp]`
