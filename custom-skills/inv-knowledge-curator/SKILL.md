---
name: inv-knowledge-curator
description: AI投资知识库：3进(链接/资源/笔记) 3出(搜/串/合) 1底座(图谱)。OKF v0.2标记来源。用于知识管理、资源分析时
version: 3.0.0
trigger: [知识管理, 收藏文章, 笔记整理, 研报分析, 券商研报, 研报提取, 财报分析, 资源入库, km_init, km_import, km_note, km_search, km_related, km_synthesize, km_stats, km_lint, km_graph]
commands:
  - /km_init - 初始化知识库
  - /km_import - 导入：丢链接(抓取→总结→入库) / 丢资源文件(归档→提取→总结→入库)
  - /km_note - 记笔记→格式化→入库
  - /km_search - 搜：关键词/标签/类型过滤
  - /km_related - 串：关联条目
  - /km_synthesize - 合：聚合分析
  - /km_stats - 统计
  - /km_lint - 健康度检查与修复
  - /km_graph - 知识图谱
---

# inv-knowledge-curator v3

> **3 进 3 出 1 底座。** 扁平存储，frontmatter + 全文检索，不依赖目录层级。

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
- `km_search` 找 ≥2 个已有条目，建交叉关联（每条 ≥2 个，写明相关原因）
- **交叉引用密度**：导入后每 5-10 条新条目，运行一次 `km_lint --fix --skip-url-check` 自动补全双向链接
- `km_import.py store` 存入 `entries/{slug}.md`（自动更新 index/log/图谱+git push）
- 去重：标题相同 或 标题相似>80%且resource相同 → 拒绝入库
- stale 条目（>183天）定期 review 是否需要更新或归档

## /km_import <url> — 丢链接

`km_import.py fetch <url>` 抓取 → LLM 读内容写摘要+要点+标签 → 建关联 → store

## /km_import res — 丢资源文件

```
1. LLM 看文件名判断归属（腾讯控股、福耀玻璃、行业研究-互联网...）
2. km_import.py res --file {路径} --target {归属}  归档到 res/ + 提取原文
3. LLM 读原文，用中文写摘要+要点+tags
4. km_import.py store 存入 entries/
```

> `res/` 不限于研报，可存放财报、公告等任何资源文件。pymupdf venv 首次自动安装。

## /km_note — 记笔记

LLM 对话流程：用户口述 → 格式化+打标签 → 找关联 → `km_import.py store --resource manual --source_type note`

---

# 三、3 出（检索与分析）

## /km_search <query> — 搜

`km_search.py <query>` 多词加权评分搜索，同时搜索 `entries/` 和 `res/`。结果含 `res_files`（匹配的资源文件）、`score`（综合评分）、`match_detail`（命中位置）、`cross_refs`（交叉引用）、`suggested_tags`（建议标签）。

**LLM 搜索策略**（让 LLM 总能找到相关内容）：

1. **多角度搜索**：同一个标的用不同关键词搜 — 中文名"腾讯"、代码"0700"、英文"tencent"、行业"互联网"
2. **过滤链**：全搜→看 `summary`→`--type`/`--source_type`/`--after`/`--before` 精准过滤
3. **跟随交叉引用**：命中条目后，读其 `cross_refs` 发现关联条目（"串"的快捷方式）
4. **标签导航**：无结果时看 `suggested_tags`，用 `--tag` 过滤；也可直接读 `entries/by-tag/{tag}.md` 浏览该标签下所有条目
5. **放宽搜索**：零结果时缩短关键词（"福耀玻璃利润趋势"→"福耀"）
6. **双向追踪**：每个搜索结果含 `cross_refs`（引用了谁），通过 `km_lint --fix` 可自动回链（谁引用了我）

| 出口 | 调用 | 说明 |
|------|------|------|
| **搜** | `km_search.py <query>` | 多词加权评分，返回 summary/score/match_detail/cross_refs/suggested_tags |
| **串** | LLM 流程 | 读条目→提取实体→搜索+`km_lint cross_references`→关联图 |
| **合** | LLM 流程 | 搜索→读匹配条目→聚合共识/分歧/时间线/缺口→可选 store 为新 Synthesis |

---

# 四、1 底座 + 健康度

**知识图谱**：`km_visualize.py`（或 `/km_graph`）生成。每次 `km_lint --fix` 后自动重建。孤立节点比例过高时图谱头部黄标提醒。不要在每条 store 后生成——太频繁。

**健康度检查**：`km_lint.py [--fix] [--skip-url-check] [--check-duplicates]`。`--fix` 修复完成后自动 git push。返回结果含 `summary` 汇总（`empty_summary:3` / `no_cross_refs:12` 等），LLM 优先修数量最多的项。

| 检查项 | --fix |
|--------|:---:|
| OKF 合规（resource, source_type 等） | ❌ |
| 死链 / 孤立文件 / 图谱过期 | ✅ |
| 缺失 resource / 重建 index.md / 重建 by-tag/ / 双向交叉关联 | ✅ |
| 资源配对 / URL 可达 / 重复检测 / 标签治理 / 时效预警 / 内容质量 | ❌ |

---

# 五、时效规则

| 时效 | 距今 | 规则 |
|------|------|------|
| **fresh** | ≤90天 | 默认引用 |
| **aging** | 91-183天 | 须标注 |
| **stale** | >183天 | 默认不引用 |

---

# 六、脚本

| 脚本 | 用途 |
|------|------|
| `km_init.py` | 拉取仓库，创建 entries/res 目录 |
| `km_import.py fetch/store/res` | URL 抓取 + 条目存储 + 资源导入 |
| `km_search.py` | 全文搜索 |
| `km_stats.py` | 统计 |
| `km_lint.py` | 健康度检查与修复 |
| `km_visualize.py` | 知识图谱 |
| `km_migrate_to_okf.py` | v0.1→v0.2 迁移 |

---

# 七、异常处理

| 场景 | 表现 | 处理 |
|------|------|------|
| 知识库不存在 | `请先运行 km_init.py` | 运行 `km_init` |
| km_import res: 文件不存在 | `# 文件不存在` | 确认路径 |
| km_import res: 缺少 --target | `请指定 --target` | 先读 `res/` 确认已有文件夹 |
| km_import res: PDF 损坏/扫描件 | `跳过无法打开` / 文本为空 | 跳过或告知用户 |
| km_import res: 目标已存在 | MD5 相同→跳过，不同→加后缀 | 自动处理 |
| km_import fetch: Firecrawl 未启动 | `Firecrawl 抓取失败` | 检查 `localhost:3672`，或手动 store |
| km_import store: 重复入库 | `疑似重复入库` | 告知用户，如需更新先删旧条目 |
| km_import store: 内容太短 | `content 过短` | 检查输入是否截断 |
| git push 超时/失败 | 超时或失败提示 | 文件已写入本地，不阻塞流程，稍后手动 push |

**git push 触发时机**：`km_import store` 自动 push、`km_import res` 自动 push、`km_lint --fix` 自动 push。
| 路径含空格 | macOS 下载常见 | shell 用引号包裹或用 `\\` 转义 |

## km_lint --fix 自动化修复内容

`km_lint.py --fix --skip-url-check` 自动处理：
- 清除死链、修复孤立文件、补全缺失 resource
- 重建 `entries/index.md` 和 `entries/by-tag/` 标签索引
- 自动发现并双向写入交叉关联（同标的+共享标签+关键词重叠）
- 重建知识图谱
- 修复后再次 lint 验证

导入 5-10 条新条目后建议运行一次，保持交叉引用密度。

## 依赖

- `_shared/git.py` `_shared/dotenv.py` `_shared/proxy.py`
- `pymupdf`（通过 `/tmp/research-pdf-venv`）
- 远程仓库：`git@github.com:shunchengGit/inv-knowledge.git`
