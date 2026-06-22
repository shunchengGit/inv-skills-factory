# A股 PE 数据结构说明

## 问题

inv-stock-data snapshot 对 A股返回的 PE 数据分布在两个层级：

1. **顶层 metrics**：`valuation_pe_ttm` 和 `trailing_pe` — 经常返回 `null`（百度 API 对部分 A 股不返回 `pe_ttm`）
2. **嵌套 valuation 子对象**：`valuation.pe_static` — 通常有值（百度静态 PE）

## 硬规则（来自用户投资分析硬规则）

**inv-stock-data PE 兜底规则**：百度估值 API 对部分 A 股不返回 `pe_ttm`，此时用 `pe_static`（静态 PE）填入 PE 列并标注 `(静)`；不得留空或标 N/A。

## 实际操作

1. 运行 `snapshot` 后，先检查 `metrics.valuation_pe_ttm` 和 `metrics.trailing_pe`
2. 若两者均为 `null`，检查 `metrics.valuation`（或 snapshot 输出中的 `valuation` 子对象）中的 `pe_static`
3. 用 `pe_static` 作为 PE 值，标注 `(静)`
4. 若 `pe_static` 也不可用，用新浪 EPS + 收盘价手动计算：`PE = price / sina_eps_annual`

## 常见案例

- **福耀玻璃 600660**：`valuation_pe_ttm: null`，`trailing_pe: null`，但 `valuation.pe_static: 15.69` → 使用 15.69(静)
- **五粮液 600519**：通常 `pe_ttm` 有值，无需兜底

## 注意

- 静态 PE 和 TTM PE 口径不同：静态 PE 基于最近年报 EPS，TTM PE 基于最近 4 个季度滚动 EPS
- 涉及"某价格对应多少倍 PE"的表述时，必须明确标注口径
- 若公司刚发布季报且业绩变化大，静态 PE 可能滞后，需提醒用户