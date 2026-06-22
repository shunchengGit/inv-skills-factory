---
name: inv-knowledge-curator
description: 个人知识管理：URL采集→LLM总结分类→交叉关联→Git仓库存储。用于整理网页文章、学习笔记、研究资料时
version: 1.4.0
trigger:
  - 知识管理
  - 收藏文章
  - 笔记整理
  - km_init
  - km_import
  - km_search
  - km_stats
  - km_lint
commands:
  - /km_init - 拉取知识库并输出 Index 结构化数据
  - /km_import - 从 URL 抓取知识，总结分类，建立交叉关联，存入 OKF 知识库
  - /km_search - 搜索知识库条目（标题/描述/内容/tags）
  - /km_stats - 查看知识库统计信息
  - /km_lint - 检查知识库完整性（死链/孤立/URL可达性/重复/OKF合规/旧格式/图谱过期）
  - /km_visualize - 生成知识图谱（Cytoscape.js 交互式 HTML）
---

# inv-knowledge-curator：专用投资知识库

> **AI 时代核心原则：元数据 > 目录层级。** `km_search` 基于全文检索 + frontmatter，不依赖文件路径。保持目录扁平，把精力花在 tags 质量和交叉关联密度上。

## 设计哲学

- **AI 检索入口是搜索，不是目录树。** `km_search` 是全文检索 + frontmatter 匹配，文件在哪个子文件夹对检索结果零影响
- **标签组合 > 层级分类。** `#fuyao-glass + #valuation + #risk-factor` 三标签组合比 `positions/fuyao-glass/valuation/risk.md` 三层路径更灵活
- **交叉引用是真正的结构。** 知识图谱的边来自 markdown 链接，不来自文件系统层级
- **扁平 = 零分类焦虑。** 导入时只思考 type + tags + 关联，不用纠结放在哪个文件夹

## 命令

| 命令 | 用途 |
|------|------|
| `/km_init` | 拉取知识库到 `~/.inv-knowledge`，输出 Index |
| `/km_import <url>` | 抓取 → 总结 → 分类 → **交叉关联** → 存储 |
| `/km_search <query>` | 搜索（标题/描述/内容/tags），支持按 type/tags 过滤 |
| `/km_stats` | 统计（分类/类型分布、标签、时间范围） |
| `/km_lint` | 完整性检查（`--fix` 自动修复） |
| `/km_visualize` | 生成交互式知识图谱 |

## 知识库结构（OKF bundle）

```
~/.inv-knowledge/
├── log.md                   ← 变更日志（自动追加）
├── knowledge-graph.html     ← 交互式知识图谱
├── investing/               ← 所有投资知识（扁平，不细分目录）
│   ├── index.md             ← 分类索引（按 type 分组）
│   └── *.md                 ← 知识条目
└── _shared/                 ← git 同步等共享模块
```

> **目录不细分。** 当前 investing/ 下所有条目平铺。未来超 200 条时再考虑按标的分目录。在此之前，tags + 交叉引用承担一切组织功能。

## 导入流程

```
1. type 判定（见下方取值指南）                ← 先确定这是什么类型的知识
2. tags 设计（标的 + 分析维度 + 时效）         ← 至少 1 个标的标签 + 2 个分析维度标签
3. km_search 搜索已有条目                     ← 找 ≥2 个相关条目
4. 写摘要（3-5句）+ 关键要点（3-7条）
5. 🔗 建交叉关联：关联节 + 正文自然引用       ← 每条 ≥2 个关联
6. km_import.py store → 自动更新 index/log/图谱 + git push
```

> ⚠ **建关联是必须步骤，不是可选项。** 没有交叉引用 = 知识图谱只有孤立节点 = 检索召回率暴跌。

## 知识条目格式（OKF v0.1）

```markdown
---
type: Article          # 见下方 type 取值指南
title: 文章标题
description: 一句话描述（搜索召回的关键字段，认真写）
timestamp: 2026-06-22T00:00:00+08:00
resource: https://example.com/article
tags: [标的标签, 分析维度标签, 时效标签]
---

# 文章标题

## 摘要
3-5 句总结，不要留空。说清核心观点/数据/结论。

## 关键要点
- 要点1
- 要点2
- 要点3

> **摘要和关键要点不能留空或填"AI 待填充"。**

## 关联
- [相关条目1](investing/related-article.md) — 为什么相关（写具体原因，不只是"相关"）
- [相关条目2](investing/another.md) — 为什么相关

## 引用
[1] [来源标题](https://source.url)
```

### 文件命名

- `km_import store` 自动用 `slugify()` 生成 kebab-case 文件名
- 时效性内容推荐日期前缀：`2026-06-22-文章标题.md`
- 使用中文标题：方便直接浏览文件系统
- 避免 `：` `空格` `+` `"` `'` 等特殊字符

### type 取值指南

| type | 适用场景 | 实例 |
|------|---------|------|
| `Article` | 采集的外部文章/新闻/数据快照 | 两融数据、南向资金、股价行情 |
| `Analysis` | 自己的分析、研判、推理、深度研究 | 竞争壁垒分析、汇兑风险深度分析、一季报业绩分析 |
| `Reference` | 基准数据锚点、年报核心数据、官方来源 | 年报核心要点、IR 页面数据 |
| `Synthesis` | 多源综合报告（`inv-topic-researcher` 产出） | 行业综合研判、跨标的对比报告 |
| `Note` | 随手记、片段、想法 | 投资灵感、待验证假设 |

> **判断标准**：内容是"自己的判断和推理"→ `Analysis`；内容是"纯数据锚点供其他分析引用"→ `Reference`。

### tags 设计规范

**三层标签体系**（每条至少覆盖前两层）：

| 层级 | 含义 | 示例 |
|------|------|------|
| **标的** | 哪个公司/行业 | `#fuyao-glass` `#tsmc` `#tencent` |
| **分析维度** | 什么角度 | `#valuation` `#risk-factor` `#competitive-advantage` |
| **时效** | 时间锚点 | `#2026-Q1` `#2024` `#2026-06` |

**分析维度标签词库**：

| 类别 | 可用标签 |
|------|---------|
| 估值相关 | `#valuation` `#valuation-snapshot` `#profit-trend` |
| 风险相关 | `#risk-factor` `#fx-risk` `#geopolitical-risk` |
| 竞争相关 | `#competitive-advantage` `#moat` `#porter-five-forces` `#industry-position` |
| 商业模式 | `#business-model` `#technology-moat` `#manufacturing-excellence` `#foundry` |
| 数据性质 | `#baseline-data` `#official-source` `#third-party-analysis` `#news-roundup` |
| 市场信号 | `#sentiment` `#short-term` `#capital-flow` `#margin-trading` |
| 其他 | `#management` `#governance` `#sustainability` `#carbon-neutral` `#rd-capability` `#product` |

## 交叉引用规范

```markdown
福耀玻璃的商业模式与[台积电](investing/台积电商业模式与护城河分析.md)有本质区别——
前者是制造壁垒，后者是技术壁垒。
```

**规则**：
- 导入时必须 `km_search` 搜标题/描述/tags，找出 ≥2 个相关条目
- 在「关联」节列出关联，**写明为什么相关**（不只是"相关"二字）
- 在正文自然处加链接引用
- 链接用**相对路径**：`[标题](investing/slug.md)`
- 优先跨标的关联（如福耀↔台积电），制造壁垒 vs 技术壁垒的对比价值最高

## 脚本

| 脚本 | 用途 |
|------|------|
| `km_init.py` | 拉取仓库 + 输出 Index |
| `km_import.py fetch <url>` | 抓取 URL（Firecrawl；失败需手动 store） |
| `km_import.py store --title ... --content-file F` | 存储（推荐用文件导入） |
| `km_search.py <query>` | 搜索 |
| `km_stats.py [--json]` | 统计 |
| `km_lint.py [--fix] [--skip-url-check]` | 完整性检查 |
| `km_visualize.py [-o path]` | 生成图谱 |
| `km_migrate_to_okf.py [--apply]` | 旧格式迁移 |

## 依赖

- `_shared/git.py`：git 同步
- 远程仓库：`git@github.com:shunchengGit/inv-knowledge.git`
