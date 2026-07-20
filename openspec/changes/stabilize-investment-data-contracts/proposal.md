## Why

`inv-stock-data` 已是估值、五力和 QARP 的统一数据入口，但生产者与消费方的字段、聚合范围和历史窗口已经漂移：约 20 条日线被用于“5 年分位/250 日收益”，`all` 消费方读取不存在的子结果，五力仍读取旧版 Yahoo 结构。当前失败常表现为空字段而非硬失败，可能继续生成看似完整的估值或行业结论，因此需要先稳定跨技能数据契约与可评级门禁。

## What Changes

- 为 `inv-stock-data` 公开 JSON payload 引入统一 envelope 和 `schema_version`，明确 `status`、市场、标的、数据时点、来源尝试、降级等级、缺口与实际观测窗口。
- **BREAKING**：统一 A 股、港股、美股和 ETF 快照及日线字段；修正 ETF NAV 字段、港股 DataFrame 降级崩溃，并移除消费者对旧 Yahoo 嵌套结构的依赖。
- **BREAKING**：明确 `all` 聚合命令的组成和部分成功语义；消费方不得读取契约外字段，也不得仅凭 `snapshot` 判断整个聚合结果完整。
- 为日线命令增加显式历史窗口/数量请求与实际覆盖元数据；样本不足时不生成 52 周、250 日或 5 年指标。
- 让 `inv-valuation-engine` 按数据完整性进入 `ok`、`partial`、`insufficient_for_valuation` 或 `upstream_failed` 状态；数据不足时不得默认“合理”或输出操作参考。
- 将 `inv-porter-five-forces` 迁移到新契约；核心事实不足时输出机器可读缺口，不生成高置信度预评分。
- 为 A/H/US/ETF 数据契约、历史窗口、聚合结果和估值/五力消费方增加离线 fixture contract tests。
- 同步受影响 Skill 文档，明确字段所有权、兼容边界和失败/降级语义。

## Capabilities

### New Capabilities
- `investment-data-contracts`: 定义 `inv-stock-data` 跨市场公开 payload、聚合命令、历史窗口、数据质量和消费方兼容要求。
- `valuation-readiness-gate`: 定义估值所需最小数据集、不可评级状态、缺口披露及操作参考生成门禁。
- `five-forces-data-adapter`: 定义五力分析对统一数据契约的消费、缺口处理和预评分置信度要求。

### Modified Capabilities
- `inv-stock-data-modular`: 调整 `commands.py` 与入口层的行为要求，使模块化实现承载版本化契约、显式历史窗口和一致的降级结果，而非保持旧 JSON 结构不变。

## Impact

- 影响技能：`inv-stock-data`（契约生产者）、`inv-valuation-engine` 与 `inv-porter-five-forces`（直接消费方）、`inv-qarp-strategy`（估值输出的间接消费方）。
- 主要代码：`custom-skills/inv-stock-data/scripts/`、`custom-skills/inv-valuation-engine/scripts/`、`custom-skills/inv-porter-five-forces/scripts/` 及对应 `SKILL.md` / references。
- API 影响：CLI JSON 输出和部分失败语义会发生破坏性变化；内部调用者必须同步迁移，不提供无限期旧字段双写。
- 依赖不新增实时服务；测试使用本地 fixture/mock，不将 Yahoo、AkShare 等网络可用性作为确定性验收条件。
