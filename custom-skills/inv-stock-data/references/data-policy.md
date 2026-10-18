# inv-stock-data 数据源策略

本页描述现有实现，不承诺接口可用性、实时性或自动补齐。缺失值、状态与来源以实际 v1 envelope 为准。

## A 股 / 北交所

- **用途**：基础行情、公司档案、财务摘要、估值指标、公告标题、同行业板块成分股；不提供调研记录。
- **现有来源**：
  - 股票代码名称列表：`stock_info_a_code_name`。
  - 新浪前复权日线：`stock_zh_a_daily`。
  - 同花顺财务摘要：`stock_financial_abstract_ths`（按报告期）。
  - 新浪财务报表：`stock_financial_report_sina`；当前财务补充函数也调用此接口，不保证独立财务指标完整覆盖。
  - 百度估值：`stock_zh_valuation_baidu`。
  - 巨潮公司概况：`stock_profile_cninfo`，缺失时尝试东财 `stock_individual_info_em`。
  - 公告：`stock_notice_report`；不可称为已实现巨潮公告主源与自动降级链。
  - 行业板块：东财 `stock_board_industry_name_em` / `stock_board_industry_cons_em`。
  - 指数日线：`stock_zh_index_daily`，失败时尝试 `stock_zh_index_daily_em`。
- **relations 语义**：旧命令名保留，返回 `data.relation_type: "industry_constituents"`、`data.industry_members`，`data.relations` 为兼容别名。最多10条，可能包含自身；不调用巨潮调研接口，不提供调研事件日期或30日调研覆盖。失败保留 failed envelope，不解释为空事件历史。
- **代理**：调用方在 A 股调用前清除 `HTTP_PROXY` / `HTTPS_PROXY` 及小写变量；当前 `safe_call` 不清除代理。CLI 没有 `--keep-proxy` 参数。

## ETF

- **分类/名称**：新浪 `fund_etf_category_sina`，天天基金名称列表 `fund_name_em` 降级。
- **日线**：新浪基金专用 `fund_etf_hist_sina` 不复权价格，不是独立基金净值或含分红总回报序列；除息可能影响趋势判断。不得调用依赖股票流通股本的 `stock_zh_a_daily` 获取 ETF 日线，ETF 股本接口可返回 null 并导致价格解析链路失败。异常通过日线与快照 sources.reason 保留类型和信息，不能将解析错误统一称为空响应。
- **净值边界**：独立净值来源尚未验证，`fetch_etf_nav` 返回 `None`；snapshot 返回 `nav: null` 和 `data.nav` 缺口。禁止把 OHLC 收盘价作为单位净值，禁止据此推算折溢价。
- 不支持 ETF 财务摘要、估值、公告或调研；代理清除要求同 A 股。

## 美股 / 港股

- **主来源**：yfinance（Yahoo Finance）的 info、history 与财务三表；不是实时盘口保证。
- **现有降级**：港股尝试 AkShare `stock_hk_hist`、`stock_hk_spot`，以及新浪报价和 `stock_hk_daily`；美股日线尝试 `stock_us_hist`。没有港股东财财务指标自动补齐保证。
- **代理**：入口通过共享代理模块检测或使用显式 `--proxy`；缺失代理在 envelope 的 notes/gaps 中提示。代理已设不代表节点可用，失败提示不等于已查明限流原因。
- **请求与失败语义**：snapshot 并行提交 info/history；Yahoo fetch 函数有进程内3秒调用间隔节流，但不保证跨进程或每个底层 HTTP 请求的间隔。未实现自动指数退避重试、缺价日线回填或同花顺单季度重试。失败时尝试现有市场降级；`safe_call` 捕获异常返回缺失值，`retryable` 仅是缺口元数据，不表示已经重试。
- 不提供美港股巨潮式 `announcements` 或调研命令。等待、换代理、独立核验与再调用属于调用方操作，不是内置重试承诺。

## 杠杆字段与单位

- `data.fundamentals.debt_to_asset_pct`：资产负债率百分数，38.5 表示38.5%。
- `data.fundamentals.debt_to_equity_ratio`：负债/权益无量纲比值，1.25 表示125%。Yahoo `debtToEquity` 除以100后进入此字段。
- A 股资产负债率不得映射为负债/权益比；两者缺失为 null，不互相回填。旧 financial `debt_to_equity` 仅为 Yahoo 原始百分数兼容字段，弃用且不得跨市场混读。

## 数据层统一与只读边界

其他投资技能只能通过本技能的 v1 公共契约获取数据，不直接调用 AkShare / yfinance。本技能为所有投资相关技能的唯一数据层。

所有命令返回 `schema_version/status/symbol/data_as_of/sources/gaps/notes/data`；日线另返回实际 `window`。`all` 固定只含 snapshot、financial、financials 三组件，不含独立 daily、announcements 或 relations。调用方检查 status 和结构化 gaps，不用空值猜测失败原因。

本技能 CLI 获取并输出数据，不提供交易、持仓主数据写入或 cron 修改入口。运行依赖可能产生供应商缓存；这里不承诺操作系统层面的零写入。持仓刷新只能使用 `inv-portfolio-tracker` 已有受控入口，默认预览，只有用户明确授权才写入；不得用逐个 snapshot 手工覆盖主文件或另建跨市场批量抓取脚本。
