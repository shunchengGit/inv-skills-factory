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
- 不得用行情 Trailing PE 反推 Non-IFRS EPS：前者通常是 IFRS 口径，不能改名为调整后盈利。
- 优先从官方披露计算 `Non-IFRS TTM净利 = 上年全年 - 上年同期 + 本年同期`；Forward EPS 必须注明机构、预测年、币种与调整口径。
- 港币股价除以人民币EPS前必须换币：`PE = 股价HKD × HKD/CNY ÷ EPS人民币`。接口Forward PE需与此式复算，避免币种错配。
- 股权激励是股东经济成本；采用加回激励的Non-IFRS盈利时，另做扣回激励或持续稀释敏感性分析，不能再把全部回购率重复加到已含回购的EPS增速上。
- 报告明确采用的实际口径，不把混合口径的Trailing/Forward PE之比当作真实盈利增速。

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
# 年度/季度财报数据（yfinance 直接拉取，需代理）
# 注意：inv-stock-data 技能目录下没有 .venv，用 uv run --with yfinance；
# export 与命令必须放在同一次 shell 调用里（每次调用都是新解释器，跨调用不保留环境变量）
cd {inv-stock-data skillDir}
export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890
uv run --with yfinance python3 baba_fin.py
```

脚本注意（实测踩坑）：
- `t.financials` / `t.cashflow` / `t.balance_sheet` 的 DataFrame 以**字段名为行索引、日期为列**——取数用 `df.loc["Normalized Income"]`，误按 `df.columns` 匹配字段名会 AttributeError 或返回空。
- 也可用 `uv run {inv-stock-data skillDir}/scripts/cs_stock_info.py financials BABA --output json` 获取结构化三表（美股代码可用），作为 yfinance 的替代入口。

## 典型 Normalized 净利润 vs GAAP 净利润差异（阿里巴巴）

| 财年 | GAAP 净利润 | Normalized 净利润 | 差异原因 |
|------|-----------|-------------------|---------|
| FY2022 | 622 | 811 | 蚂蚁集团投资减值 |
| FY2023 | 728 | 750 | 较小差异 |
| FY2024 | 800 | 882 | 投资减值 |
| FY2025 | 1,301 | 1,349 | 投资公允价值变动 |
| FY2026 | 1,036 | 1,109 | 资产减值 95 亿 + 投资公允价值变动；S&M 激增至 2,450 亿与 AI 投资亏损同步压低两条口径 |

> FY2022→FY2025 Normalized 复合约 18.6% 曾是可参考的增速锚；进入 AI CapEx+新业务投入期后（FY2026 起），历史复合增速不再线性外推，改用「卖方下修后保守值 vs 共识值」区间做情景——两家机构对同一预测年利润的分歧可达 20%+，取保守侧为估值基准。

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

#### 5. 投入期平台公司利润表的三类光学失真（以阿里巴巴 FY2026 为实测样本）

进入 AI/新业务投入期的平台公司，除 GAAP/Normalized 口径差之外，还有三类失真要逐一拆解后再进估值：

- **CapEx 型 FCF 失真**：CapEx 单年可 3-4 倍跳升（阿里 FY2026：86→127 十亿 CNY），经营现金流近乎腰斩（163.5→76.2），FCF 转负（-50.7）。判断「投资 vs 恶化」看三个信号：经营现金流是否仍为正、对应业务收入是否在加速（云 +45% 且 AI 收入占比提升）、管理层是否给出减亏时间表。另看单季 CapEx/经营现金流比率：>1 即在透支存量现金，需配股/发债补充——注意股权融资的稀释代价（折价配售对老股东是真实损耗）。
- **会计重分类型收入失真**：合同化的商家/用户补贴按会计准则计为冲减收入（contra-revenue）而非销售费用，EBITA 不受影响但表观收入增速被大幅拖累（实测阿里 CY1Q26 CMR 表观 +1% vs 剔除补贴 +6-7%，拖累约 6pp）。**不要用表观收入增速判断业务趋势**——改用「核心业务 EBITA 剔除新业务」或「剔除补贴的可比增速」，并核验管理层是否披露口径拆分。
- **利润基数型 Normalized 失真**：投入期单季 Normalized NI 同比可骤降三分之二（阿里 Jun-26 季 133 亿 vs 上年同期 406 亿），主因 S&M 与研发前置。TTM Normalized 分母自动含此坑位；前瞻利润必须基于「投入产出拐点假设」做情景（云增速/减亏进度/补贴退坡），而非把单季骤降线性外推，也不能把 Forward PE 直接当便宜证据。
