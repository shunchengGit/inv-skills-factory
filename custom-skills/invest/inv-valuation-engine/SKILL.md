---
name: inv-valuation-engine
description: 当需要评估股票估值水平、判断低估或高估时使用，结合价值投资框架给出买卖参考
version: 1.6.0
commands:
  - /valuation - 价值估值判断（先抓数据再结论）
  - /valuation_data - 仅抓取估值数据快照
  - /valuation_report - 直接输出五档估值报告
  - /valuation_compare - 多股票相对估值比较
---

# 价值投资估值判断

## 核心目标
基于公司类型、经营质量、增长预期和估值水平，输出五档结论：`低估`、`合理偏低`、`合理`、`合理偏高`、`高估`。

## 快速命令（新增）

路径中 `{baseDir}` = 本技能目录，`{stockDir}` = `{baseDir}/../inv-stock-data`，`{researchDir}` = `{baseDir}/../inv-research-analyzer`。

```bash
# ===== 代理设置说明 =====
# 美股/港股数据依赖 Yahoo Finance，国内网络需要代理
# 通过环境变量设置代理（inv-stock-data CLI 自动读取）
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# ===== 首选：一次获取全量数据 =====
# cs_stock_all 合并 snapshot + financial + financials，减少跨进程调用和限流风险
uv run {stockDir}/scripts/cs_stock_info.py all AAPL --output json
uv run {stockDir}/scripts/cs_stock_info.py all 600519 --output json

# ===== 具体命令 =====
# 1) 抓取估值快照（文本）
uv run {baseDir}/scripts/valuation_snapshot.py AAPL

# 2) 抓取估值快照（JSON，便于后续自动化）
uv run {baseDir}/scripts/valuation_snapshot.py 600519 --output json
uv run {baseDir}/scripts/valuation_snapshot.py 0700.HK --output json

# 3) 直接输出五档估值报告
uv run {baseDir}/scripts/valuation_report.py 600660

# 4) 指定公司类型，避免自动识别偏差
uv run {baseDir}/scripts/valuation_report.py 002475 --company-type tech

# 5) 同行相对估值比较
uv run {baseDir}/scripts/valuation_compare.py 002475 601138 002241 --company-type tech

# 6) 输出 Markdown 表格版，便于直接阅读
uv run {baseDir}/scripts/valuation_report.py AAPL --output markdown

# 7) 手动估值计算（当自动化脚本失败时降级）
uv run {baseDir}/scripts/valuation_manual_compute.py \
  --price 98.78 --shares 14.82 --fx 7.15 \
  --ni-gaap 978.43 --ni-nongaap 1073 --eps-fy1 82.08 \
  --equity 4133.85 --equity-prev 3133.13 \
  --revenue 4318.46 --gross-profit 2430.44 --op-income 931.02 \
  --fcf 1057.94 --cash 1089 --investments 3134 --debt 54 \
  --scenario-profit "悲观,1127,8|基准,1300,10|乐观,1500,12"
```

## 脚本优先级（新增）
1. **首选 `cs_stock_all`**：一次调用获取 snapshot + financial + financials，避免分开调用触发限流或超时。这是所有估值分析的默认第一步。
2. 用户给了代码但没给完整数据：先运行 `scripts/valuation_snapshot.py`。
3. 用户要直接结论：优先运行 `scripts/valuation_report.py`。
4. 用户要比较几家公司谁更便宜/更贵：优先运行 `scripts/valuation_compare.py`。
5. **脚本超时降级**：若 `uv run` 因依赖下载超时（常见于首次运行或网络慢），降级为 inv-stock-data `financials` 子命令获取财务三表数据，再按本技能框架手动计算。不得因脚本超时而放弃数据获取。
5. 脚本返回后，先检查 `data_gaps`，明确缺口和置信度影响。
6. 定量判断只按 `references/scoring-rules.md` 执行，定性解释再用 `references/master-frameworks.md`。
7. 如果用户已给高质量最新数据，可跳过抓取直评估，但需标注数据时点。
8. **若用户本地存在该标的券商研报 PDF**（默认目录或子目录见 `skills/inv-research-analyzer/SKILL.md`）：应把 **`inv-research-analyzer`** 作为**重要参考之一**——先 `list` / `extract` 梳理近半年卖方**共识、分歧、盈利预测区间、隐含假设与资本配置/分红**叙述，再运行本技能脚本；不得用卖方目标价直接代替本技能的五档结论。

## 重要参考：本地券商研报（`inv-research-analyzer`）

- **定位**：卖方 PDF 提供**叙事、一致预期区间、风险清单与隐含假设**，用于补充和校验你在「增长假设」「护城河叙事」「资本开支与股东回报」等定性环节的论据；**定量五档结论仍以本技能脚本 + `references/scoring-rules.md` 为准**。
- **何时必须引用**：用户已整理 `~/Desktop/股票研报`（或子文件夹如标的简称）且任务涉及**中长期价值判断**时，应在输出「关键依据」「核心假设」「风险与失效条件」中**单列一小节「卖方研报摘要（近半年窗口）」**，注明文件名日期窗口与券商来源。
- **衔接方式**：用 `inv-research-analyzer` 的 `scripts/research_pdf.py` 获取卖方观点：
  ```bash
  # 第一步：读 Index.md 确定子文件夹名（如 微软、腾讯控股）
  # 第二步：提取文本
  python3 {researchDir}/scripts/research_pdf.py extract --folder <子文件夹名>
  # 或按关键词提取
  python3 {researchDir}/scripts/research_pdf.py extract --contains <公司简称或代码>
  ```
  重点关注：一致评级、目标价区间、核心看多/看空论据、风险提示。与本技能 `valuation_snapshot` / `valuation_report` 的**数据时点**对照，冲突时**优先财报与行情事实**，卖方仅作假设参考。
- **边界**：卖方存在乐观偏差；研报**不构成**本技能的独立数据源替代 Yahoo/AkShare；价位判断不因「买入」评级而自动升级。

## 数据源说明（新增）
- 所有数据统一通过 `inv-stock-data` CLI 获取，不直接调用 yfinance/AkShare。
- A 股：inv-stock-data 聚合同花顺财务、新浪财务指标、百度估值等数据源。
- 美股/港股：inv-stock-data 通过 Yahoo Finance 获取快照和基本面数据。
- 输出中会写 `data_sources`，明确本次实际使用的数据来源。
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
  - 位置与分位：5年价格分位代理、20/60/250日回报、52周位置
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
6. 定量阈值以 `references/scoring-rules.md` 为唯一标准来源，主文件不重复定义冲突阈值。
7. 定性框架用于解释和修正结论置信度，不覆盖明显失真的定量结论。
8. 缺少数据时可使用内置手动计算脚本 `{baseDir}/scripts/valuation_manual_compute.py`，从 inv-stock-data `financials` + 研报数据补全核心指标。
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
2. **若存在本地券商 PDF**：按 `inv-research-analyzer` 抽取并归纳近半年卖方观点（可与下一步并行，但须在终稿中体现对照）。
3. 优先用 `cs_stock_all` 一次获取全量数据（snapshot + financial + financials），避免多次跨进程调用触发限流。然后标注数据时点。
4. 检查关键数据是否齐全；缺失、过旧或无法更新时先列出缺口。
5. 按公司类型选择框架，不强行套用全部方法。
6. 读取 `references/scoring-rules.md` 对照阈值完成定量判断。
7. 结合 `references/master-frameworks.md` 做定性校验，解释应享有溢价或折价的原因；**与卖方研报共识/分歧交叉验证**（若有）。
8. 输出五档结论、关键假设、风险条件、数据时点和操作参考。

## 多源数据整合分析框架（四层验证法）

当用户要求"结合大行研报、实时行情和网络数据给出分析和操作思路"时，按以下四层结构输出：

| 层级 | 回答的问题 | 数据来源 | 作用 |
|------|------------|---------|------|
| **数据层** | 事实是什么 | 实时行情（Yahoo Finance/inv-stock-data）+ 财务快照 | 锚定事实，确定估值锚点 |
| **研报层** | 卖方怎么看 | 本地券商PDF（inv-research-analyzer） | 校验假设，发现一致预期与关键分歧 |
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
按以下结构输出，避免自由发挥：

```markdown
## 核心结论
- 估值结论：低估 / 合理偏低 / 合理 / 合理偏高 / 高估
- 结论置信度：高 / 中 / 低

## 关键依据
- 1-3 条最重要的定量或定性依据
- （若有本地 PDF）卖方研报近半年共识/分歧要点，并注明与脚本数据时点是否一致

## 分框架判断
- 巴菲特/芒格：
- 段永平：
- 彼得·林奇：
- 邓普顿：

## 定量指标验证
- 数据时点：
- 当前估值指标：
- 历史分位：
- 增长假设：
- 安全边际：

## 核心假设
- 明确列出 2-4 条估值建立在什么前提上

## 风险与失效条件
- 哪些变量变化会让当前结论失效

## 操作参考
- 持有 / 逢低加仓 / 观望 / 分批减仓 / 回避
```

## 报告输出规范

当用户要求将分析结论整理为**公众号文章、研报或任何可发表格式**时，详见 `references/report-formatting-guide.md`，包含：先规划结构再动笔、突出时效性、去除个人化表述、估值与操作分离、精简冗余、数据来源透明 6 条规范。

## 参考文件
- `references/scoring-rules.md`：定量阈值、行业口径、五档结论映射
- `references/master-frameworks.md`：各大师框架的适用范围、判断逻辑和注意事项
- `references/internet-platform-valuation.md`：互联网平台公司（阿里/腾讯/美团等）估值注意事项——GAAP 净利润失真问题、Normalized 利润计算、SOTP 分部估值方法
- `references/us-hk-data-workaround.md`：美股/港股 `inv-stock-data snapshot` 返回大量 data_gaps 时的 inv-stock-data financials 补全流程、关键字段映射表、一致性校验清单
- `references/valuation-traps.md`：常见陷阱（数据层/估值层/脚本输出），含运行后必做检查清单
- `references/report-formatting-guide.md`：公众号/可发表格式报告输出规范
