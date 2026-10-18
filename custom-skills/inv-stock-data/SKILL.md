---
name: inv-stock-data
description: 获取A股/港股/美股/ETF行情与财务数据，所有投资技能的唯一数据层。用于查询股票行情、财务报表、估值指标时
version: 2.0.0
trigger:
  - 股票数据
  - 行情查询
  - 财务数据
  - A股
  - 港股
  - 美股
  - ETF
  - cs_stock
commands:
  - /cs_stock - 综合信息快照（默认；自动识别 A 股 / ETF / 美港股）
  - /cs_stock_profile - A 股交易所列表全量键值；美港股 Yahoo info 全量键值；ETF 新浪分类信息
  - /cs_stock_daily - 最近日线（A 股新浪 / ETF 新浪 / 美港股 Yahoo）
  - /cs_stock_financial - A 股同花顺财务摘要 + 新浪财务指标；美港股 Yahoo fundamentals
  - /cs_stock_financials - 财务三表（利润表/资产负债表/现金流量表），美港股走 yfinance，A 股走 akshare
  - /cs_stock_all - 一次调用获取 snapshot + financial + financials，减少跨进程调用（不保证避免限流）
  - /cs_stock_description - 公司简介（A 股巨潮 / 美港股 Yahoo description）
  - /cs_stock_announcements - 近期公告（stock_notice_report，仅 A 股）
  - /cs_stock_relations - 同行业板块成分股（旧命令名，仅 A 股；不是调研）
  - /cs_stock_index-daily - A 股指数日线
---

# 股票信息获取（inv-stock-data）

## 核心目标

在用户询问 **个股基础信息、行情、财务摘要、公告或行业数据** 时，优先用本技能内置脚本拉取结构化数据，再回答或整理；不做估值结论与买卖建议（估值请用 `inv-valuation-engine`）。

**本技能是所有投资相关技能的唯一数据层**，其他技能只能通过本技能的公共契约获取数据，不直接调用 AkShare / yfinance。脚本优先级、代理规则、重试/降级语义以本技能为权威，其他技能只保留与自身分析逻辑强相关的补充说明。

### v1 公共契约（破坏性变更）

所有 JSON 命令统一返回 `schema_version: "1.0"` envelope：`status`（`ok|partial|failed`）、`symbol`、`data_as_of`、`sources`、结构化 `gaps`、`notes`、`data`，日线另含实际 `window`。调用方必须先检查 `status`，不得读取供应商原始字段；`failed` 的 CLI 退出码非零。

标准杠杆字段位于 `data.fundamentals`：`debt_to_asset_pct` 是资产负债率百分数（38.5 表示38.5%）；`debt_to_equity_ratio` 是负债/权益无量纲比值（1.25 表示125%）。A 股不以资产负债率冒充负债权益比；Yahoo `debtToEquity` 除以100后进入 ratio。旧 financial 字段 `debt_to_equity` 仅为 Yahoo 原始百分数兼容，弃用且不得跨市场混读。缺失为 null，不互相回填。

`relations` 返回 `data.relation_type: "industry_constituents"`、`data.industry_members`；旧 `data.relations` 是同一列表兼容别名。最多10条、可能含自身、无事件日期/30日覆盖，来源 `eastmoney-industry`；失败保留 failed envelope。

`all` 固定只聚合 `snapshot + financial + financials`，位于 `data.components` 且各有独立状态；**不包含** `daily`、`announcements`、`relations`。需要历史或事件数据时显式调用对应命令。

## 快速命令

路径中 `{baseDir}` 表示本技能目录（`skills/inv-stock-data`）。

```bash
# ===== 代理规则（硬约束） =====
# 美股 / 港股建议配置代理，入口自动检测并提示缺口：
#   1. 优先读 HTTPS_PROXY / HTTP_PROXY 环境变量
#   2. 其次检测本地 Clash 端口（7890 → 7891 → 7897）
#   3. 都未检测到 → envelope 的 notes/gaps 提示代理缺失
#   4. 仍失败时手动指定：--proxy <地址>（以本机代理实际端口为准）
#   5. Yahoo 全空时给出代理/限流排查提示，不保证已查明失败原因
# A 股 / ETF **必须清除代理**，每次调用前先执行 unset：
#   unset HTTPS_PROXY HTTP_PROXY https_proxy http_proxy
#   当前 safe_call 不自动清除代理；调用方应显式 unset，
#   避免代理配置导致国内接口 ProxyError。
#
# ⚠️ 分市场批次调用，避免代理配置切换导致错误。
#   先跑完一种市场，确认清除/设置代理，再跑另一种。

# 自动探测失败时才手动设置（端口以本机代理为准；export 与命令须在同一次 shell 调用）：
#   export HTTPS_PROXY=<地址> HTTP_PROXY=<地址>

# —— A 股 / 北交所 ——
uv run {baseDir}/scripts/cs_stock_info.py snapshot 600519
uv run {baseDir}/scripts/cs_stock_info.py snapshot 000001 --output json
uv run {baseDir}/scripts/cs_stock_info.py profile 300750 --output json
uv run {baseDir}/scripts/cs_stock_info.py daily 688981 --period 5y --output json
# 可显式限制返回数量：--limit 250；未给 limit 时不截短请求窗口
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

# —— 美股 / 港股（需代理，入口自动探测）——
uv run {baseDir}/scripts/cs_stock_info.py snapshot AAPL
uv run {baseDir}/scripts/cs_stock_info.py snapshot 0700.HK
uv run {baseDir}/scripts/cs_stock_info.py snapshot 9992.HK --proxy <地址>  # 自动探测失败时手动指定
uv run {baseDir}/scripts/cs_stock_info.py daily MSFT --output json
uv run {baseDir}/scripts/cs_stock_info.py profile NVDA --output json
uv run {baseDir}/scripts/cs_stock_info.py financial AAPL --output json
uv run {baseDir}/scripts/cs_stock_info.py description AAPL --output json
```

## 脚本使用优先级

1. 用户要 **一眼看清** 名称、行业、价格/收盘、短期涨跌、关键估值或质量指标：运行 `snapshot`，并从 v1 `data` 读取标准字段。
   - A 股 snapshot data：name, industry, price, currency, daily, financial, valuation, sina, description
   - ETF snapshot data：name, category, price, currency, daily, nav
   - 美港股 snapshot data：name, sector, industry, price, currency, daily, fundamentals
   - snapshot 内的 daily 仅用于短期概览；52 周/250 日/5 年指标必须显式调用 `daily --period 5y` 并检查 window 门槛
2. 用户要 **完整字段表**（股票代码名称列表或 Yahoo `info`，位于 v1 data）：运行 `profile --output json`。
3. 用户要 **K 线序列**：运行 `daily --output json`。
4. 用户要 **财务摘要**：运行 `financial --output json`（A 股同花顺+新浪；美港股 Yahoo fundamentals）。
5. 用户要 **公司简介**：运行 `description --output json`。
6. 用户要 **A 股公告标题** 做事件排查：运行 `announcements`（**仅 A 股**）。
7. 用户要 **A 股同行业成分股**：运行 `relations`（旧接口名，仅 A 股）。它不是巨潮调研记录，不提供30日调研覆盖；需要调研证据时另行核对官方披露，不能用此列表替代。
8. 用户要 **A 股指数日线**：运行 `index-daily <指数代码>`。
9. 美港股遇 `YFRateLimitError` / `Too Many Requests`：设置 **`HTTPS_PROXY`** 环境变量后再执行。
10. **实际失败语义**：本层未实现自动退避重试、缺价日线回填或同花顺单季度重试。美港股 snapshot 并行请求 info/history；失败时尝试已有市场降级。AkShare 的 `safe_call` 失败返回缺失值；调用方按 `status/gaps/notes` 处理，不得把 `retryable` 当成已执行重试。
11. 脚本返回的 `notes` / `gaps` 必须原样关注；缺数据时说明缺口，不要编造。
12. **禁止管道执行**：**绝不**使用 `uv run ... --output json | python3 -c "..."` 模式。管道传递的 JSON 可能因截断、换行或转义导致解析错误，且触发安全审批。正确做法：`uv run ... --output json > /tmp/stock_data.json`，再 `python3 -c "import json; d=json.load(open('/tmp/stock_data.json')); ..."`。
13. **Yahoo 限流**：连续 Yahoo 请求（snapshot + financials + daily）必须间隔 ≥3 秒。Yahoo fetch 函数另有进程内3秒节流，不保证跨进程或每个底层请求间隔，不保证避免限流，也不是自动重试。优先用 `cs_stock_all` 合并调用。
14. **批处理边界**：数据层允许 `cs_stock_all` 合并抓取单标的；组合层批量刷新只允许走受控脚本（如 `qq_update_portfolio.py`），不要自行写批量跨市场抓取脚本。

## 代码与市场识别

| 类型 | 输入示例 | 说明 |
|------|----------|------|
| ETF | `513010`、`159915` | 6 位数字，`51xxxx`（沪市）或 `15xxxx`（深市） |
| 沪深 A | `600519`、`000001`、`300750` | 6 位数字（非 51/15 开头）；可带 `.SS` / `.SZ` |
| 北交所 | `430047` 等 | 6 位数字 |
| 港股 | `0700.HK`、`9988`（自动为 `9988.HK`） | 显式 `.HK` 优先；纯 4～5 位数字视为港股；**注意**：`snapshot` 子命令对港股需用5位代码如 `00700`（非 `0700`），否则返回空数据 |
| 美股 | `AAPL`、`MSFT`、`BRK.B` | Yahoo ticker；含字母即按美股等处理 |
| 韩股/日股等 | `000660.KS`、`7203.T` | ⚠️ **不支持**：yfinance 实测返回空数据；请用 Brave Search 搜索英文关键词获取行情 |

`announcements` 和 `relations` 仅用于 **A 股 6 位代码**；当前 CLI 分派未强制校验这两个命令的市场，调用方须遵守该使用边界，不把其他市场返回结果当有效数据。

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

- **A 股**：交易所列表、新浪日线、同花顺财务摘要、百度 PE/PB、巨潮公司概况（东财降级）、公告接口、东财行业板块成分股、指数日线。`relations` 不调用巨潮调研接口。
- **ETF**：新浪基金专用不复权日线（`fund_etf_hist_sina`；非总回报序列，除息可能影响趋势判断）、新浪分类列表（天天基金名称列表降级）。独立净值来源尚未验证，`fetch_etf_nav` 返回 `None`，snapshot 输出 `nav: null` 和 `data.nav` 缺口；不能从行情 OHLC 猜净值或折溢价。不支持财务摘要、估值、公告、调研。
- **美港股**：**yfinance（Yahoo Finance）**；非实时盘口。
- **代理**：美港股入口自动检测代理；A 股/ETF 调用前由调用方清除代理，当前 `safe_call` 不自动清除。
- **估值指标**：A 股 snapshot 含 `valuation`（百度 PE TTM/PE 静态/PB/市现率/总市值）和 `sina_financial_supplement`（新浪 EPS/每股净资产/股息发放率）；百度缺失时用新浪数据 + 收盘价自行计算。
- **yfinance 高级 API**：当 CLI 子命令返回不全或需完整年度财报时，可直接用 Python `yfinance` 调用 `ticker.income_stmt` / `balance_sheet` / `cash_flow` 和 `ticker.history(period='5y', interval='1mo')`。详见 `references/yfinance-advanced-usage.md`。

## 持仓数据刷新流程

当用户要求"刷新持仓数据"时，加载 `inv-portfolio-tracker`，使用其 `scripts/qq_update_portfolio.py` 受控入口：默认预览，`--check` 检查可用性，`--report` 或 `--json` 输出；仅用户授权更新时使用 `--write`。入口读取持仓主数据，不自行重建持仓列表。

保留报价来源、市场、币种与报价时点；缺失或过期价格明确列出，不猜测回填。异常价格、影响重要决策的价格及重大疑点按需独立验证，不强制每个报价双源。禁止逐个 snapshot 后手工汇总写主文件或另写批量抓取脚本。

## 与其他技能配合

- **数据层统一**：本技能是所有投资相关技能的**唯一数据层**。`inv-valuation-engine`、`inv-qarp-strategy` 通过 CLI 子进程调用本技能获取数据，不直接调用 AkShare / yfinance。
- **价值投资估值**：本技能只提供事实数据；五档估值结论请走 `inv-valuation-engine`。
- **Yahoo 子命令大全**（期权、评级、search 等）：可用 Python `yfinance` 直接调用，详见 `references/yfinance-advanced-usage.md`。
- **Yahoo Finance Web 降级方案**：当所有 yfinance API 端点均失败时，用 Agent WebFetch 抓取 Yahoo Finance 网页获取价格/PE/52周范围等数据，详见 `references/yahoo-browser-fallback.md`。
- **QQ Finance 实时行情降级方案**：当 AkShare 东财源因代理失败、新浪返回空时，用 QQ Finance API（`qt.gtimg.cn`）获取 A 股/港股盘中实时价格，详见 `references/qq-finance-realtime-api.md`。
- **技能与数据组织约定**：投资技能目录结构、持仓文件位置、迁移记录见 `references/skill-organization.md`。
- **持仓快照更新**：只走 `inv-portfolio-tracker` 的 `qq_update_portfolio.py` 受控入口；不逐个 snapshot 手工汇总或直接改主文件。
- **批处理边界**：使用现有受控入口，不新增跨市场批量抓取脚本。

## 首次运行依赖安装

脚本依赖 `akshare`、`pandas`、`yfinance` 等 Python 包。`uv run` 不会自动安装到 venv，首次运行会因解析/下载依赖而超时。

**一次性修复**（在技能目录下执行）：
```bash
cd {baseDir}
uv venv                          # 创建 .venv（如不存在）
uv pip install --python .venv/bin/python akshare pandas yfinance
```

安装后 `uv run` 即可在 1-2 秒内启动。若后续 `uv run` 仍慢，检查 `.venv` 是否存在且包完整。

## 详细参考文档

- **Yahoo Finance 限流策略**：`references/yahoo-rate-limit-strategy.md`（含 `yf.download()` vs `Ticker.history()` 差异、连续请求触发模式、应对策略、代码示例）
- **宏观利率数据**：`references/macro-rates-guide.md`（10Y UST、^TNX、中国国债收益率获取方法）
- **QQ Finance 实时行情降级**：`references/qq-finance-realtime-api.md`（A股/港股盘中实时行情、字段索引、代码示例）
- **Yahoo 浏览器降级**：`references/yahoo-browser-fallback.md`（Agent WebFetch 用法、JS 提取技巧）
- **已知问题与降级**：`references/known-issues.md`（分端点限流、SSL 失败、A 股数据源问题等）
- **yfinance 高级用法**：`references/yfinance-advanced-usage.md`（期权、评级、search 等）
- **持仓刷新流程**：加载 `inv-portfolio-tracker`，以其受控刷新入口及文档为准。

## 使用原则

1. **先加载本技能再执行投资分析**：不得跳过技能直接用浏览器/curl/yfinance——技能封装了代理管理、降级策略、数据校验等逻辑。
2. 先跑脚本再组织语言，输出中注明数据时点。
3. 不输出投资建议。
4. 网络失败时根据 `notes`/`gaps` 重试、切换代理或检查本机网络。
5. 韩股/日股不支持，用搜索替代。
6. 遇数据异常或脚本失败（PE 缺失、日线空、Yahoo 限流、同花顺远古数据等），查阅 `references/known-issues.md` 中的降级策略。
7. **分市场批次调用**：避免代理配置切换导致错误，同一批次只处理一种市场。
8. **禁用 `uv run | python3 -c`**：管道传递 JSON 易出错且触发审批。用 `--output json > /tmp/xxx.json` 再读取。
