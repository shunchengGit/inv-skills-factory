---
name: inv-valuation-engine
description: 从价值投资视角评估个股估值，结合巴菲特/芒格、段永平、彼得·林奇、邓普顿等框架给出买卖参考。用于估值判断、多股票对比时
version: 2.0.0
trigger:
  - 估值分析
  - 价值投资
  - 市盈率
  - PE
  - PB
  - 估值对比
  - valuation
commands:
  - /valuation - 价值估值判断（先抓数据再结论）
  - /valuation_data - 仅抓取估值数据快照
  - /valuation_report - 直接输出五档估值报告
  - /valuation_compare - 多股票相对估值比较
---

# 价值投资估值判断

## 核心目标
基于公司类型、经营质量、增长预期和估值水平，输出五档结论：`低估`、`合理偏低`、`合理`、`合理偏高`、`高估`。

## 快速命令

路径中 `{baseDir}` = 本技能目录。详见 `references/commands-quickref.md`。

## 脚本优先级（新增）
1. **首选 `cs_stock_all` 获取三个核心组件**：v1 `all.data.components` 固定为 snapshot + financial + financials，各有独立状态；不含 daily/announcements/relations。估值脚本会另行显式请求 `daily(period=5y)`，A 股再请求公告与关联数据。
2. 用户给了代码但没给完整数据：先运行 `scripts/valuation_snapshot.py`。
3. 用户要直接结论：优先运行 `scripts/valuation_report.py`。
4. 用户要比较几家公司谁更便宜/更贵：优先运行 `scripts/valuation_compare.py`。
5. 若脚本超时或字段缺失，按 `inv-stock-data` 的数据层策略降级，先检查 `data_gaps`，必要时再用 `financials` + `valuation_manual_compute.py` 补全。
6. 定量判断按 `references/scoring-rules.md` 的人类说明执行；脚本阈值以 `scripts/scoring_rules.json` 为机器来源，两者必须同步。定性解释再用 `references/master-frameworks.md`。
7. 如果用户已给高质量最新数据，可跳过抓取直评估，但需标注数据时点。
8. **查阅知识库**（`inv-knowledge-curator`）：估值分析默认最低 L2，按 `inv-knowledge-curator/references/deep-mining-protocol.md` 执行。保留本技能特有约束：Reference 类条目优先作为数据锚点；条目摘要不足时，可用 `km_import read --file <res/...pdf> --pages edges` 回溯原始 PDF。定量结论仍按 `scoring-rules.md` 的说明判断。

## 数据源说明（新增）
- 所有数据统一通过 `inv-stock-data` CLI 获取，不直接调用 yfinance/AkShare。
- A 股：inv-stock-data 聚合同花顺财务、新浪财务指标、百度估值等数据源。
- 美股/港股：inv-stock-data 通过 Yahoo Finance 获取快照和基本面数据。
- 输出保留数据层 v1 的 `upstream_status`、`data_sources`、结构化 `data_gaps`、`data_as_of` 与历史 `window`。`all`、数据层和估值层的状态不可混为一谈。
- 估值状态为 `ok | partial | insufficient_for_valuation | upstream_failed`：只有 `ok` 可以生成操作参考；`partial` 可保留受限五档结论但操作为空；后两者结论和操作均为空。
- **Yahoo Finance Forward PE 陷阱**：港股互联网公司（如0700.HK）的 `forwardPE` 可能包含 Non-GAAP 调整或投资收益，导致 Forward EPS 隐含的净利润增速远超合理范围（实测出现过隐含56%增速）。使用 Forward PE 时必须做常识校验：`隐含增速 = (1/ForwardPE) / (1/TrailingPE) - 1`，若超过20%应标注口径差异，改用自建增速假设计算 Forward PE。
- **A+H 双上市 Forward PE 失真**：福耀玻璃等 A+H 双上市公司的 Yahoo Forward PE 可能基于 Non-GAAP/调整后 EPS（剔除汇兑损失等一次性项），而 Trailing PE 基于 GAAP（含汇兑损失），导致隐含增速虚高（实测福耀出现过隐含33%增速，实际一致预期增速仅4-5%）。校验方法：用一致预期 EPS 手算 Forward PE = 当前价/一致预期EPS，与 Yahoo Forward PE 对比；若差异大，以手算为准并标注口径差异。
- **港股/美股代理**：由 inv-stock-data 脚本内置自动检测和管理，详见 `inv-stock-data/SKILL.md`「代理规则」。

## 跨市场支持（新增）
- **A股**：`600519` / `000001` / `300750`
- **港股**：`0700.HK` / `1810.HK`
- **美股**：`AAPL` / `MSFT` / `NVDA`
- 三个市场统一尽量补齐以下字段：
  - 标的基本信息：名称、市场、币种、行业、公司类型提示
  - 估值指标：PE、PB、PS、EV/EBITDA、股息率、盈利收益率、Price/FCF
  - 增长与质量：营收增速、利润增速、ROE、毛利率、净利率、负债、FCF
  - 位置与分位：5年价格分位代理、20/60/250日回报、52周位置。52周至少 200 个观测且覆盖 350 天；250日收益至少 251 个观测；5年分位至少 1000 个观测且覆盖 4.5 年。不足时字段为 null 并记录 gap
  - 事件与预期：分析师目标价/上行空间、下一次财报日期、最近一次财报日期
- A股额外补充：近 1～2 个月公告关键词、近 30 日调研记录、事件层偏向与摘要

## 输出格式（新增）
- `text`：适合终端快速查看
- `json`：适合自动化处理
- `markdown`：适合直接阅读、复制和整理成报告

## 使用原则
1. 先收集关键数据，再做估值判断；缺少关键数据时，先说明缺口，不要臆测。
2. 先判断公司类型，再选择估值框架；不是所有框架都默认启用。
3. 尽可能使用最新数据：优先采用最近交易日价格、最新财报、最近十二个月（TTM）指标、最新一致预期和最新可得行业数据。
4. 若无法拿到最新数据，必须明确说明缺失项、数据日期、无法更新的原因，以及这会如何影响估值结论的置信度。
5. 若不同指标的数据时点不一致，必须明确标注各自日期，并优先采用最近一期且口径一致的数据。
6. `scripts/scoring_rules.json` 是脚本阈值的唯一机器可读来源，`references/scoring-rules.md` 是同步维护的人类说明；主文件不重复定义冲突阈值。
7. 定性框架用于解释和修正结论置信度，不覆盖明显失真的定量结论。
8. 缺少数据时可使用内置手动计算脚本 `{baseDir}/scripts/valuation_manual_compute.py`，从 inv-stock-data `financials` + 知识库已有数据补全核心指标。
9. 所有结论都要写明核心假设、风险条件和适用边界，不把估值结论表达成确定性预测。

## 必要输入
- 股票代码、名称、市场
- 行业分类与公司类型：消费、医疗、互联网、科技制造、周期、金融、地产、困境反转等
- 当前价格及主要估值指标：PE、PB、PS、股息率、EV/EBITDA、NAV（按标的类型选用）
- 历史估值分位：PE/PB 至少一项（拿不到时明确降级）
- 未来 3 年利润或自由现金流增长假设（优先一致预期）
- 经营质量指标：ROE、毛利率、净利率、自由现金流、负债水平

## 框架选择规则
### 1. 巴菲特/芒格框架
- 默认主框架，适用于大多数非金融公司
- 核心看点：护城河、管理层、自由现金流、长期回报率、安全边际

### 2. 段永平框架
- 优先用于消费、互联网、科技龙头
- 核心看点：商业模式是否“赚钱不辛苦”、企业文化是否本分、长期年化预期收益率是否达标

### 3. 彼得·林奇框架
- 用于成长股和中小盘股
- 仅在盈利稳定、增速可估时启用
- 周期股、低增速成熟公司、持续亏损公司默认不使用 PEG 作为核心依据

### 4. 约翰·邓普顿框架
- 仅用于周期股、困境反转股、市场极度悲观场景
- 普通稳态公司默认不启用该框架

### 5. 特殊行业处理
- 金融、地产弱化 DCF 和 PEG，优先看 PB-ROE、股息率、NAV
- 周期股优先看周期位置、资产重置价值和安全边际，不以单一年份利润估值

## 执行流程
1. 确认标的类型和适用估值口径。
2. **查阅知识库（L2 深度探索）**：按 `inv-knowledge-curator/references/deep-mining-protocol.md` 的 L2 标准执行。**必须先完成深度搜索，不可跳过或与下一步并行。** 本技能只保留两条特有约束：Reference 类条目优先读取（作为数据锚点），Analysis/Synthesis 次之（定性校验）；若知识库无记录，按协议输出结构化知识缺口。
3. 用 `cs_stock_all` 获取三个核心组件，再显式请求 `daily --period 5y`；A 股按需请求 announcements/relations。标注每个响应的状态、时点、来源与实际历史窗口。
4. 先执行估值就绪门禁：上游失败或可评级指标/核心锚不足时输出不可评级；partial 只允许受限结论、不输出操作参考。
5. 按公司类型选择框架，不强行套用全部方法。
6. 读取 `references/scoring-rules.md` 对照阈值完成定量判断。
7. 结合 `references/master-frameworks.md` 做定性校验，解释应享有溢价或折价的原因；**与知识库中已有分析交叉验证**：逐一对照评分结论与知识库条目中的判断，标注共识/分歧。特别注意：若知识库中多份研报的盈利预测/估值假设与自建假设差异 >5pp，必须分析根源并说明采用理由。
8. 输出五档结论、关键假设、风险条件、数据时点和操作参考。

## 多源数据整合分析框架（四层验证法）

当用户要求"结合大行研报、实时行情和网络数据给出分析和操作思路"时，按以下四层结构输出：

| 层级 | 回答的问题 | 数据来源 | 作用 |
|------|------------|---------|------|
| **数据层** | 事实是什么 | 实时行情（Yahoo Finance/inv-stock-data）+ 财务快照 | 锚定事实，确定估值锚点 |
| **知识层** | 已有资料怎么说 | inv-knowledge-curator（按 `deep-mining-protocol.md` 执行 L2；Reference 优先、必要时回溯原始 PDF） | 校验假设，发现共识与分歧；输出知识覆盖度矩阵 |
| **竞争层** | 护城河有多深 | Porter五力 / 行业数据 | 验证长期竞争优势是否结构性 |
| **操作层** | 具体怎么做 | 前三层结论 + 位置/波动判断 | 落到价格区间、仓位、打脸条件 |

**关键原则**：
- 每层只回答一个问题，不跳跃、不重复
- 下层不否定上层，而是在上层基础上进一步细化
- 数据烛突时，**以财报与行情事实为准**，卖方仅作假设参考
- 网络增量信息（行业智库、媒体报道）用于校验或补充卖方模型，尤其是**毛利率、定价变化、产能进度**等卖方可能偏保守的指标

## 不适用或需降级判断的场景
- 上市时间短、历史财报不足 3 年
- 持续亏损且商业模式未跑通
- 财务数据质量存疑，或一次性损益显著扭曲利润
- 高度依赖商品价格、政策补贴或单一事件驱动，导致常规估值失真

## 常见陷阱

详见 `references/valuation-traps.md`，按边界分三类：
- **数据层陷阱**：Yahoo earningsGrowth 失真、Forward PE 口径不一致、A+H 双上市失真、snapshot 返回空
- **估值层陷阱**：历史PE分位失真、5年vs3年分位选取、AI CapEx 期 FCF 失真、Normalized Income 增速失真
- **脚本输出陷阱**：uv run 首次超时、增速假设需人工校验、极简报告降级

运行脚本后**必做检查清单**见 `references/valuation-traps.md` 末尾（5 项）。

## 输出模板

详见 `references/output-template.md`。

## 报告输出规范

当用户要求将分析结论整理为**公众号文章、研报或任何可发表格式**时，详见 `references/report-formatting-guide.md`，包含：先规划结构再动笔、突出时效性、去除个人化表述、估值与操作分离、精简冗余、数据来源透明 6 条规范。

## 行业特化指南

### CDMO / CRDMO 行业

详见 `references/cdmo-industry-valuation.md`，核心要点：

- **管线驱动收入**：收入预测需基于项目数+转化率，关注综合项目数、Win-the-Molecule 胜率、商业化阶段项目占比
- **产能扩张周期**：FCF/净利润波动大（实测 -7%~53%），CapEx/净利润比率是关键质量指标
- **客户粘性极高**：商业化阶段切换成本极高 → LTV 长
- **地缘/监管风险**：常为 thesis breaker，关注北美收入占比、生物安全法案进展
- **毛利率=护城河代理**：高毛利→技术平台优势+定价权（药明46% vs 三星35% vs Lonza28%）
- **订单储备=前瞻指标**：Backlog 转化节奏决定收入增速
- **优先估值指标**：PE（盈利稳定后）、DCF（需假设 FCF 转化率随产能周期改善）；次要：PS（早期/亏损）、EV/EBITDA（重资产+杠杆）、PEG（增速明确时）；行业特有：订单/Backlog 倍数
- **CapEx 质量判断**：>80%NI 警惕扩张过激进；50-80% 扩张期正常；<50% 产能成熟期 FCF 释放加速
- **QARP 三闸门特别关注**：商业模式闸门重点看北美收入占比+地缘风险；财务质量闸门重点看 FCF 转化率趋势+CapEx/NI+ROE 能否随产能成熟回到 15%+；管理层闸门重点看回购 vs CapEx 平衡
- **典型 thesis breaker**：生物安全法案通过→北美收入腰斩；毛利率从 40%+跌至 30%以下；产能利用率持续低于 50%
- **可比公司数据限制**：三星生物(207940.KS) yfinance 返回空需 web_search；Catalent 已退市

## 参考文件
- `references/scoring-rules.md`：定量阈值、行业口径、五档结论映射
- `references/master-frameworks.md`：各大师框架的适用范围、判断逻辑和注意事项
- `references/internet-platform-valuation.md`：互联网平台公司（阿里/腾讯/美团等）估值注意事项——GAAP 净利润失真问题、Normalized 利润计算、SOTP 分部估值方法
- `references/us-hk-data-workaround.md`：美股/港股 `inv-stock-data snapshot` 返回大量 data_gaps 时的 inv-stock-data financials 补全流程、关键字段映射表、一致性校验清单
- `references/valuation-traps.md`：常见陷阱（数据层/估值层/脚本输出），含运行后必做检查清单
- `references/report-formatting-guide.md`：公众号/可发表格式报告输出规范
- `references/cdmo-industry-valuation.md`：CDMO/CRDMO 行业 QARP 估值指南——管线驱动收入、FCF 随产能周期波动、CapEx 质量判断、可比公司数据获取限制
