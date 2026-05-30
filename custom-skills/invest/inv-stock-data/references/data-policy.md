# inv-stock-data 数据源策略

## A 股 / 北交所

- **用途**：基础行情、公司档案、财务摘要、估值指标、公告标题、调研记录、行业板块。
- **允许**：
  - 新浪日线 (`stock_zh_a_daily`)
  - 新浪财务指标 (`stock_financial_analysis_indicator`)
  - 同花顺财务摘要 (`stock_financial_abstract_ths`)
  - 巨潮公告 (`stock_zh_a_disclosure_report_cninfo`)
  - 巨潮调研记录 (`stock_zh_a_disclosure_relation_cninfo`)
  - 交易所列表 (上交所 `stock_info_sh_name_code`、深交所 `stock_info_sz_name_code`、北交所 `stock_info_bj_name_code`)
  - 百度估值 (`stock_zh_valuation_baidu`)
  - 同花顺行业板块名称 (`stock_board_industry_name_ths`)
  - 同花顺行业指数日线 (`stock_board_industry_index_ths`)
  - 新浪指数日线 (`stock_zh_index_daily`)
- **降级使用**：东财公告 (`stock_individual_notice_report`) 仅在巨潮公告失败时降级使用，不用于行情/财务/估值。
- **明确不使用**：东方财富行情与财务系列接口（不调用任何 `*_em` 函数获取行情或财务数据），与 `inv-valuation-engine` 保持一致。
- **已废弃**：雪球 `stock_individual_basic_info_xq`（AkShare 1.18+ 已不可用，KeyError 'data'），脚本保留调用路径但会自动降级到交易所列表。
- **代理**：部分 AkShare 接口在已设置 `HTTP(S)_PROXY` 时可能失败；脚本默认在调用 AkShare 前**临时清除**代理环境变量（与估值快照脚本一致），可用 `--keep-proxy` 关闭该行为。

## 美股 / 港股

- **用途**：报价与日线、估值与盈利质量等摘要字段、财报日期、新闻。
- **主来源**：**yfinance**（底层为 Yahoo Finance），与 `inv-valuation-engine` 的美港股数据体系一致。
- **降级来源（Yahoo 限流或不可用时）**：
  - 港股日线：AkShare 东财源 `stock_hk_daily`
  - 港股财务指标：AkShare 东财源 `stock_hk_financial_indicator_em`（PE/PB/ROE/净利率/股息率等 21 字段）
  - 港股实时行情：AkShare 新浪源 `stock_hk_spot`（名称/最新价/涨跌/成交量）
  - 美股日线：AkShare 东财源 `stock_us_daily`
- **限制**：受 Yahoo 可用性与地区网络影响；国内环境常出现限流，需 **`--proxy`** 或 `HTTPS_PROXY`；**不提供**美港股巨潮式 `announcements` 子命令。
- **代理**：美港股路径**不会**自动清除环境代理；建议显式传入 `--proxy http://127.0.0.1:7890`（端口按本机为准），或设置 **`YF_PROXY`**，脚本会在调用 yfinance 前自动写入 `HTTP_PROXY`/`HTTPS_PROXY`。
- **重试**：对超时、连接错误、429 等瞬时失败做有限次指数退避重试；`snapshot` 优先建立日线再拉 `info`，并在缺价时用日线回填；Yahoo 失败后自动尝试 AkShare 降级。

## 数据层统一

其他投资技能（`inv-valuation-engine`、`inv-qarp-strategy`、`inv-porter-five-forces`）通过 CLI 子进程调用本技能获取数据，不直接调用 AkShare / yfinance。本技能为所有投资相关技能的**唯一数据层**。
