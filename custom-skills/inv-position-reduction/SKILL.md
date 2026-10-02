---
name: inv-position-reduction
description: 减仓与换仓问题的薄入口：统一调用QARP资本配置判断，只补卖出和净换仓测算。
version: 2.0.0
trigger:
  - 减仓
  - 仓位调整
  - 换仓
  - 调仓
  - 减持
---

# 减仓与换仓入口

## 唯一策略

先加载 `inv-qarp-strategy`、`inv-valuation-engine`、`inv-stock-data`。不另维护减仓清单、补现金优先级或估值透支规则；所有持有、增持、减持、替换、暂缓统一走QARP四问与资本配置协议。

## 决策边界

直接读取 `~/.hermes/memories/PORTFOLIO.md` 与 `~/.hermes/memories/USER.md`；个人约束与默认分批节奏仅由USER定义。

- 从今天价格比较未来回报，不因浮亏、涨回成本或短期波动决定卖出。税费和交易成本仍计入。
- 逻辑破坏、严重治理或生存风险优先处理，不必等出现替代标的；紧急风险说明时效并由用户确认执行方式，不自动绕过USER约束。
- 仓位上限不是目标仓位；未超限也不证明适配，检查共同经济风险。
- 现金少不是卖出理由，除非用户明确要提款或改变资金安排；不得套旧现金最低线。
- 先卖A再买B作为一笔净换仓比较，不把名义卖出当降低风险或增加现金。

## 同口径比较

继续持有A、换入B、暂缓三案统一估值日、期限、盈利口径、币种与假设保守度；一主一辅及三情景由估值技能定义。对B的绝对吸引力和相对优势分别判断；证据不足不排序，不因主题更纯或PE更低而建议换仓。

ETF命题不清楚先区分行业看法、工具适配、价格及证据缺口，不把研究不足解释为应清仓；调用 `inv-etf-comparison` 的按需工具分析。

## 执行测算

目标仓位有依据后，用工具计算卖出数量、费用、净回款、买入数量以及交易后资产/仓位/行业集中度。按实际交易单位取整，所有币种先统一。买卖和资金流同时发生时联立重算，不沿用静态卖股公式。

如无提款、费用或同步买入，减股近似为：组合资产乘当前与目标仓位之差，再除以当前股价及币种换算；这只是计算，不是目标仓位依据。

## 专题参考（按问题调用，不新增门槛）

- `references/three-year-cross-sector-comparison.md`：财年、盈利及权益口径。
- `references/rotation-robustness-and-cross-listing.md`：跨市场、分红与排序敏感性。
- `references/incumbent-business-and-new-business-options.md`：已有业务与新业务去重。
- `references/thematic-etf-fit-and-exit.md`：ETF工具适配。
- `references/cash-replenishment-and-redeployment.md`：净资金流测算，不定义现金纪律。

## 记录与收尾

按QARP判断记录和受控台账协议记研究及建议；真实成交只记PORTFOLIO，不因讨论改股数。无实质变化复用已有研究，只复核受影响变量。

关键假设：说明比较依赖的保守盈利、终值与成本。
失效条件：说明何种可核实变化需要重新判断。
