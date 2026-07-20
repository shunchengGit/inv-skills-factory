## ADDED Requirements

### Requirement: 统一公开数据 envelope
`inv-stock-data` 的每个公开命令 SHALL 返回包含 `schema_version`、`command`、`status`、`symbol`、`data_as_of`、`sources`、`gaps`、`notes` 和 `data` 的统一 envelope。`status` MUST 为 `ok`、`partial` 或 `failed`；调用方 SHALL NOT 依赖供应商原始字段或命令私有的错误形状。

#### Scenario: 完整快照成功
- **WHEN** 快照命令取得该市场契约要求的全部核心数据
- **THEN** 返回 `schema_version: "1.0"`、`status: "ok"`、规范化 symbol 和领域数据，且 `gaps` 为空

#### Scenario: 部分数据源失败
- **WHEN** 至少存在可消费领域数据，但一个必需字段或组件获取失败
- **THEN** 返回 `status: "partial"`，并在 `gaps` 中记录 `code`、`field`、`reason` 和 `retryable`

#### Scenario: 所有数据源失败
- **WHEN** 命令没有取得任何可消费领域数据
- **THEN** 返回 `status: "failed"`、非空 `gaps` 和空的领域数据，不得伪造默认事实值

### Requirement: 跨市场标准字段
A 股、港股、美股和 ETF 的 snapshot SHALL 在 `data` 中使用稳定的标准字段；市场特有字段 SHALL 位于明确的市场子结构，不得要求消费者读取 Yahoo、AkShare、Sina 或 QQ 的原始键名。ETF NAV SHALL 使用数据源实际提供的最新净值、日期、累计净值和折溢价字段生成标准结构。

#### Scenario: 港美股快照字段
- **WHEN** 港股或美股快照成功
- **THEN** `data` 直接提供标准化的 `name`、`currency`、`sector`、`industry`、`price`、`fundamentals` 和可用的日线摘要，而不是旧 `quote` 或 `yahoo_fundamentals` 路径

#### Scenario: ETF 净值成功
- **WHEN** ETF 净值源返回 `latest`、`date`、`acc_nav` 和 `premium_pct`
- **THEN** snapshot 的标准 `nav` 结构 SHALL 保留这些值，不得因读取不存在的 `latest_nav` 等字段而返回空值

### Requirement: 数据来源与降级可追踪
每次供应商尝试 SHALL 在 `sources` 中记录来源名称、状态和是否为 fallback。fallback 成功不得伪装为主来源成功，失败原因不得仅存在于自由文本说明中。

#### Scenario: Yahoo 失败后港股新浪成功
- **WHEN** Yahoo 日线失败且港股新浪返回非空 DataFrame
- **THEN** 命令成功使用新浪数据，返回 `status: "partial"` 或符合契约的降级状态说明，并记录 Yahoo 失败和新浪 fallback 成功；不得对 DataFrame 做布尔值求值

#### Scenario: 主来源成功
- **WHEN** 主来源成功且未调用降级来源
- **THEN** `sources` 标记主来源成功和 `fallback: false`，且不声称调用了未执行的来源

### Requirement: 显式历史窗口
`daily` 命令 SHALL 接受显式 `period` 和可选 `limit`，至少支持 `1mo`、`1y`、`5y` 和 `max`。响应 SHALL 在 `window` 中返回请求窗口、有效观测数、首日和末日；抓取层不得在请求长期窗口后无条件截为 20 条。

#### Scenario: 请求五年日线
- **WHEN** 调用方请求 `period: "5y"` 且数据源返回完整序列
- **THEN** 响应保留完整的可用五年序列（除非调用方显式给出 `limit`），并报告实际观测数和日期范围

#### Scenario: 数据源只返回短窗口
- **WHEN** 请求 `5y` 但实际只取得约 20 个交易日
- **THEN** 响应报告真实窗口和观测数、返回 `partial` 并记录覆盖不足 gap，不得将其标记为五年完整数据

### Requirement: 长周期指标样本门槛
消费历史数据计算指标时 SHALL 同时检查有效观测数和日期覆盖。52 周区间至少需要 200 个有效收盘观测且覆盖 350 天；250 日收益至少需要 251 个有效收盘观测；5 年价格分位代理至少需要 1000 个有效收盘观测且覆盖 4.5 年。

#### Scenario: 二十条输入不生成长期指标
- **WHEN** 历史输入仅有 20 个有效收盘观测
- **THEN** 52 周位置、250 日收益和 5 年分位代理均为 `null`，并分别记录样本不足 gap

#### Scenario: 五年覆盖满足门槛
- **WHEN** 历史输入包含至少 1000 个有效收盘观测且覆盖至少 4.5 年
- **THEN** 系统可计算 5 年价格分位代理，并在结果中保留观测窗口元数据

### Requirement: `all` 聚合组成与组件状态
`all` v1 SHALL 仅承诺 `snapshot`、`financial` 和 `financials` 三个组件。每个组件 SHALL 有独立状态、数据和缺口；外层状态 SHALL 根据组件状态汇总。`daily`、`announcements` 和 `relations` 不得被调用方假定存在。

#### Scenario: 所有核心组件成功
- **WHEN** `snapshot`、`financial` 和 `financials` 均成功
- **THEN** `all` 返回 `status: "ok"`，并在 `data.components` 中提供三个状态明确的组件

#### Scenario: 快照成功但财务三表失败
- **WHEN** `snapshot` 成功但 `financials` 失败
- **THEN** `all` 返回 `status: "partial"`，保留成功组件并记录失败组件 gap；调用方不得仅检查 snapshot 后认定整体完整

#### Scenario: 消费者需要事件和历史数据
- **WHEN** 估值或其他消费者需要 `daily`、`announcements` 或 `relations`
- **THEN** 消费者显式调用对应命令，不得从 `all` 读取契约外字段

### Requirement: 离线数据契约测试
系统 SHALL 为 A 股、港股、美股和 ETF 提供无网络 fixture contract tests，覆盖成功、部分成功、失败、fallback、历史窗口和聚合组件状态。

#### Scenario: 干净环境运行契约测试
- **WHEN** 外部行情服务不可访问但本地测试依赖完整
- **THEN** 所有数据契约和消费方门禁测试仍可确定性运行，不把实时网络可用性作为通过条件
