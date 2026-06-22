---
name: inv-knowledge-curator
description: 个人知识管理（OKF v0.1）：URL采集 → LLM总结分类 → 交叉关联 → Git仓库存储 + 索引 + 搜索 + Lint + 可视化
version: 1.3.0
commands:
  - /km_init - 拉取知识库并输出 Index 结构化数据
  - /km_import - 从 URL 抓取知识，总结分类，建立交叉关联，存入 OKF 知识库
  - /km_search - 搜索知识库条目（标题/描述/内容）
  - /km_stats - 查看知识库统计信息
  - /km_lint - 检查知识库完整性（死链/孤立/URL可达性/重复/OKF合规/旧格式/图谱过期）
  - /km_visualize - 生成知识图谱（Cytoscape.js 交互式 HTML）
---

# inv-knowledge-curator：个人知识管理

## 命令

| 命令 | 用途 |
|------|------|
| `/km_init` | 拉取知识库到 `~/.knowledge`，输出 Index |
| `/km_import <url>` | 抓取 → 总结 → 分类 → **交叉关联** → 存储（含图谱 + log 自动更新） |
| `/km_search <query>` | 搜索，支持按分类过滤 |
| `/km_stats` | 统计（分类/类型分布、标签、时间范围） |
| `/km_lint` | 完整性检查（`--fix` 自动修复） |
| `/km_visualize` | 生成交互式知识图谱 |

## 导入流程（关键：必须建交叉关联）

```
1. km_search 搜索已有条目                           ← 找相关条目
2. km_import.py fetch <url>                         ← 抓取内容
3. Agent 阅读内容 → 确定 type → 选分类 → 加 tags
4. Agent 写摘要（3-5句）＋ 提取关键要点（3-7条）
5. 🔗 在正文中引用相关条目：[条目名](relative/path.md) ← 建交叉关联
6. km_import.py store --title ... --content-file /tmp/xxx.md ← 存储
   → 自动更新 index.md + log.md + knowledge-graph.html + git push
```

> ⚠ **建关联是必须步骤，不是可选项。** 没有交叉引用 = 知识图谱只有孤立节点。

## 知识条目格式（OKF v0.1）

```markdown
---
type: Article          # Article | Analysis | Reference | Note | Synthesis
title: 文章标题
description: 一句话描述
timestamp: 2026-06-22T00:00:00+08:00
resource: https://example.com/article
tags: [tag1, tag2]
---

# 文章标题

## 摘要
3-5 句总结，不要留空。说清核心观点/数据/结论。

## 关键要点
- 要点1
- 要点2
- 要点3

## 关联
- [相关条目1](investing/related-article.md) — 为什么相关
- [相关条目2](ai-engineering/another.md) — 为什么相关

> **摘要和关键要点不能留空或填"AI 待填充"。**

## 引用
[1] [来源标题](https://source.url)
```

### 文件命名

- `km_import store` 自动用 `slugify()` 生成 kebab-case 文件名
- 避免 `：` `空格` `+` `"` `'` 等特殊字符（导致路径问题）
- 时效性内容可选日期前缀：`2026-06-22-文章标题.md`
- 使用中文标题：方便直接浏览文件系统

### type 取值指南

| type | 适用场景 |
|------|---------|
| `Article` | 采集的外部文章/新闻 |
| `Analysis` | 自己的分析、研判、推理 |
| `Reference` | 数据、API 文档、常量表（纯参考） |
| `Synthesis` | 多源综合报告（`inv-topic-researcher` 产出） |
| `Note` | 随手记、片段、想法 |

## 交叉引用规范

OKF 用标准 markdown 链接建立关联：

```markdown
福耀玻璃的商业模式与[台积电](investing/tsmc-analysis.md)有本质区别——
前者是制造壁垒，后者是技术壁垒。
```

**规则**：
- 导入时 `km_search` 搜标题/描述，找出 ≥2 个相关条目
- 在「关联」节列出来，并在正文自然处加链接
- 链接用**相对路径**：`[标题](category/slug.md)`
- 可以在 `引用` 节列外部来源 URL

## 脚本

| 脚本 | 用途 |
|------|------|
| `km_init.py` | 拉取仓库 + 输出 Index |
| `km_import.py fetch <url>` | 抓取 URL（Firecrawl → pwright 兜底） |
| `km_import.py store --title ... --content-file F` | 存储（推荐用文件导入） |
| `km_search.py <query>` | 搜索 |
| `km_stats.py [--json]` | 统计 |
| `km_lint.py [--fix] [--skip-url-check]` | 完整性检查 |
| `km_visualize.py [-o path]` | 生成图谱 |
| `km_migrate_to_okf.py [--apply]` | 旧格式迁移 |

## 知识库结构（OKF bundle）

```
~/.knowledge/
├── log.md                   ← 变更日志（km_import 自动追加）
├── investing/
│   ├── index.md             ← 分类索引
│   └── article.md
├── ai-engineering/
│   └── index.md
└── _unsorted/
```

## 依赖

- `_shared/pwright.py`：Playwright 网页抓取
- `_shared/git.py`：git 同步
- 远程仓库：`git@github.com:shunchengGit/knowledge.git`
