## ADDED Requirements

### Requirement: 五力使用标准数据 adapter
`inv-porter-five-forces` SHALL 通过单一 adapter 消费 `investment-data-contracts` v1 envelope，并将标准快照映射到五力领域模型。业务逻辑 SHALL NOT 直接读取旧 `quote`、`yahoo_fundamentals`、`stats_52w`、供应商原始键或其他未声明路径。

#### Scenario: 消费港美股标准快照
- **WHEN** adapter 收到包含标准 `price`、`currency`、`sector`、`industry` 和 `fundamentals` 的 v1 快照
- **THEN** 五力底稿正确填充对应事实，不再从旧嵌套路径读取空值

#### Scenario: 收到未知 schema 版本
- **WHEN** adapter 收到不支持的 major schema 版本
- **THEN** 返回机器可读的不兼容错误，不得按旧字段猜测解析

### Requirement: 数据缺口与来源向上传递
五力底稿 SHALL 保留上游 `status`、`data_as_of`、`sources` 和结构化 `gaps`，并区分主来源、fallback 和缺失数据。不得以默认事实值掩盖上游失败。

#### Scenario: Yahoo 失败但 fallback 可用
- **WHEN** 快照为 partial 且 fallback 提供价格和公司信息
- **THEN** 五力底稿保留可用事实，同时标记 fallback 来源和仍未解决的缺口

#### Scenario: 核心公司信息缺失
- **WHEN** 名称、行业或业务描述等核心事实缺失
- **THEN** 底稿明确列出缺口，不得虚构行业或公司画像

### Requirement: 每个力具有证据就绪度
每个力的结构化预评分 SHALL 包含 `evidence_count`、`gaps`、`confidence` 和可空 `score`。当现有框架定义的最小证据条件不满足时，`score` MUST 为 `null`，不得以中性默认分生成看似完整的总分。

#### Scenario: 某一力证据不足
- **WHEN** 供应商议价能力仅有零散或不足最低条件的证据
- **THEN** 该力返回 `score: null`、低 confidence 和具体 gap，不参与数值总分

#### Scenario: 五力均满足证据条件
- **WHEN** 每个力均满足对应最小证据条件
- **THEN** 系统可生成各力预评分和汇总分，并保留每项证据来源

### Requirement: 结构化底稿与最终研究相分离
数据快照缺失 SHALL 只限制结构化预评分的置信度，不得错误声明整个五力研究不可进行。最终 LLM 分析可结合明确标注来源的外部研究补充证据，但补充内容不得回写为 `inv-stock-data` 事实。

#### Scenario: 市场快照失败但外部研究可用
- **WHEN** 数据层快照 failed，但用户仍要求行业五力研究
- **THEN** 系统输出上游失败状态并允许进入外部研究流程，结构化预评分保持不可用，外部证据单独标注

### Requirement: 五力 adapter 离线契约测试
五力 SHALL 使用与数据层一致的 A/H/US fixture 验证字段映射、未知版本、partial、fallback 和证据不足路径。

#### Scenario: 旧字段回归检查
- **WHEN** 测试扫描或执行五力 adapter
- **THEN** 港美股标准 fixture 能正确映射，且代码不再依赖旧 `quote`、`yahoo_fundamentals` 或 `stats_52w` 路径
