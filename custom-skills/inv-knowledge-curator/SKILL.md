---
name: inv-knowledge-curator
description: AI投资知识库：3进3出1底座，OKF v0.2。脚本管确定性IO，检索/关联/综合交LLM。用于知识管理、资源分析时
version: 3.2.0
trigger: [知识管理, 收藏文章, 笔记整理, 研报分析, 券商研报, 研报提取, 财报分析, 资源入库, km_init, km_import, km_search, km_stats, km_lint, km_graph]
commands:
  - /km_init - 初始化知识库（LLM 流程：bash git clone + 建目录）
  - /km_import - 导入：丢链接(LLM用firecrawl抓取→总结→入库) / 丢资源文件(归档→提取→总结→入库) / 记笔记
  - /km_search - 搜（LLM 流程：读 index.md + grep entries + 跟随链接）
  - /km_stats - 统计（LLM 流程：读 index.md 口算）
  - /km_lint - 健康度检查与修复（脚本）
  - /km_graph - 知识图谱（脚本）
---

# inv-knowledge-curator v3.2

> **3 进 3 出 1 底座。** 扁平存储，frontmatter + 全文检索，不依赖目录层级。
> **脚本/LLM 分工**：脚本只做确定性 IO（git/PDF提取/索引重建/图谱生成/合规校验）；检索、统计、关联发现、综合分析全交 LLM（读 `entries/index.md` + `grep entries/*.md` + 跟随 markdown 链接）。

## 仓库结构

```
~/.inv-knowledge/
├── entries/                       ← 知识条目（扁平）
│   ├── index.md                   ← 按 type 分组
│   ├── by-tag/                    ← 按标签索引（{tag}.md）
│   └── {slug}.md                  ← OKF v0.2
├── res/                           ← 资源文件（研报/财报/其他，按标的）
│   ├── index.md                   ← 资源索引
│   └── {ticker}/
├── knowledge-graph.html           ← 知识图谱
└── log.md                         ← 变更日志
```

---

# 一、OKF v0.2 知识条目格式

LLM 生成条目时按此模版填充，**描述用中文，摘要≥3句，关键要点≥3条，关联≥2个**：

```markdown
---
type: Analysis
title: 福耀玻璃2026年Q1毛利率回升至38%的核心原因
description: 福耀玻璃2026Q1毛利率38%（+3pp YoY），受益纯碱降价+产品结构升级（天幕/HUD玻璃占比25%），ASP同比+11%超长期指引。
timestamp: 2026-06-22T00:00:00+08:00
resource: res/福耀玻璃/2026-04-21-UBS-Fuyao-Glass-Q126.pdf
source_type: pdf
tags: [fuyao-glass, profit-trend, competitive-advantage, 2026-Q1]
---

# 福耀玻璃2026年Q1毛利率回升至38%的核心原因

## 摘要
福耀玻璃2026年Q1实现营收104.13亿元（+5.1% YoY），毛利率38%（+3pp YoY），超出市场预期。核心驱动力：1）纯碱价格同比下降约15%；2）高附加值产品（天幕玻璃、HUD前挡玻璃、镀膜玻璃）占比提升至25%，带动ASP同比+11%。剔除汇兑损益后净利润+10% YoY，显示主营业务韧性。5家外资券商（UBS/BNP/BofA/JPM/MS）一致看好，目标价CNY80/HKD80。

## 关键要点
- 毛利率38%：纯碱降价贡献约1.5pp，产品结构升级贡献约1.5pp
- ASP同比+11%（vs长期指引6-7% CAGR），受益国内高端车型销量增长
- 汇兑损益逆转是Q1利润下滑的核心干扰项（2025Q1收益2.4亿→2026Q1亏损4.4亿）
- 美国工厂产能利用率85%，关税影响可控（美国市占率30%+，替代供应商有限）
- 一致预期2026年归母净利润约93亿，当前PE约15x，处于近5年估值低位

## 关联
- [福耀玻璃竞争壁垒与护城河分析](entries/福耀玻璃竞争壁垒分析.md) — 补充四大竞争壁垒（国运红利/柔性生产/垂直一体化/降本文化）
- [曹德旺2025年度股东大会关税表态](entries/曹德旺股东大会表态-美国关税.md) — 管理层对关税风险的最新判断

## 引用
- [UBS - Fuyao Glass Q126 Earnings](res/福耀玻璃/2026-04-21-UBS-Fuyao-Glass-Q126.pdf)
```

### type 取值

| type | 适用场景 |
|------|---------|
| `Article` | 外部文章/新闻/数据快照 |
| `Analysis` | 自己的分析、研判、深度研究 |
| `Reference` | 基准数据锚点、年报核心数据 |
| `Synthesis` | 多源综合报告 |
| `Note` | 随手记、片段、想法 |

### tags 三层标签体系

| 层级 | 含义 | 示例 |
|------|------|------|
| **标的** | 公司/行业 | `fuyao-glass` `tsmc` `tencent` |
| **分析维度** | 角度 | `valuation` `risk-factor` `competitive-advantage` |
| **时效** | 时间锚点 | `2026-Q1` `2024` `2026-06` |

维度标签词库：估值(`valuation` `profit-trend`)、风险(`risk-factor` `fx-risk` `geopolitical-risk`)、竞争(`competitive-advantage` `moat` `porter-five-forces`)、商业模式(`business-model` `technology-moat`)、数据(`baseline-data` `official-source`)、市场(`sentiment` `capital-flow` `margin-trading`)

### 内容质量标准

**description（搜索召回的命脉）**：一句话说清"这篇文章/研报的核心发现是什么"。

| ❌ 差 | ✅ 好 |
|------|------|
| `福耀玻璃相关知识的整理与摘要` | `福耀2026Q1毛利率38%(+3pp YoY)，纯碱降价+产品升级驱动，ASP+11%超指引` |
| `腾讯控股研报综合摘要` | `腾讯Q1营收1965亿(+9%),调整后净利+11%,15家券商一致看多,目标价690-716港元` |

**摘要 ≠ 关键要点**：

| 章节 | 定位 | 写法 |
|------|------|------|
| 摘要 | 概述"发生了什么" | 3-5 句连贯段落，给出全貌：背景→核心发现→结论 |
| 关键要点 | 提取"具体论据" | 3-7 条独立要点，每条含数据/事实，可直接引用 |

**type 选型**：LLM 根据内容性质判断，默认不选 Article：

| 场景 | 选 type |
|------|---------|
| 提取外部文章/新闻的客观内容 | `Article` |
| **有自己的分析、推理、判断**（最常见） | `Analysis` |
| 年报/财报/官方数据的基准锚点 | `Reference` |
| 融合多份研报/多源信息的综合报告 | `Synthesis` |
| 随口记录的想法、灵感 | `Note` |

---

# 二、3 进（导入）

生成 entry 前自查：

- [ ] description 含具体数据和结论，不可空泛
- [ ] 摘要 ≥3 句（连贯段落），关键要点 ≥3 条（独立数据点）
- [ ] tags 含 1 标的 + 2 分析维度 + 时效
- [ ] 关联 ≥2 条，写明为什么相关（不是只写"相关"）
- [ ] title 清晰含标的/主题关键词
- [ ] resource 指向真实来源

所有入口共享的**导入规则**：
- **description** 含具体数据和结论，不可留空或填"XX相关知识的整理"——description 是搜索召回的核心字段
- 写摘要（3-5句）+ 关键要点（3-7条），不可留空
- tags 至少包含 1 标的 + 2 分析维度
- **关联由 LLM 建立并写入**：导入时 LLM 自行搜索已有条目（读 `entries/index.md` + `grep entries/*.md`），找 ≥2 个建交叉关联，写明相关原因。`km_lint --fix` 不再自动补关联（确定性词袋规则已移除），仅做密度检查
- **关联链接必须用实际文件名**（死链根因）：写 `## 关联` 段的 `[](path)` 时，**path 必须是条目的实际 `.md` 文件名（slugified）**，不是标题原文。标题含 `：` `/` 等符号时，slugify 会转成 `-`（如标题"ASML首选股：三大驱动因素" → 文件名 `ASML首选股-三大驱动因素.md`）。写链接前先 `ls entries/` 或读 `entries/index.md` 核对真实文件名，禁止凭标题臆造路径
- `km_import.py store` 存入 `entries/{slug}.md`（自动更新 index/log + git push）
- 去重：标题相同 或 标题相似>80%且resource相同 → 拒绝入库
- stale 条目（>183天）定期 review 是否需要更新或归档

## /km_import <url> — 丢链接

LLM 用 `firecrawl_scrape` MCP 工具抓取 URL → 读内容写摘要+要点+标签 → 搜索已有条目建关联 → `km_import.py store`

## /km_import res — 丢资源文件

```
1. LLM 看文件名判断归属（腾讯控股、福耀玻璃、行业研究-互联网...）
2. km_import.py res --file {路径} --target {归属}  归档到 res/ + 提取原文（pymupdf）
3. LLM 读原文，用中文写摘要+要点+tags
4. km_import.py store 存入 entries/
```

> `res/` 不限于研报，可存放财报、公告等任何资源文件。pymupdf venv 首次自动安装。

## /km_import note — 记笔记（折叠进 /km_import）

LLM 对话流程：用户口述 → 格式化+打标签 → 搜索已有条目建关联 → `km_import.py store --resource manual --source_type note`

---

# 三、3 出（检索与分析）

## /km_search <query> — 搜（LLM 流程，无脚本）

LLM 直接操作，不依赖脚本评分：
1. 读 `entries/index.md`（按 type 分组的全量条目清单，含 title/description）→ 一句话定位候选
2. `grep -rl "<关键词>" entries/*.md` 按命中文件精筛；按 frontmatter 的 `type`/`source_type`/`tags`/`timestamp` 过滤
3. `grep` 也覆盖 `res/`（`res/index.md` 列出所有资源文件）

**LLM 搜索策略**（让 LLM 总能找到相关内容）：

1. **多角度搜索**：同一个标的用不同关键词搜 — 中文名"腾讯"、代码"0700"、英文"tencent"、行业"互联网"
2. **过滤链**：全搜 → 读命中条目 frontmatter → 按 type/source_type/tags/timestamp 精准过滤
3. **跟随交叉引用**：命中条目后，读其正文 `## 关联` 段的 markdown 链接，跳到关联条目（"串"的快捷方式）
4. **标签导航**：无结果时读 `entries/by-tag/{tag}.md` 浏览该标签下所有条目
5. **放宽搜索**：零结果时缩短关键词（"福耀玻璃利润趋势"→"福耀"）
6. **双向追踪**：想知道"谁引用了我关注的条目"，用 `grep -rl "条目slug.md" entries/*.md` 反查

| 出口 | 方式 | 说明 |
|------|------|------|
| **搜** | LLM 读 index + grep | 多角度 + 过滤 + 跟随链接 + 标签导航 |
| **串** | LLM inline | 读条目→提取实体→grep 搜索扩展→读关联链→输出关联图（无独立命令） |
| **合** | LLM inline | 搜索→读匹配条目→聚合共识/分歧/时间线/缺口→可选 `store` 为新 Synthesis（无独立命令） |

---

# 四、深度挖掘协议（下游技能必读）

> 以下三个深度等级供下游技能（估值引擎/QARP策略/主题研究）选择使用。不是每次查询都需要 L3——根据任务性质选择，**但估值和决策类分析默认最低 L2**。

## 4.1 L1 快速检索（30 秒）

**适用场景**：快速过滤、数据补充、非核心环节的旁路查询。

```
读 entries/index.md（全量条目清单，含 title + description）
→ 按关键词定位 top 3-5 条候选
→ 不跟随引用，不深度展开
```

## 4.2 L2 深度探索（估值/决策默认，3-5 分钟）

**适用场景**：估值分析、QARP 选股闸门、持仓检查。**这是估值和决策类分析的默认最低深度。**

```
1. 多角度搜索（≥3 个角度）—— LLM 读 index.md + grep entries/*.md
   grep -rl "<标的>" entries/*.md          # 标的直达
   grep -rl "<标的> 估值" entries/*.md     # 估值维度
   grep -rl "<标的> 风险" entries/*.md     # 风险维度
   grep -rl "<行业> 趋势" entries/*.md     # 行业维度

2. 过滤链
   → 读命中条目 frontmatter，按 type/source_type/tags/timestamp 精准过滤

3. 跟随关联链（≥1 层）
   → 命中条目后，读其正文 ## 关联 段的 markdown 链接，跳到关联条目
   → 对每条高关联条目，再读其关联链（第 2 层）
   → 同一标的的 Reference 类条目优先读取（数据锚点）
   → 注意时效：aging（91-183天）标注，stale（>183天）跳过

4. 标签导航收尾
   → 读 entries/by-tag/{tag}.md 浏览该标签下所有条目，补充遗漏维度

5. 按类型分层读取
   → Reference 优先（年报/财报数据锚点）
   → Analysis/Synthesis 次之（已有分析结论）
   → Article 最后（外部信息，需交叉验证）
```

## 4.3 L3 全库挖掘（主题研究默认，5-10 分钟）

**适用场景**：主题研究（`/research`）、行业全景扫描、首次覆盖深度分析。

```
L2 全部步骤 +
  6. 系统遍历关联（LLM inline）
     → 对 L2 发现的 3-5 个核心条目，逐一做相关性分析
     → 实体提取 → grep 搜索扩展 → 读关联链发现间接关联

  7. 聚合分析（LLM inline）
     → 收集所有匹配条目 → 识别共识/分歧/时间线/信息缺口
     → 可选：km_import.py store 为新的 Synthesis 条目

  8. 双向回链查询
     → grep -rl "<关注条目slug>.md" entries/*.md 查找"谁引用了我关注的条目"
     → 发现 L2 搜索遗漏的间接关联

  9. 知识缺口评估（结构化输出）
     → 逐项评估覆盖度（见下方检查清单）
```

## 4.4 深度搜索检查清单

每次 L2/L3 结束时，LLM 自查：

| # | 检查项 | 通过标准 |
|---|--------|---------|
| 1 | 多关键词覆盖 | ≥3 个不同角度搜索过 |
| 2 | 关联链跟随 | ≥1 层 `## 关联` 链接已追踪 |
| 3 | 标签导航收尾 | `entries/by-tag/{tag}.md` 已浏览 |
| 4 | Reference 锚点 | 若库中有该标的 Reference 条目，必须已读取 |
| 5 | 时效标注 | aging/stale 条目已标注时效风险 |
| 6 | 知识缺口输出 | 说明知识库缺少什么维度的信息 |

## 4.5 知识缺口输出格式

当知识库覆盖不足时，下游技能应结构化输出缺口（而非简单标注"知识库无记录"）：

```
## 知识库覆盖度
| 维度 | 状态 | 已有条目数 | 最晚时点 | 缺口说明 |
|------|:--:|:--:|---------|---------|
| 财务数据 | ✅ | 3 | 2026-Q1 | — |
| 竞争格局 | ⚠ | 1 | 2025-Q3 | 缺少 Porter 五力分析条目 |
| 管理层评价 | ❌ | 0 | — | 无管理层相关条目 |
| 卖方研报 | ✅ | 5 | 2026-05 | — |
| 风险分析 | ⚠ | 1 | 2025-12 | 缺少地缘风险维度 |

→ 降级决策：{L3 全库挖掘已完成，缺口无可避免 / Web 降级补充 {维度}}
```

---
# 五、1 底座 + 健康度

**知识图谱**：`km_visualize.py`（或 `/km_graph`）生成。每次 `km_lint --fix` 后自动重建。孤立节点比例过高时图谱头部黄标提醒。不要在每条 store 后生成——太频繁。

**健康度检查**：`km_lint.py [--fix] [--skip-url-check] [--check-duplicates]`。`--fix` 修复完成后自动 git push。返回结果含 `summary` 汇总（`empty_summary:3` / `no_cross_refs:12` 等），LLM 优先修数量最多的项。

| 检查项 | --fix |
|--------|:---:|
| OKF 合规（resource, source_type 等） | ❌ |
| 死链 / 孤立文件 / 图谱过期 | ✅ |
| 缺失 resource / 重建 index.md / 重建 by-tag/ | ✅ |
| 交叉引用密度（只读检查，关联由 LLM 导入时建立） | ❌ |
| 资源配对 / URL 可达 / 重复检测 / 标签治理 / 时效预警 / 内容质量 | ❌ |

---

# 六、时效规则

| 时效 | 距今 | 规则 |
|------|------|------|
| **fresh** | ≤90天 | 默认引用 |
| **aging** | 91-183天 | 须标注 |
| **stale** | >183天 | 默认不引用 |

---

# 七、批量导入（Subagent 工作流）

当有多份 PDF（如批量研报）需要一次性入库时，使用 `delegate_task` 派发 subagent 并行处理。

## 7.1 Subagent 派发模板

```
delegate_task(
  context="知识库路径 ~/.inv-knowledge/。脚本路径 ~/.hermes/skills/.../scripts/。
   待处理文件列表（精确到文件名）：
   - res/腾讯控股/2026-05-13-xxx.pdf
   - res/腾讯控股/2026-05-14-yyy.pdf
   ...
  ",
  goal="读取上述 PDF，创建并写入 OKF 条目到 ~/.inv-knowledge/entries/。每个公司至少1条。",
  toolsets=["terminal","file"]
)
```

## 7.2 写库方式选择

| 方式 | 适用场景 | 注意 |
|------|---------|------|
| `km_import.py store`（无 --content-file） | 单条或少量导入 | ✅ 自动更新 index/log/git push。传 `--content` 或 stdin，不要传 `--content-file`——**`--content-file` 会导致双重 frontmatter**（脚本生成自己的 frontmatter 追加到文件已有 frontmatter 后）。CLI 传 description 含 `$` 符号时用单引号 |
| `write_file` 直写 entries/（含完整OKF frontmatter） | 批量导入（subagent）或避免shell转义问题 | 写入后必须运行 `km_lint --fix --skip-url-check` 重建索引/标签/图谱。**这是推荐的批量写入方式**——避免双重frontmatter和shell `$` 转义两个问题 |

**安全拦截降级**：当 subagent 内 `km_import.py store` 被 Hermes 安全策略阻止时，改为 `write_file()` 直接写 `~/.inv-knowledge/entries/{slug}.md`。全部写入完成后在主会话运行 `km_lint.py --fix --skip-url-check` 统一重建索引、标签、图谱和 git push。

**推荐批量导入工作流**：
1. 归档：`km_import.py res --file {path} --target {target}` 或直接 `cp`
2. 写条目：subagent 内用 `write_file()` 直接写 `~/.inv-knowledge/entries/{slug}.md`（含完整 OKF frontmatter: type/title/description/timestamp/resource/source_type/tags）
3. 重建：主会话运行 `km_lint.py --fix --skip-url-check`（重建索引/标签/图谱/git push）

## 7.3 Subagent 格式硬规则（必遵守）

派发 subagent 时必须在 context 中写明以下规则，否则会产出垃圾条目：

```
CRITICAL RULES:
1. 每条条目 25-50 行 MAX。禁止倾倒 PDF 原文
2. 格式：YAML frontmatter + ## 摘要（段落） + ## 关键要点（bullet list）
3. frontmatter 中 type 只能是：Analysis/Article/Reference/Synthesis/Note（5选1）
4. description 字段：一句含具体数据的结论，禁止空泛
5. tags 不含特殊字符（/ \ : * ? " < > |），否则标签索引文件创建失败
6. 禁止包含 PDF disclaimer/boilerplate 文本
7. 如果多份同标的研报，可合并为一条多投行综合条目（更高效）
```

**为什么 size matters**：25-50 行的干净条目（如福耀玻璃UBS快评）与 1500+ 行的原始PDF倾倒（如上一轮subagent产物）的质量差异天壤之别。LLM必须理解：入库的是"知识条目"（提炼后的摘要），不是"PDF备份"。

## 7.4 垃圾条目清理

批量导入后，立即检查并删除以下垃圾：

```
# 1. PDF 免责声明标题（文件名来自 PDF 页脚文本）
grep -l "^--- page [0-9]" ~/.inv-knowledge/entries/*.md  # 原始PDF文本倾倒
# 2. 超大条目（>200行 = PDF原文倾倒）
wc -l ~/.inv-knowledge/entries/*.md | sort -rn | head
# 3. 无 frontmatter 字段的幽灵条目
grep -L "^type:" ~/.inv-knowledge/entries/*.md | grep -v index.md
```

识别后直接 `rm` 删除，重新派发 subagent 处理。

---

# 八、脚本

> 原则：只保留确定性 IO 脚本。检索/统计/初始化/关联发现/综合分析交 LLM。

| 脚本 | 用途 |
|------|------|
| `knowledge.py` | 共享 OKF 引擎：frontmatter 解析、索引/标签重建、合规校验（被其他脚本 import，不直接调用） |
| `km_import.py store/res` | 条目存储（git push + index/log 更新）+ 资源导入（pymupdf PDF 提取 + MD5 归档） |
| `km_lint.py` | 健康度检查与修复（确定性检查 + index/by-tag/图谱重建 + git push） |
| `km_visualize.py` | 知识图谱（Cytoscape HTML，确定性数据构建） |

**已交 LLM 的能力**（无脚本）：
- 初始化 `/km_init` → LLM bash `git clone` + `mkdir`
- 搜索 `/km_search` → LLM 读 `entries/index.md` + `grep entries/*.md`
- 统计 `/km_stats` → LLM 读 index 口算
- 关联发现 → LLM 导入时手动建（不再用确定性词袋规则自动补）
- 综合 `/合` → LLM inline 聚合

---

# 九、异常处理

| 场景 | 表现 | 处理 |
|------|------|------|
| 知识库不存在 | `请先运行 km_init.py` | LLM 用 bash：`git clone <INV_KNOWLEDGE_REPO_URL> ~/.inv-knowledge` + `mkdir -p entries res` |
| km_import res: 文件不存在 | `# 文件不存在` | 确认路径 |
| km_import res: 缺少 --target | `请指定 --target` | 先读 `res/` 确认已有文件夹 |
| km_import res: PDF 损坏/扫描件 | `跳过无法打开` / 文本为空 | 跳过或告知用户 |
| km_import res: 目标已存在 | MD5 相同→跳过，不同→加后缀 | 自动处理 |
| 抓取 URL 失败 | firecrawl_scrape MCP 返回空/反爬 | LLM 换 `waitFor`/`proxy`，或手动粘贴正文 store |
| LLM 搜索无结果 | grep/index 无命中 | 缩短关键词（"福耀玻璃利润趋势"→"福耀"）；读 `entries/by-tag/{tag}.md` 浏览 |
| km_import store: 重复入库 | `疑似重复入库` | 告知用户，如需更新先删旧条目 |
| km_import store: 内容太短 | `content 过短` | 检查输入是否截断 |
| km_import store: --description 自动提取错误 | 从frontmatter误取`title: xxx` | 始终显式传 `--description`，不依赖`_auto_description` |
| km_import store: 双重 frontmatter / Shell `$` 转义 / 被安全拦截 | 见 7.2 写库方式选择（已详述机制与降级） | 按 7.2：避免 `--content-file`、description 含 `$` 用单引号、subagent 被 Hermes 拦截则 `write_file` 直写 + 主会话 `km_lint --fix` |
| subagent 倾倒PDF原文 | 条目>200行，含`--- page N ---`标记 | 删除后重新派发，context中写明"25-50行MAX，禁止PDF原文" |
| 标签含斜杠(`I/O`) | `by-tag/I/O-2026.md`创建失败 | tags禁止使用`/ \ : * ? " < > |`，用`IO-2026`替代 |
| 条目type不合法 | `type: Research Report` | OKF合法type仅5种：`Analysis/Article/Reference/Synthesis/Note` |
| 同标的研报大量重复 | 每家券商一条独立条目导致膨胀 | 合并为「标的+主题」综合条目（如"腾讯控股1Q26多投行分析"），覆盖2-5家券商观点 |
| git push 超时/失败 | 超时或失败提示 | 文件已写入本地，不阻塞流程，稍后手动 push |

**git push 触发时机**：`km_import store` 自动 push、`km_import res` 自动 push、`km_lint --fix` 自动 push。
| 路径含空格 | macOS 下载常见 | shell 用引号包裹或用 `\\` 转义 |

## km_lint --fix 自动化修复内容

`km_lint.py --fix --skip-url-check` 自动处理：
- 清除死链、修复孤立文件、补全缺失 resource
- 重建 `entries/index.md` 和 `entries/by-tag/` 标签索引
- 重建知识图谱
- 修复后再次 lint 验证

> 交叉关联**不再自动写入**（确定性词袋规则已移除，质量差）。关联由 LLM 导入时手动建立，`km_lint` 仅做密度检查（`no_cross_refs` 计数）。导入 5-10 条后跑一次 `--fix` 重建索引/标签/图谱即可。

## 依赖

- `_shared/git.py` `_shared/dotenv.py` `_shared/proxy.py`
- `pymupdf`（通过 `/tmp/research-pdf-venv`）
- 远程仓库：`git@github.com:shunchengGit/inv-knowledge.git`
