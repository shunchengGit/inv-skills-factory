## MODIFIED Requirements

### Requirement: commands 模块职责与导出
`commands.py` SHALL 导出所有公开 `cmd_*` 子命令函数和所需降级函数，并通过契约模块构造 `investment-data-contracts` v1 envelope。模块 SHALL 依赖 `fetch_*`、`market`、`utils` 和 `_shared.proxy`，但 SHALL NOT 将供应商原始 payload 直接暴露给消费者。`cmd_daily` SHALL 接受显式历史窗口参数，`cmd_all` SHALL 仅聚合 snapshot、financial 和 financials 并保留各组件状态。

#### Scenario: cmd_snapshot 跨模块调用
- **WHEN** `cmd_snapshot("600519", "a")` 执行
- **THEN** 调用 A 股抓取模块并返回 schema v1 标准 snapshot envelope，而不是供应商原始键集合

#### Scenario: 降级回退路径
- **WHEN** Yahoo Finance 返回空数据且港股降级源成功
- **THEN** `cmd_snapshot_yahoo` 使用降级数据生成 partial envelope，记录主来源失败和 fallback 成功，不得因 DataFrame 布尔判断崩溃

#### Scenario: 日线窗口透传
- **WHEN** `cmd_daily` 收到 `period="5y"` 且未指定 limit
- **THEN** 抓取层接收长期窗口请求，响应保留完整可用序列和实际 window 元数据，不得固定截取 20 条

#### Scenario: all 组件范围
- **WHEN** `cmd_all` 执行
- **THEN** 仅聚合 snapshot、financial、financials 三个有独立状态的组件，不隐式承诺 daily、announcements 或 relations

### Requirement: 入口文件职责
`cs_stock_info.py` SHALL 仅包含 CLI 参数、市场级代理管理、命令 dispatch、统一退出码和渲染入口，不包含数据抓取或领域计算。CLI SHALL 支持 daily 的历史窗口参数，并按 envelope 状态返回可判定退出结果：`ok` 为成功，`partial` 保留可消费输出并显式标识降级，`failed` 返回非零退出码。

#### Scenario: 入口文件导入所有模块
- **WHEN** `cs_stock_info.py` 被执行
- **THEN** 从 commands、render、market 和契约模块导入公开接口，且入口本身不实现抓取逻辑

#### Scenario: 入口文件处理代理
- **WHEN** 市场为港股或美股
- **THEN** 按共享代理策略配置请求环境，并把代理不可用记录为结构化来源或 gap

#### Scenario: 命令行输出采用新契约
- **WHEN** 运行 `python cs_stock_info.py snapshot 600519 --output json`
- **THEN** 输出 `investment-data-contracts` v1 envelope；旧 JSON shape 不再作为公共兼容承诺

#### Scenario: failed 返回非零
- **WHEN** 命令返回 `status: "failed"`
- **THEN** CLI 输出结构化失败 envelope 并以非零退出码结束
