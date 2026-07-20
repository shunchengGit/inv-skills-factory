## Context

`inv-stock-data` 同时被估值、五力和 QARP 视为唯一数据层，但目前公开接口没有稳定版本或共享模型。命令函数返回各自形状的字典，调用者通过散落的键路径解析；这已造成三类问题：生产者与消费者字段漂移、聚合成功被误判为完整成功，以及真实观测窗口与指标名称不符。

本变更横跨 `inv-stock-data`、`inv-valuation-engine` 和 `inv-porter-five-forces`。实现必须保持 Python 3.10+ 和 `uv run` 模型，不增加在线服务；确定性验证使用 fixture/mock，实时数据源只用于可选 smoke test。

## Goals / Non-Goals

**Goals:**

- 建立可版本化、机器可判定的跨市场数据 envelope，统一成功、部分成功、失败、来源、缺口和时点语义。
- 让历史指标严格依据实际观测窗口生成，不再将短窗口静默冒充 52 周、250 日或 5 年数据。
- 明确 `all` 的组成及每个组件状态，阻止消费者读取契约外字段。
- 在同一变更内迁移估值和五力两个直接消费者，消除旧 Yahoo 字段路径。
- 让估值在数据不足时进入不可评级状态，让五力预评分显式反映证据不足。
- 用离线 contract tests 固化 A/H/US/ETF 的核心 payload 和消费者门禁。

**Non-Goals:**

- 不重写 AkShare、Yahoo、Sina 等供应商抓取实现，也不保证实时网络可用性。
- 不在本变更中重构 portfolio 写回、知识库事务、代理作用域或全仓 CI；但新契约应便于这些后续变更消费。
- 不为旧 JSON shape 提供长期双写兼容层，也不引入通用 RPC 服务或数据库。
- 不改变估值阈值本身、五力理论框架或 QARP 决策纪律。

## Decisions

### 1. 统一 envelope，领域数据放入 `data`

所有公开命令返回同一顶层结构：

```json
{
  "schema_version": "1.0",
  "command": "daily",
  "status": "ok",
  "symbol": {"input": "AAPL", "code": "AAPL", "market": "us"},
  "data_as_of": "2026-07-20",
  "sources": [{"name": "yahoo", "status": "ok", "fallback": false}],
  "gaps": [],
  "notes": [],
  "window": {
    "requested": "5y",
    "observations": 1258,
    "first_date": "2021-07-21",
    "last_date": "2026-07-20"
  },
  "data": {"daily": []}
}
```

`status` 仅取 `ok | partial | failed`：全部必需字段满足为 `ok`，仍有可用数据但存在组件/字段缺口为 `partial`，无可消费领域数据为 `failed`。`gaps` 使用结构化对象，至少包含 `code`、`field`、`reason`、`retryable`；`notes` 只承载非门禁型说明。

选择 envelope 而不是继续追加 `_notes`、`error` 等命令特有字段，是为了让上游用统一逻辑判断状态。替代方案是维持旧结构并提供 adapter；这会继续保留多个事实来源，因此只允许在迁移代码内部使用短生命周期解析辅助，不在公共输出中长期双写。

### 2. 契约模型位于 `inv-stock-data`，消费者只通过 adapter 访问

在 `inv-stock-data/scripts/` 中建立无网络依赖的契约构造、验证和字段访问模块。CLI、进程内调用和 fixture tests 共用该模型。估值与五力各保留薄 adapter，把 envelope 转为自身领域模型；业务计算不再直接 `_dig()` 任意供应商或旧 payload 路径。

不把投资领域 schema 放进 `_shared`，因为 `_shared` 只承载无业务含义的基础设施。也不立即发布独立 Python package，以避免扩大本次迁移范围。

### 3. `all` 固定聚合核心组件，不隐式承诺事件与历史数据

`all` v1 固定包含 `snapshot`、`financial`、`financials` 三个组件，与当前生产者实际行为一致。每个组件具有独立 `status`、`gaps` 和 `data`；外层状态由组件状态汇总。

`daily`、`announcements`、`relations` 不属于 v1 `all`，需要它们的消费者必须显式调用对应命令。这比把所有端点塞入 `all` 更能控制延迟、限流和各市场能力差异。若未来需要批量聚合，应新增显式 `include` 参数并提升 minor schema 版本，而不是让消费者猜测字段是否存在。

### 4. 历史窗口由请求和实际覆盖共同定义

`daily` 接受显式 `period`（至少支持 `1mo`、`1y`、`5y`、`max`）和可选 `limit`；抓取层不得在请求 5 年后无条件截成 20 条。响应必须返回 `requested`、`observations`、`first_date`、`last_date`。

指标门槛采用可测试规则：

- 52 周区间：至少 200 个有效收盘观测，且首尾日期覆盖至少 350 天；
- 250 日收益：至少 251 个有效收盘观测；
- 5 年价格分位代理：至少 1000 个有效收盘观测，且覆盖至少 4.5 年。

未达到门槛时相关指标为 `null`，并加入结构化 gap，禁止退化为较短窗口后沿用原字段名。选择观测数与日期覆盖双门槛，是为了同时防止停牌/缺口和简单截断造成的假覆盖。

### 5. 估值状态与数据层状态分离

估值报告引入 `ok | partial | insufficient_for_valuation | upstream_failed`：

- `upstream_failed`：没有可用公司快照或数据层核心调用失败；
- `insufficient_for_valuation`：少于两个可评级指标，或缺少至少一个核心估值锚（PE、PB 或显式手工估值输入）；
- `partial`：达到最低评级条件，但存在关键数据缺口或只能使用降级来源；
- `ok`：达到最低评级条件且无关键缺口。

`insufficient_for_valuation` 和 `upstream_failed` 的 `conclusion`、`action_reference` 必须为 `null`；`partial` 可给出带限制的估值结论，但 `action_reference` 仍为 `null`。只有 `ok` 可以映射操作参考。所有 text、Markdown 和 JSON 输出都列出状态、缺口、时点及来源。

替代方案是只降低 confidence；现状证明低置信度仍容易被当作有效方向结论，因此采用显式不可评级状态。

### 6. 五力 adapter 输出证据就绪度，不用默认值掩盖缺失

五力脚本从新快照的扁平标准字段读取公司、行业、价格和 fundamentals。每个力记录 `evidence_count`、`gaps` 和 `confidence`。未达到该力定义的最小证据数时，预评分为 `null`，而不是用中性默认分生成看似完整的总分；整体状态由各力就绪度汇总。

五力最终定性分析仍可由 LLM 结合外部检索完成，本变更只约束结构化底稿和预评分，不把缺少市场快照等同于无法开展任何行业研究。

### 7. fixture 是契约事实来源，网络 smoke 不阻断实现验收

为 A 股、港股、美股、ETF 保存最小匿名 fixture，覆盖正常、部分、失败及 fallback。生产者测试验证 envelope；估值和五力测试直接消费同一 fixture，形成跨技能 contract test。测试还必须覆盖 20 条历史输入不得生成长期指标，以及 `all` 缺少组件时的部分成功。

不录制含时间敏感结论的整页真实响应；fixture 仅保留契约所需字段，避免供应商噪声和敏感数据。

## Risks / Trade-offs

- [破坏性 JSON 变更影响未识别消费者] → 全仓搜索命令名和旧字段路径；在同一变更迁移所有仓内消费者，并由 contract tests 阻断遗留读取。
- [统一 envelope 增加 payload 层级和 adapter 代码] → 契约构造和验证集中在一个模块，消费者 adapter 保持薄层，禁止复制 schema。
- [严格历史门槛会让更多指标暂时为空] → 明确 gap 和实际窗口；宁可不可用，也不输出名称与样本不符的指标。
- [`all` 不再被误认为包含所有端点，调用次数可能增加] → 消费者仅按分析需要显式请求；未来通过显式 `include` 扩展，而非隐式加字段。
- [数据层 `partial` 与估值层 `partial` 容易混淆] → 两层使用各自独立状态枚举，并在报告中分别保留 upstream status 与 valuation status。
- [五力预评分出现更多 null] → 将证据缺口暴露给 LLM 和用户，避免默认分伪造置信度。

## Migration Plan

1. 先建立契约模型、fixture 和生产者测试，不切换消费者。
2. 修复 ETF 字段与港股 DataFrame fallback，并让 snapshot/daily/all 生成 v1 envelope。
3. 迁移估值 adapter、历史请求和 readiness gate；删除旧 shape 读取。
4. 迁移五力 adapter 和证据就绪度；删除旧 Yahoo 嵌套字段读取。
5. 更新 SKILL/references 和 QARP 对估值状态的消费说明。
6. 运行离线 contract tests、现有 curator tests、skill linter；再执行可选的各市场 smoke test。
7. 完成迁移后直接移除旧字段，不进入长期双写期。

回滚时按单个提交整体回退生产者与消费者，不允许只回退数据层或只回退某个消费方；schema 版本和消费者必须保持原子一致。

## Open Questions

- `period` 是否需要在 v1 同时支持自定义起止日期，还是先限定枚举并在后续 minor 版本扩展？默认先采用枚举。
- 五力每个力的最小 `evidence_count` 应由现有框架规则静态定义，还是只输出证据数、暂不阻断预评分？实现前应以 `porter-framework.md` 的现有评分输入确认阈值。
- `partial` 估值是否应保留五档 conclusion 供研究参考？本设计保留结论但禁止 action；如果测试发现容易误用，可进一步收紧为 conclusion 也为空。
