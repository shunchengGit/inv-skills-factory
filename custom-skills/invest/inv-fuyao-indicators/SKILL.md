---
name: inv-fuyao-indicators
description: 当需要追踪福耀玻璃前置指标时使用，包括纯碱价格、天然气、汇率、汽车销量等成本收入端数据
version: 4.0.0
commands:
  - /fuyao_indicators - 完整分析：获取数据 → Agent分析 → 输出报告
  - /fuyao_indicators_data - 仅获取数据快照（JSON），不做分析
dependencies:
  - _shared
---

# 福耀玻璃前置指标分析

> 版本 4.0.0 — 配置驱动框架（共享 `_shared/indicators/`），11 指标，agent_search 标记搜索补充

## 用法

- `/fuyao_indicators` — 完整分析：获取数据 → 分析 → 输出报告
- `/fuyao_indicators_data` — 仅获取数据快照（JSON），不做分析

## 执行流程

### /fuyao_indicators（完整分析）

1. **获取数据快照**
   ```bash
   uv run {baseDir}/scripts/fuyao_indicators.py
   ```
   如果汽车销量 `parse_status` 不是 `success`，用 `--raw-cpca` 重跑获取乘联会原文：
   ```bash
   uv run {baseDir}/scripts/fuyao_indicators.py --raw-cpca
   ```

2. **读取传导机制框架**
   读取 `{baseDir}/references/indicator-framework.md`

3. **逐指标分析**
   对快照中每个指标，结合以下信息输出：
   - **信号**：偏多 / 中性 / 偏空
   - **评分**：-1.0 到 +1.0（-1=强利空，0=中性，+1=强利好）
   - **理由**：1-2句话，引用具体数据

   分析依据（按优先级）：
   - `scoring_guide`：量化评分区间（新增），优先参考
   - `direction` 和 `transmission_summary`：传导方向和机制
   - `trend_20d` / `trend_60d`：短期和中期趋势
   - `percentile_120d`：历史分位（极端分位=强信号）
   - `yoy_change` / `mom_change`：同比/环比变化（汽车销量）
   - `volatility_warning`：波动剧烈时降低信号强度
   - 指标间交互效应（如人民币贬值+运价下跌对出口利润的叠加效应）

   **方向规则**：
   - `cost`：价格↓→成本↓→利好→偏多信号
   - `revenue`：数值↑→收入↑→利好→偏多信号
   - `cost_reverse`：价格↓→成本↓→利好→偏多信号（与 cost 方向相同，但显示标注为"成本端(反向)"）

4. **综合判断**
   - 按各指标 `weight` 加权汇总评分
   - 考虑指标间交互效应，可适当调整
   - 输出综合信号（偏多/中性/偏空）、置信度（高/中/低）、一句话理由

5. **按输出模板格式输出报告**

### /fuyao_indicators_data（仅数据）

```bash
uv run {baseDir}/scripts/fuyao_indicators.py --output text
```

直接展示文本快照，不做分析。

## 输出模板

```
# 福耀玻璃前置指标分析报告
> 数据获取时间：{fetched_at}

## 综合判断

**信号：{偏多/中性/偏空}** | 评分：{+0.XX} | 置信度：{高/中/低}

{一句话综合理由}

---

## 各指标详情

### 纯碱价格 (成本端，权重20%)
- 当前：{price} 元/吨 | 合约：{contract_name}
- 20日趋势：{trend_20d} | 60日趋势：{trend_60d} | 120日分位：{percentile}%
- **信号：{偏多/中性/偏空}** (评分 {score}) — {理由}

### NYMEX天然气 (成本端，权重12%)
- 当前：{price} 美元/百万BTU
- 20日趋势：{trend_20d} | 60日趋势：{trend_60d} | 120日分位：{percentile}%
- **信号：{偏多/中性/偏空}** (评分 {score}) — {理由}

### USD/CNY汇率 (收入端，权重18%)
- 当前：{price}
- 20日趋势：{trend_20d} | 60日趋势：{trend_60d} | 120日分位：{percentile}%
- **信号：{偏多/中性/偏空}** (评分 {score}) — {理由}

### 中国汽车销量 (收入端，权重18%)
- {latest_month}：零售 {retail} 万辆，同比 {yoy}，环比 {mom}
- **信号：{偏多/中性/偏空}** (评分 {score}) — {理由}

### 集运指数(欧线) (成本端(反向)，权重12%)
- 当前：{price} | 合约：{contract_name}
- 20日趋势：{trend_20d} | 60日趋势：{trend_60d} | 120日分位：{percentile}%
- **信号：{偏多/中性/偏空}** (评分 {score}) — {理由}

### 新能源车渗透率 (收入端，权重5%)
- {latest_month}：渗透率 {penetration}%
- **信号：{偏多/中性/偏空}** (评分 {score}) — {理由}

### 美国汽车销量 (收入端，权重10%)
- {latest_month}：SAAR {saar} 百万辆，同比 {yoy}%
- **信号：{偏多/中性/偏空}** (评分 {score}) — {理由}

### 欧洲汽车销量 (收入端，权重5%)
- {latest_month}：注册量 {registrations} 万辆，同比 {yoy}%
- **信号：{偏多/中性/偏空}** (评分 {score}) — {理由}

---

## 综合评分

| 指标 | 方向 | 权重 | 评分 | 加权 |
|------|------|------|------|------|
| 纯碱价格 | 成本端 | 20% | {score} | {weighted} |
| NYMEX天然气 | 成本端 | 12% | {score} | {weighted} |
| USD/CNY汇率 | 收入端 | 18% | {score} | {weighted} |
| 中国汽车销量 | 收入端 | 18% | {score} | {weighted} |
| 集运指数(欧线) | 成本端(反向) | 12% | {score} | {weighted} |
| 新能源车渗透率 | 收入端 | 5% | {score} | {weighted} |
| 美国汽车销量 | 收入端 | 10% | {score} | {weighted} |
| 欧洲汽车销量 | 收入端 | 5% | {score} | {weighted} |
| **合计** | | **100%** | | **{total}** |

## 数据与说明

- K线类指标（纯碱/天然气/汇率/集运）：东方财富实时行情 + K线数据，合约按成交量选主力
- 汽车销量/新能源渗透率：乘联会(CPCA) Playwright 抓取
- 美国汽车销量：FRED API（`TOTALSA`），脚本自动获取
- 欧洲汽车销量：ACEA 数据，搜索补充（推荐并行搜索，比逐个搜索更高效）
- 期货合约为近月主力合约（按成交量选），避免快到期合约的价格失真
- 集运指数(欧线)期货波动剧烈（20日/60日超35%触发波动警告），信号可信度较低
- 汽车销量数据来自乘联会月度预测/快报，可能与最终数据有差异
- 每个指标均含 `scoring_guide` 字段，Agent 评分时优先参考
- 本报告为前置指标辅助分析，不构成投资建议
```

## 指标权重与传导方向

| 指标 | 方向 | 权重 | 传导机制 |
|------|------|------|----------|
| 纯碱价格 | 成本端 | 20% | 纯碱↓→玻璃成本↓→毛利率↑→利好 |
| NYMEX天然气 | 成本端 | 12% | 天然气↓→熔制成本↓→毛利率↑→利好 |
| USD/CNY汇率 | 收入端 | 18% | 人民币贬值→海外收入折算增加→营收↑→利好 |
| 中国汽车销量 | 收入端 | 18% | 销量↑→OE需求↑→营收↑→利好 |
| 集运指数(欧线) | 成本端(反向) | 12% | 运价↓→海运成本↓→出口利润↑→利好 |
| 新能源车渗透率 | 收入端 | 5% | 渗透率↑→单车玻璃价值量↑→利好 |
| 美国汽车销量 | 收入端 | 10% | 美国销量↑→海外OE需求↑→利好（FRED CSV） |
| 欧洲汽车销量 | 收入端 | 5% | 欧洲注册量↑→海外OE需求↑→利好（Agent搜索） |
