# 已知问题与降级策略

本文档汇总 cs-stock 脚本在数据获取过程中的已知问题、根因和降级方案。遇数据异常时按症状查找对应章节。

## Yahoo Finance 限流

### 分端点限流模式

**症状**：`snapshot`/`daily`/`history` 返回 "possibly delisted; no price data found"，但 `financial` 和 `profile` 正常。

**根因**：不同子命令调用不同 Yahoo API 端点，限流粒度是端点级别的。

**降级**：依次尝试 `financial`（PE/PB/ROE/毛利率/FCF）和 `profile`（公司名/行业/描述），再用 Python 读 `yf.Ticker('TSM').info` 获取 `currentPrice`、`targetMeanPrice`、`fiftyTwoWeekHigh/Low`、`trailingPE`、`forwardPE`。

### 反向端点失败（snapshot 正常，financial/profile 失败）

**症状**：`snapshot` 成功返回基础数据，但 `financial`/`profile`/`description` 同时返回 "Yahoo Finance 不可用"。

**根因**：Yahoo 不同 API 端点限流的反向表现。

**降级**：snapshot 的 `fundamentals` 字段已含大部分估值指标（PE/PB/ROE/毛利率/利润率/营收增速），通常足够支撑快速分析。需更完整财报时降级到 `yfinance` 直调 `ticker.income_stmt`/`balance_sheet`/`cash_flow`，或走 value-investing-valuation 的全端点 blackout 兜底链路。

### yfinance info 端点 SSL 失败但 financials 可用

**症状**：美股（如 META）`info` 端点返回 `curl_cffi.curl.CurlError: (35) Recv failure: Connection reset by peer`（SSL 握手失败），但 `income_stmt`/`balance_sheet`/`cash_flow`/`history()` 正常。

**根因**：`info` 走 `v10/finance/quoteSummary` 端点，financials 走不同 API 端点，限流/SSL 粒度是端点级别的。

**降级**：直接用 financials 三表 + history 补全 QARP 所需字段（PE/PB/PS/ROE/毛利率/FCF/CapEx/回购分红/52周位置），等待数分钟后重试 `t.info` 获取 `currentPrice`、`targetMeanPrice` 等快照字段。实测 financials 端点可在 5-10 秒内返回完整数据。

### 全局限流

**症状**：所有 Yahoo 端点（snapshot/daily/financial/profile）均返回 "possibly delisted"。

**降级**：用内置搜索功能搜索财经网站获取近期价格、PE。数据时点可能滞后 1-3 天，使用时必须标注来源与时点。

### 浏览器降级方案（最后手段）

当所有 yfinance API 端点均失败时，用无头浏览器访问 `https://finance.yahoo.com/quote/<ticker>/` 抓取页面数据（当前价格、PE(TTM)、EPS、52周高低、市值、成交量）。**注意**：这是最后降级手段，数据为延迟报价，需标注来源为"Yahoo Finance 网页"。多次换代理端口（7890→7891→7897）通常无效，等待数分钟后重试更有效。

## A 股数据源问题

### AkShare hist 端点偶发返回空 DataFrame

**症状**：`ak.stock_zh_a_hist(symbol, period='daily'/'weekly'/'monthly')` 在部分时段返回空结果（exit_code=1）。非代理问题（A 股自动清代理）。

**影响**：无法计算 5 年/3 年/52 周价格分位、区间涨跌。

**降级**（按优先级）：
1. 用 `cs_stock_info.py daily` 获取最近 20 个交易日 + valuation.pe_static + 收盘价手动计算 PE
2. 用年度财报 EPS + 当前股价推算 PE 分位区间
3. 用 yfinance 获取港股对应标的月线计算分位，映射回 A 股（注意 A-H 价差）
4. 标注分位为"推算值，置信度中等"

**重要**：不得因 hist 返回空而放弃分位计算——推算值优于无值。

### 同花顺返回远古数据

**症状**：`financial` 子命令的 `ths_financial` 返回报告期为 `1992-12-31` 等远古日期，关键字段全为 `false`。

**降级**：依赖 `sina_financial` 子对象。判断方法：检查 `ths_financial.报告期`，若年份 < 2010 或关键字段全为 `false`，直接跳过同花顺，用新浪数据。

### PE 字段位置不一致

**症状**：`valuation_pe_ttm` 和 `trailing_pe` 在 metrics 顶层返回 `null`，但 `pe_static` 实际在 `valuation` 子对象中（如 `valuation.pe_static: 15.69`）。

**处理**：当顶层 PE 缺失时，必须检查 `valuation` 子对象中的 `pe_static`，标注 `(静)`。不要因顶层 `null` 就报告"PE 不可用"。

## 港股数据源问题

### Yahoo 404 标的

**症状**：部分港股（07709.HK、06809.HK）Yahoo Finance 返回 "possibly delisted"/404。

**降级**：脚本自动降级到新浪港股源（仅价格/成交量，无 PE/市值）。可尝试去掉前导零（如 `7709.HK`、`6809.HK`）获取日线用于 52 周计算，但 `info`/`fundamentals` 仍不可用。

### description 返回 null

港股 Yahoo Finance `description` 子命令可能返回 `null`，不影响基础估值判断。优先用 snapshot 的 `fundamentals` 或降级到 `financial`。

### 系统代理干扰 AkShare 港股源

**症状**：Clash 系统代理开启时，`unset HTTPS_PROXY` 无法完全清除 `uv run` 子进程的代理，AkShare 经代理连接被重置（`RemoteDisconnected`）。

**降级**：在 Python 代码内用 `os.environ.pop('HTTPS_PROXY', None)` 清除，或用 `os.environ['NO_PROXY'] = 'push2.eastmoney.com'` 绕过代理。若仍失败，降级到浏览器抓取 Yahoo Finance 网页。

## 执行环境问题

### uv run 首次超时

首次运行或网络慢时 `uv run` 可能因依赖下载超时（实测 300 秒+）。降级：直接用 `python` + `yfinance`（港股/美股需设 `HTTPS_PROXY=http://127.0.0.1:7890`）抓取 snapshot 数据，再传递给上游技能。

### venv python 直接调用失败

技能目录下 `.venv/bin/python3` 通过 `terminal()` 执行时返回 exit code -1（原因未明）。应使用 `uv run` 替代直接调用 venv python。

## 其他限制

### 韩股/日股不支持

yfinance 对韩股/日股（如 `000660.KS`、`7203.T`）实测返回空数据。替代方案：用内置搜索功能搜索英文关键词获取行情。

### A 股 daily 仅返回最近 20 个交易日

不足以计算 52 周高低位。如需 1 年日线，用 akshare 直接调用 `ak.stock_zh_a_hist(symbol, period='daily', start_date='YYYYMMDD', adjust='qfq')`，ETF 用 `ak.fund_etf_hist_em()`。

### 外资投行研报

cs-stock 仅提供行情与财务事实数据，不包含投行评级/目标价。搜索外资投行研报时，使用内置搜索功能。
