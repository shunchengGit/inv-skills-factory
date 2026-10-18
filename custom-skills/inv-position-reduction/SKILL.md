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

## 路由

加载 `inv-qarp-strategy`，由其统一选择行情刷新、事件增量或新增资本与换仓模式；取数与估值分别交 `inv-stock-data`、`inv-valuation-engine`。本入口不另立策略、现金闸门或财务门槛，也不因用户说“加/减仓”预设动作。新增资本与换仓须完整情景及代表性替代比较，不重复全组合或大矩阵；四问、证据、反证、同口径回报及门禁只在 QARP 定义。

直接读最新 `~/.hermes/memories/USER.md`、`PORTFOLIO.md` 与当前判断基准：用户约束只由 USER 定义，仓位/现金/成交以 PORTFOLIO 为权威。资金可用性约束执行，不替代价值判断；紧急治理或生存风险交 QARP 优先复核。

## 执行测算

目标仓位有依据后，用工具按交易单位取整，计算卖出数量、费用、净回款、同步买入数量与交易后资产/仓位/行业集中度；币种统一，买卖/提款/费用同时发生时联立重算。净换仓是一笔资金与风险转换，不能把名义卖出等同降风险。

输出 QARP 结论引用、执行数量/成本/资金与交易后组合变化、不可执行原因；关键假设及失效条件引用有效研究，不重复评审。触价只触发复核，不是自动交易授权。

## 专题参考（按问题调用，不新增策略门槛）

- `references/comparative-quality-framework.md`：跨公司质量比较。
- `references/three-year-cross-sector-comparison.md`：财年、盈利及权益口径。
- `references/rotation-robustness-and-cross-listing.md`：跨市场、分红与排序敏感性。
- `references/incumbent-business-and-new-business-options.md`：已有业务与新业务去重。
- `references/thematic-etf-fit-and-exit.md`：ETF工具适配；必要时调用 `inv-etf-comparison`。
- `references/cash-replenishment-and-redeployment.md`：净资金流测算。

## 责任边界

研究及建议按 QARP 与 tracker 受控台账协议记录，必要写入读回验证。建议、用户确认、实际成交分离；讨论不改持仓，真实成交只由 tracker 记账，不因缺研究卡拒绝记账。
