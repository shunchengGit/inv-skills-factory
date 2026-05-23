---
name: cs-stock
description: 获取股票/ETF 相关信息：A 股/北交所（交易所列表、新浪日线、同花顺财务摘要、百度估值、巨潮公告与调研、行业板块与指数、指数日线）；ETF（东财日线与净值、同花顺分类名称）；美股与港股（yfinance / Yahoo Finance：报价、日线、基本面 info、财报日期、新闻）。用于快速查代码/名称/行业/价格与区间涨跌、K 线、财务与估值指标、公告与调研摘要；非投资建议。A 股行情与财务不使用东方财富数据源。所有投资技能的唯一数据层。
version: 1.5.0
commands:
  - /cs_stock - 综合信息快照（默认；自动识别 A 股 / ETF / 美港股）
  - /cs_stock_profile - A 股交易所列表全量键值；美港股 Yahoo info 全量键值；ETF 同花顺分类信息
  - /cs_stock_daily - 最近日线（A 股新浪 / ETF 东财 / 美港股 Yahoo）
  - /cs_stock_financial - A 股同花顺财务摘要 + 新浪财务指标；美港股 Yahoo fundamentals
  - /cs_stock_financials - 财务三表（利润表/资产负债表/现金流量表），美港股走 yfinance，A 股走 akshare
  - /cs_stock_all - 一次调用获取 snapshot + financial + financials，避免多次跨进程调用触发限流
  - /cs_stock_description - 公司简介（A 股巨潮 / 美港股 Yahoo description）
  - /cs_stock_announcements - 近期巨潮公告（仅 A 股）
  - /cs_stock_relations - 近期巨潮调研记录（仅 A 股）
  - /cs_stock_index-daily - A 股指数日线
---

# 股票信息获取（cs-stock）

## 核心目标

在用户询问 **个股基础信息、行情、财务摘要、公告、调研或行业数据** 时，优先用本技能内置脚本拉取结构化数据，再回答或整理；不做估值结论与买卖建议（估值请用 `value-investing-valuation`）。

**本技能是所有投资相关技能的唯一数据层**，其他技能通过 CLI 子进程调用本技能获取数据，不直接调用 AkShare / yfinance。

## 快速命令

路径中 `{baseDir}` 表示本技能目录（`skills/cs-stock`）。

```bash
# ===== 代理规则（硬约束） =====
# 美股 / 港股 **必须走代理**，脚本自动检测并强制要求：
#   1. 优先读 HTTPS_PROXY / HTTP_PROXY 环境变量
#   2. 其次检测本地 Clash 端口（7890 → 7891 → 7897）
#   3. 都未检测到 → stderr 输出明确警告，payload._proxy_ok=false，notes 注入修复提示
#   4. 可手动指定：--proxy http://127.0.0.1:7890
#   5. Yahoo 全空时自动诊断：代理缺失 vs 代理已设但节点限流，分别提示
# A 股 / ETF 自动清除代理环境变量，避免国内源绕远路。

# 手动设置代理（推荐，确保可用）：
export HTTPS_PROXY=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890

# —— A 股 / 北交所 ——
uv run {baseDir}/scripts/cs_stock_info.py snapshot 600519
uv run {baseDir}/scripts/cs_stock_info.py snapshot 000001 --output json
uv run {baseDir}/scripts/cs_stock_info.py profile 300750 --output json
uv run {baseDir}/scripts/cs_stock_info.py daily 688981 --output json
uv run {baseDir}/scripts/cs_stock_info.py financial 600519 --output json
uv run {baseDir}/scripts/cs_stock_info.py description 600519 --output json
uv run {baseDir}/scripts/cs_stock_info.py announcements 600660 --output json
uv run {baseDir}/scripts/cs_stock_info.py relations 000858 --output json
uv run {baseDir}/scripts/cs_stock_info.py index-daily sh000300 --output json

# —— ETF（沪市 51xxxx / 深市 15xxxx）——
uv run {baseDir}/scripts/cs_stock_info.py snapshot 513010
uv run {baseDir}/scripts/cs_stock_info.py snapshot 159915 --output json
uv run {baseDir}/scripts/cs_stock_info.py daily 513010 --output json
uv run {baseDir}/scripts/cs_stock_info.py profile 513010 --output json

# —— 美股 / 港股（必须设置代理后再执行）——
uv run {baseDir}/scripts/cs_stock_info.py snapshot AAPL
uv run {baseDir}/scripts/cs_stock_info.py snapshot 0700.HK
uv run {baseDir}/scripts/cs_stock_info.py snapshot 9992.HK --proxy http://127.0.0.1:7890  # 手动指定代理
uv run {baseDir}/scripts/cs_stock_info.py daily MSFT --output json
uv run {baseDir}/scripts/cs_stock_info.py profile NVDA --output json
uv run {baseDir}/scripts/cs_stock_info.py financial AAPL --output json
uv run {baseDir}/scripts/cs_stock_info.py description AAPL --output json
```

## 脚本使用优先级

1. 用户要 **一眼看清** 名称、行业、价格/收盘、短期涨跌、关键估值或质量指标：运行 `snapshot`。
   - A 股 snapshot 含：name, industry, daily, financial, valuation, sina, description
   - ETF snapshot 含：name, fund_type, daily, nav, stats_20d, stats_52w
   - 美港股 snapshot 含：name, sector, industry, price, currency, daily, fundamentals
2. 用户要 **完整原始字段表**（雪球 item 或 Yahoo `info`）：运行 `profile --output json`。
3. 用户要 **K 线序列**：运行 `daily --output json`。
4. 用户要 **财务摘要**：运行 `financial --output json`（A 股同花顺+新浪；美港股 Yahoo fundamentals）。
5. 用户要 **公司简介**：运行 `description --output json`。
6. 用户要 **A 股公告标题** 做事件排查：运行 `announcements`（**仅 A 股**）。
7. 用户要 **A 股调研记录**：运行 `relations`（**仅 A 股**）。
8. 用户要 **A 股指数日线**：运行 `index-daily <指数代码>`。
9. 美港股遇 `YFRateLimitError` / `Too Many Requests`：设置 **`HTTPS_PROXY`** 环境变量后再执行。
10. **命中率**：脚本对 AkShare 与 Yahoo 请求均带**有限次退避重试**；美港股 `snapshot` **先拉日线再拉 info**，并在报价缺失时用日线收盘回填；同花顺财务在「按报告期」失败时会尝试 **「按单季度」**。
11. 脚本返回的 `notes` / `error` 必须原样关注；缺数据时说明缺口，不要编造。

## 代码与市场识别

| 类型 | 输入示例 | 说明 |
|------|----------|------|
| ETF | `513010`、`159915` | 6 位数字，`51xxxx`（沪市）或 `15xxxx`（深市） |
| 沪深 A | `600519`、`000001`、`300750` | 6 位数字（非 51/15 开头）；可带 `.SS` / `.SZ` |
| 北交所 | `430047` 等 | 6 位数字 |
| 港股 | `0700.HK`、`9988`（自动为 `9988.HK`） | 显式 `.HK` 优先；纯 4～5 位数字视为港股；**注意**：`snapshot` 子命令对港股需用5位代码如 `00700`（非 `0700`），否则返回空数据 |
| 美股 | `AAPL`、`MSFT`、`BRK.B` | Yahoo ticker；含字母即按美股等处理 |
| 韩股/日股等 | `000660.KS`、`7203.T` | ⚠️ **不支持**：yfinance 实测返回空数据；请用 Brave Search 搜索英文关键词获取行情 |

`announcements` 和 `relations` 仅接受 **A 股 6 位代码**。

## 数据校验（必须）

获取数据后在下结论前，必须先过一遍**常识校验**。< 1 分钟的校验可以避免整篇分析的数据硬伤。

**<span style="color:red">台积电案例：数据源曾返回 ~64% 毛利率，实际披露约 58.8%。差 5pp 是极严重错误。</span>**

校验清单见 `references/data-validation-checklist.md`，包含：
- 毛利率合理区间（制造业 >70% 必查，半导体代工 >65% 必查）
- 净利率极值（>50% 必查）
- PE/PB/PEG 异常信号
- ROE >50% 必查
- FCF 与净利润一致性
- 股价-PE 双向一致性校验

**A股 PE 数据层级**：snapshot 返回的 PE 分布在两个层级——顶层 `valuation_pe_ttm`/`trailing_pe`（常为 null）和嵌套 `valuation.pe_static`（通常有值）。详见 `references/a-share-pe-data-structure.md`。

触发异常信号时，必须交叉验证（切换数据源、查财报原文、搜索确认），确认无误后才进入估值论述。

## 数据源与约束

详见 `references/data-policy.md`。

- **A 股**：交易所列表、新浪日线、同花顺财务摘要、百度估值（PE/PB/总市值等）、巨潮公告与调研、行业板块与指数、指数日线；**不调用** `*_em`（公告降级除外）。
- **ETF**：东财日线（`fund_etf_hist_em`）、东财净值（`fund_etf_fund_info_em`）、同花顺分类列表（`fund_etf_category_ths`，含名称/基金类型/净值/涨跌幅）；不支持财务摘要、估值、公告、调研。
- **美港股**：**yfinance（Yahoo Finance）**；非实时盘口。
- **代理**：脚本内置自动代理管理——美港股自动检测并设置 `HTTPS_PROXY`（环境变量 > 本地 Clash 端口探测），A 股/ETF 自动临时清除代理；无需手动传参。
- **估值指标**：A 股 snapshot 含 `valuation`（百度 PE TTM/PE 静态/PB/市现率/总市值）和 `sina_financial_supplement`（新浪 EPS/每股净资产/股息发放率）；百度缺失时用新浪数据 + 收盘价自行计算。
- **yfinance 高级 API**：当 CLI 子命令返回不全或需完整年度财报时，可直接用 Python `yfinance` 调用 `ticker.income_stmt` / `balance_sheet` / `cash_flow` 和 `ticker.history(period='5y', interval='1mo')`。详见 `references/yfinance-advanced-usage.md`。

## 与其他技能配合

- **数据层统一**：本技能是所有投资相关技能的**唯一数据层**。`value-investing-valuation`、`quality-growth-qarp`、`porter-five-forces-analysis` 通过 CLI 子进程调用本技能获取数据，不直接调用 AkShare / yfinance。
- **价值投资估值**：本技能只提供事实数据；五档估值结论请走 `value-investing-valuation`。
- **本地券商研报 PDF**：近半年卖方共识/分歧与叙事梳理请走 **`stock-research-report-analysis`**（`~/Desktop/股票研报` 等）；本技能提供**行情与财务事实**，与研报交叉时以**披露与行情时点**为准。
- **Yahoo 子命令大全**（期权、评级、search 等）：可用 Python `yfinance` 直接调用，详见 `references/yfinance-advanced-usage.md`。
- **Yahoo Finance 浏览器降级方案**：当所有 yfinance API 端点均失败时，用无头浏览器抓取 Yahoo Finance 网页获取价格/PE/52周范围等数据，详见 `references/yahoo-browser-fallback.md`。
- **QQ Finance 实时行情降级方案**：当 AkShare 东财源因代理失败、新浪返回空时，用 QQ Finance API（`qt.gtimg.cn`）获取 A 股/港股盘中实时价格，详见 `references/qq-finance-realtime-api.md`。
- **技能与数据组织约定**：投资技能目录结构、持仓文件位置、迁移记录见 `references/skill-organization.md`。
- **持仓快照更新**：逐个调用 `uv run scripts/cs_stock_info.py snapshot <code>` 拉取，手动汇总更新 PORTFOLIO.md。
- **⚠️ 不要写批量持仓更新脚本**：实测证明不可行——(1) A股/ETF 的 AkShare 需清除代理，美港股需设置代理，频繁切换导致连接失败；(2) Yahoo 连续请求触发限流，3-5s间隔仍不够稳定；(3) 07709/06809 等港股降级新浪后无52周数据；(4) uv run 单进程 import cs-stock 函数时代理管理混乱（ThreadPoolExecutor 内子线程继承代理状态不一致）。逐个 snapshot 调用虽慢（8标的~50s），但稳定可靠。

## 首次运行依赖安装

脚本依赖 `akshare`、`pandas`、`yfinance` 等 Python 包。`uv run` 不会自动安装到 venv，首次运行会因解析/下载依赖而超时。

**一次性修复**（在技能目录下执行）：
```bash
cd {baseDir}
uv venv                          # 创建 .venv（如不存在）
uv pip install --python .venv/bin/python akshare pandas yfinance
```

安装后 `uv run` 即可在 1-2 秒内启动。若后续 `uv run` 仍慢，检查 `.venv` 是否存在且包完整。

## Yahoo Finance API 限流与降级策略（2026-05 实测）

### `yf.Ticker().history()` vs `yf.download()` 行为差异（2026-05 实测）

| 方法 | ^TNX / ^TYX 等指数 | 个股（TSM/0700.HK等） | 备注 |
|------|:---:|:---:|------|
| `yf.Ticker('^TNX').history(period='1mo')` | ⚠️ 有时可用，有时返回 "possibly delisted" | ⚠️ 同上 | 受 Yahoo 端点限流影响大，短周期（1mo）成功率高于长周期（1y） |
| `yf.download('^TNX', period='1y', interval='1d')` | ✅ 更稳定 | ⚠️ 单独可用，批量多标的易失败 | 批量下载端点与 Ticker.history() 走不同 API，限流策略不同 |
| `yf.Ticker('^TNX').history(period='5y', interval='1mo')` | ❌ 几乎必返回 "possibly delisted" | ⚠️ 不确定 | 长周期+月频对指数标的极易触发限流 |

**推荐策略**：
1. 对 ^TNX/^TYX/^FVX/^IRX 等利率指数，**优先用 `yf.download()`**
2. 若 `yf.download()` 也失败，降级到 `yf.Ticker().history(period='1mo')`（短周期成功率更高）
3. 对个股，两种方法均可，但 `yf.download()` 在限流环境下更可靠
4. `yf.download()` 返回的 DataFrame 列可能是 MultiIndex（如 `('Close', '^TNX')`），需用 `.iloc[:, 0]` 或 `['Close']['^TNX']` 提取单列
5. **⚠️ `yf.download()` 批量多标的（如 `yf.download(['TSM','0700.HK'], ...)`）在限流环境下反而更容易全部失败**；逐个请求+间隔3-5s更可靠

### Yahoo Finance 限流的「连续请求触发」模式（2026-05 实测关键发现）

**现象**：同一进程内连续请求多个 Yahoo 标的时，第2-3个请求极易触发 "possibly delisted" 限流，导致超时（实测0700.HK单次51s超时失败）。但**间隔数秒后单独请求同一标的**可在3-5s内成功。

**实测数据**：
| 场景 | TSM | 0700.HK | 说明 |
|------|-----|---------|------|
| 单独请求（首次） | 5.1s ✅ | 3.3s ✅ | 无前序请求，正常 |
| 连续请求第2-3个 | 11s ❌→重试3.8s ✅ | 51s ❌→重试3.0s ✅ | 前序请求消耗了限额 |
| `yf.download` 批量2标的 | ❌ 全部失败 | ❌ 全部失败 | 批量端点更易触发 |

**应对策略**：
1. **美港股请求间加 3-5s 间隔**（`time.sleep(3)`），比失败重试省大量时间（3s vs 51s）
2. **优先级排序**：先请求最重要的标的，确保关键数据拿到后再请求次要标的
3. **失败后等 30-60s 再重试**，不要立即重试（立即重试大概率继续失败）
4. **批量持仓更新时**：A股/ETF（AkShare，无限制）可连续请求；美港股需间隔

### 代码示例

```python
import yfinance as yf, os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

# 方法1（推荐）：yf.download
tnx_data = yf.download('^TNX', period='1y', interval='1d')
tnx_close = tnx_data['Close']
if isinstance(tnx_close, pd.DataFrame):
    tnx_close = tnx_close.iloc[:, 0]  # 处理 MultiIndex

# 方法2（降级）：Ticker.history 短周期
tnx = yf.Ticker('^TNX')
tnx_hist = tnx.history(period='1mo')  # 短周期成功率更高
```

## 宏观利率数据（10Y UST 等）

本技能聚焦个股/ETF 数据，但投资分析常需宏观利率数据（10Y UST、2Y、联邦基金利率等）。**获取方式**：

```bash
# 10年美债收益率 — yfinance ^TNX（需代理）
cd {baseDir} && uv run python3 -c "
import yfinance as yf, os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
tnx = yf.Ticker('^TNX')
hist = tnx.history(period='1mo')
print(hist.tail(10).to_string())
"
# ^TNX = 10Y, ^IRX = 13周T-bill, ^FVX = 5Y, ^TYX = 30Y
# Close 列即为收益率（如 4.595 = 4.595%）
```

- **注意**：`^TNX` 的 `info` 端点经常失败，但 `history` 端点通常可用；优先用 `history` 获取最近收盘值
- **注意**：收益率数据为百分比数值（4.595 = 4.595%），不是价格
- **A股利率**：中国10年国债收益率无免费稳定API，可用 `akshare.bond_china_yield(start_date="20260501")` 获取中债收益率曲线

## A 股 / 港股盘中实时行情：QQ Finance API

当 AkShare 东财源因 Clash 代理干扰失败、新浪 `hq.sinajs.cn` 返回 0.000（集合竞价/盘初）时，**QQ Finance API** 是可靠的盘中实时行情降级方案：

```bash
# A 股代码格式：sh600660, sz159915, sh588000, sh513010
# 港股代码格式：hk00700, hk07709
# 无需代理，直接 HTTP 请求

# 示例：获取 A 股 + 港股实时行情
python3 -c "
import requests
codes = ['sh600660', 'sh588000', 'sh513010', 'hk00700', 'hk07709']
url = f'https://qt.gtimg.cn/q={\",\".join(codes)}'
r = requests.get(url, headers={'Referer': 'https://gu.qq.com'}, timeout=10)
for line in r.text.strip().split(';'):
    line = line.strip()
    if not line or '~' not in line:
        continue
    parts = line.split('~')
    if len(parts) > 5:
        code = parts[2]    # 代码
        name = parts[1]    # 名称
        curr = parts[3]    # 现价
        prev = parts[4]    # 昨收
        chg_pct = parts[32] if len(parts) > 32 else '?'  # 涨跌幅%
        print(f'{code}|{name}|现价={curr}|昨收={prev}|涨跌幅={chg_pct}%')
"
```

**关键字段索引**（`~` 分隔）：
| 索引 | 字段 | 说明 |
|------|------|------|
| 1 | 名称 | 如"福耀玻璃" |
| 2 | 代码 | 如"600660" |
| 3 | 现价 | 当前最新价 |
| 4 | 昨收 | 昨日收盘价 |
| 32 | 涨跌幅% | 如"1.74" |

**优势**：
- 无需代理，国内直连
- 支持盘中实时（集合竞价阶段也能返回昨收价）
- 同时支持 A 股和港股
- 响应快（<2s）

**局限**：
- 无 PE/PB/市值等基本面数据
- 港股为延迟报价
- 不支持美股

## Yahoo Finance 浏览器降级方案（补充：JS 提取技巧）

当 yfinance API 全端点限流时，用无头浏览器 + `browser_console` JS 提取比解析 snapshot 更高效：

```javascript
// 在 browser_navigate 到 Yahoo Finance 页面后执行
const result = {};
document.querySelectorAll('li').forEach(li => {
  const spans = li.querySelectorAll('span');
  if (spans.length >= 2) {
    const label = spans[0].textContent.trim();
    const value = spans[1].textContent.trim();
    if (['Previous Close','Open','Day\'s Range','52 Week Range','Volume',
         'PE Ratio (TTM)','EPS (TTM)','Forward Dividend & Yield',
         '1y Target Est','Market Cap'].includes(label)) {
      result[label] = value;
    }
  }
});
JSON.stringify(result);
```

**实测**：TSM 在 yfinance 全端点超时/失败时，浏览器页面 + JS 提取可在 10s 内获取价格、PE(TTM)、EPS、52周范围等关键数据。

## 使用原则

1. **先加载本技能再执行投资分析**：不得跳过技能直接用浏览器/curl/yfinance——技能封装了代理管理、降级策略、数据校验等逻辑。
2. 先跑脚本再组织语言，输出中注明数据时点。
3. 不输出投资建议。
4. 网络失败时根据 `notes`/`error` 重试、切换代理或检查本机网络。
5. 韩股/日股不支持，用搜索替代。
6. 遇数据异常或脚本失败（PE 缺失、日线空、Yahoo 限流、同花顺远古数据等），查阅 `references/known-issues.md` 中的降级策略。
