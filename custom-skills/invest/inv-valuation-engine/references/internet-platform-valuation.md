# 互联网平台公司估值注意事项

## 适用标的
阿里巴巴、腾讯、拼多多、美团、京东等持有大量股权投资或存在投资公允价值变动的互联网平台公司。

## 核心问题：GAAP 净利润严重失真

这类公司持有大量上市公司/非上市公司股权投资，按 IFRS/GAAP 需将公允价值变动计入损益，导致：
- 单季 GAAP 净利润可能因股市波动剧烈摇摆（+100% 到 -70% 都有可能）
- Yahoo Finance 的 `earningsGrowth`（最近一季 GAAP 同比）因此严重失真
- 静态 PE（TTM）也会被扭曲

## 正确做法

### 1. 使用 Normalized / Non-GAAP 净利润
- 阿里巴巴：看"Non-GAAP 净利润"或财报中的"Normalized Income"（剔除投资公允价值变动、减值等）
- 腾讯：看"Non-IFRS 净利润"
- 美团：看"经调整净利润"
- 拼多多：yfinance `Normalized Income` 字段可用；GAAP 净利润受投资公允价值变动影响（2024年 GAAP 112.4bn vs Normalized 111.9bn 差异小，但 2022年 GAAP 188.2bn vs Normalized 97.7bn 差异 90.5bn，主因出售美团/京东等投资收益一次性计入）

### 2. 从年度财报手动计算增速
- 取 3-4 年 Normalized 净利润，计算复合增速
- 不要用 Yahoo 的 `earningsGrowth` 字段

### 3. 分部估值（SOTP）更合适
这类公司业务多元（电商+云+本地生活+数字媒体+投资组合），单一 PE 估值容易失真：
- 核心电商：PE 估值
- 阿里云：PS 或 EV/Revenue（利润率尚低）
- 本地生活：PS（仍在亏损）
- 投资组合：按市值折扣估值（通常 20-30% 折扣，反映流动性/控制权折价）

### 4. 关注经营利润率而非净利润率
- 经营利润率反映核心业务盈利能力，不受投资波动影响
- 阿里 FY2022-FY2025 经营利润率持续改善（11.1% → 14.8%），比净利润率更有参考价值

## Forward PE 异常案例库

当 `valuation_snapshot.py` 输出的 `forward_pe` 显著低于 `trailing_pe` 时，必须做增速常识校验。

### 案例：腾讯控股 0700.HK（2026-05-12）

| 指标 | 数值 | 来源 |
|------|------|------|
| 当前价格 | 457.20 HKD | `qt.gtimg.cn` |
| Trailing PE | 16.43-16.75x | `valuation_snapshot.py` / `qt.gtimg.cn` |
| Forward PE | 11.72x | `valuation_snapshot.py` |
| 隐含 EPS 增速 | ~40% | `(16.75 / 11.72 - 1) * 100` |
| Non-IFRS 净利润增速 | 15-17% | 招商证券 2026-03-23、东方证券 2026-03-26 |

**判断**：Forward PE 11.72x 隐含 EPS 增速 40%，与 Non-IFRS 实际增速 15-17% 严重不符。原因：
1. Yahoo 的 forward EPS 可能基于 GAAP 净利润（含投资公允价值变动）
2. 或基于某些卖方一致预期的上限偏乐观值
3. 港股互联网公司的 Forward PE 常见此类异常，不能直接采纳

**处理**：
- 以 Trailing PE 为主要锚点
- 手动用 Non-IFRS/Normalized 净利润计算 "调整后 Forward PE"：
  ```python
  price = 457.20
  eps_ttm_nongaap = price / 16.5  # 以 Trailing PE 反推 Normalized EPS
  growth_nongaap = 0.16           # 16%
  fwd_pe_adj = price / (eps_ttm_nongaap * (1 + growth_nongaap))
  # 结果：~14.2x，比 Yahoo 的 11.72x 更可信
  ```
- 在报告中明确标注："Forward PE 口径异常，本报告以 Trailing PE 为主锚点"

### 案例：拼多多 PDD（2026-05-17）

| 指标 | 数值 | 来源 |
|------|------|------|
| 当前价格 | $95.83 | Yahoo Finance |
| Trailing PE | 9.86x | `valuation_snapshot.py` |
| Forward PE | 6.78x | `valuation_snapshot.py` |
| 隐含 EPS 增速 | ~45% | `(9.86 / 6.78 - 1) * 100` |
| Normalized 净利润增速 | -11.1% (2025 YoY) | yfinance financials |

**判断**：Forward PE 6.78x 隐含增速 45%，与 2025 年 Normalized 净利润同比 -11.1% 严重不符。原因：2024 年利润基数含投资收益等非经常项偏高，2025 年回归常态。**以 Trailing PE 9.86x 为主锚点。**

## 数据获取路径

```
# 年度财报数据（从 Yahoo financials 获取）
cd {inv-stock-data skillDir}
HTTPS_PROXY=http://127.0.0.1:7890 .venv/bin/python3 -c "
import yfinance as yf
t = yf.Ticker('BABA')
# 年度利润表 - 取 Normalized Income 和 Operating Income
financials = t.financials
# 年度现金流量表 - 取 Operating Cash Flow 和 Free Cash Flow
cashflow = t.cashflow
# 年度资产负债表 - 取 Total Cash, Total Debt, Stockholders Equity
balance = t.balance_sheet
"
```

## 典型 Normalized 净利润 vs GAAP 净利润差异（阿里巴巴）

| 财年 | GAAP 净利润 | Normalized 净利润 | 差异原因 |
|------|-----------|-------------------|---------|
| FY2022 | 622 | 811 | 蚂蚁集团投资减值 |
| FY2023 | 728 | 750 | 较小差异 |
| FY2024 | 800 | 882 | 投资减值 |
| FY2025 | 1,301 | 1,349 | 投资公允价值变动 |

> Normalized 净利润增速 FY2022→FY2025 复合约 18.6%，远比 GAAP 的波动性更有参考价值。

## AI CapEx 暴增期估值调整

### 适用标的
Meta、Google、Microsoft、Amazon 等进入 AI 基础设施投资周期的平台公司。

### 核心问题：CapEx 暴增导致 FCF 失真

这类公司在 AI 投资周期中 CapEx 可从营收 15-20% 跳升至 30-40%，导致：
- FCF/净利润从 >80% 降至 <80%（如 META 2024 FCF/NI 86.7% → 2025 76.3%）
- FCF 绝对值可能下降（如 META 2024 $54.1B → 2025 $46.1B，尽管净利润增长）
- 简单看 FCF 下降会误判为利润质量恶化

### 正确做法

#### 1. 区分维持型 CapEx 与投资型 CapEx
- **维持型 CapEx**：保持现有业务运转所需，通常为营收 15-20%（数据中心替换、服务器更新等）
- **投资型 CapEx**：增量 AI 基础设施（GPU 集群、新数据中心），为未来变现做准备
- **可持续 FCF 估算**：经营现金流 - 维持型 CapEx（而非总 CapEx）

#### 2. 用经营利润增速而非 Normalized NI 增速
- 当对比基期含一次性投资收益/减值时，Normalized NI 同比增速可能为负但实际经营在改善
- 案例：META 2024→2025 Normalized NI -4.4%（$63.0B→$60.2B），但 Operating Income +20.0%（$69.4B→$83.3B）
- 原因：2024 年有一次性投资收益推高 Normalized NI 基数
- **结论**：对平台公司，Operating Income 增速是最可靠的核心增长指标

#### 3. 关注 CapEx 增速拐点
- CapEx 同比增速从 >50% 降至 <20% 时，通常是 FCF 释放的先行信号
- META 2025 CapEx +87%（$37.3B→$69.7B），若 2026 增速降至 20-30%，FCF 将大幅回升
- 估值应前瞻性定价 CapEx 见顶后的 FCF 释放，而非仅看当前 FCF

#### 4. Forward PE 在 AI 投资期的解读
- Forward PE 可能看似便宜（如 META 16.9x），但隐含了 AI 变现成功的预期
- 隐含增速校验：Forward EPS $36.16 vs Trailing $27.52 → 隐含增速 31.4%
- 若保守增速假设 15-20%，则 Forward PE 调整后为 19-22x
- **在 AI 投资期，应同时报告"当前 Forward PE"和"保守增速假设下的调整 Forward PE"**
