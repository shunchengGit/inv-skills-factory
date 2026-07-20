## ADDED Requirements

### Requirement: 估值就绪状态
估值引擎 SHALL 将结果分类为 `ok`、`partial`、`insufficient_for_valuation` 或 `upstream_failed`。状态 SHALL 根据数据层状态、可评级指标数量、核心估值锚和关键缺口确定，而不是仅降低自由文本 confidence。

#### Scenario: 上游快照整体失败
- **WHEN** 数据层未返回可用公司快照或核心调用为 `failed`
- **THEN** 估值状态为 `upstream_failed`，且 `conclusion` 和 `action_reference` 均为 `null`

#### Scenario: 可评级指标不足
- **WHEN** 可评级指标少于两个，或不存在 PE、PB、显式手工估值输入中的任一核心估值锚
- **THEN** 状态为 `insufficient_for_valuation`，不得默认结论为“合理”

#### Scenario: 达到最低条件但存在关键缺口
- **WHEN** 至少两个指标可评级且存在核心估值锚，但数据层为 partial、使用关键 fallback 或存在关键缺口
- **THEN** 状态为 `partial`，系统可输出受限估值结论但 `action_reference` MUST 为 `null`

#### Scenario: 完整数据可评级
- **WHEN** 最低评级条件满足且无关键数据缺口
- **THEN** 状态为 `ok`，系统可按现有评分规则生成五档结论和操作参考

### Requirement: 历史指标遵循实际窗口
估值引擎 SHALL 显式请求所需历史窗口，并仅在 `investment-data-contracts` 定义的观测门槛满足时计算 52 周位置、250 日收益和 5 年价格分位代理。

#### Scenario: 数据层返回短窗口
- **WHEN** 请求五年历史但响应只有 20 个观测
- **THEN** 估值 Snapshot 将三个长期指标设为 `null`，保留上游 window，并将对应缺口纳入 readiness 判定

#### Scenario: 数据层返回完整五年窗口
- **WHEN** 响应满足五年分位的观测数与日期覆盖门槛
- **THEN** 估值引擎使用完整序列计算分位，不得再次截短后计算

### Requirement: 估值报告披露数据质量
JSON、text 和 Markdown 输出 SHALL 展示估值状态、上游数据状态、数据时点、来源和关键 `data_gaps`。任何不可评级结果 SHALL 以显著、机器可读的方式说明原因。

#### Scenario: Markdown 输出不可评级结果
- **WHEN** 估值状态为 `insufficient_for_valuation`
- **THEN** Markdown 明确显示“数据不足，无法评级”、列出关键缺口，且不出现“逢低加仓”“持有”“减仓”等操作参考

#### Scenario: JSON 输出部分评级
- **WHEN** 估值状态为 `partial`
- **THEN** JSON 保留受限 conclusion、`action_reference: null`、上游状态和结构化缺口

### Requirement: QARP 尊重估值门禁
`inv-qarp-strategy` SHALL 将 `upstream_failed` 和 `insufficient_for_valuation` 视为估值闸门未通过，将 `partial` 视为需要显著降置信度的输入；不得自行把不可评级结果转换为五档估值或买入动作。

#### Scenario: QARP 收到不可评级结果
- **WHEN** QARP 消费的估值状态为 `insufficient_for_valuation`
- **THEN** QARP 明确要求补数或手工情景估值，不得输出基于自动估值的买入结论

### Requirement: 估值就绪度离线回归测试
估值引擎 SHALL 使用固定 fixture 覆盖上游全失败、仅价格可用、部分财务可用、完整数据以及历史样本不足场景。

#### Scenario: 运行就绪度测试矩阵
- **WHEN** 离线测试依次输入上述 fixture
- **THEN** 每个 fixture 产生预期状态、结论和 action 门禁，且不依赖实时 Yahoo 或 AkShare
