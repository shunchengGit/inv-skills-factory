---
name: gen-knowledge-curator
description: 当需要收集、整理、检索或管理知识资料时使用，支持从网页采集、LLM总结分类、存储到Git仓库、搜索和统计分析
version: 0.2.0
commands:
  - /km_init - 拉取知识库并输出 Index 结构化数据
  - /km_import - 从 URL 抓取知识（Firecrawl + pwright 兜底）
  - /km_search - 搜索知识库条目（标题/内容/标签）
  - /km_stats - 查看知识库统计信息
  - /km_lint - 检查知识库完整性（死链、孤立文件、URL可达性、重复检测、内容质量）
---

# gen-knowledge-curator：个人知识管理

## 命令

| 命令 | 用途 |
|------|------|
| `/km_init` | 从远程仓库拉取知识库到 `~/.knowledge`，输出 Index 结构化数据 |
| `/km_import <url>` | 抓取 URL 内容 → Agent 总结分类 → 存储到知识库 |
| `/km_search <query>` | 搜索知识库条目，支持按分类过滤 |
| `/km_stats` | 查看知识库统计信息（分类分布、最近导入等） |
| `/km_lint` | 检查知识库完整性（支持 `--fix` 自动修复） |

## 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/km_init.py` | 拉取仓库 + 输出 Index JSON |
| `scripts/km_import.py fetch <url>` | 抓取 URL 内容（Firecrawl → pwright 兜底） |
| `scripts/km_import.py store --title T --category C --url U --content MD` | 存储知识条目 + 更新 Index + git 同步 |
| `scripts/km_import.py store --title T --category C --url U --content-file F` | 从文件读取内容并存储（推荐，避免管道截断） |
| `scripts/km_import.py categories` | 列出所有可用分类 |
| `scripts/km_search.py <query>` | 搜索知识库条目 |
| `scripts/km_stats.py` | 输出知识库统计信息 |
| `scripts/km_lint.py` | 检查知识库完整性（支持 `--fix` 自动修复） |

## 典型工作流

```
1. /km_init                              ← 拉取知识库，感知所有条目
2. /km_import https://example.com/article ← 抓取内容
3. Agent 总结 + 选分类（对话中完成）
4. km_import.py store --title ... --category ... ← 存储并同步
   # 推荐用法：先 write_file 写入 /tmp/xxx.md，再用 --content-file 参数导入
   # 备选：直接传入 --content 参数（注意管道截断风险）
5. /km_search "关键词"                      ← 检索已有知识
6. /km_stats                             ← 查看知识库概况
7. /km_lint                              ← 定期检查完整性
```

## 知识库结构

```
~/.knowledge/                    ← git 仓库
├── index/                       ← 分类索引（每分类一个文件，减少 git 冲突）
│   ├── investing.md
│   ├── programming.md
│   └── ...
├── investing/                   ← 分类目录（自动创建）
│   └── dcf-valuation.md
├── programming/
│   └── python-async.md
└── _unsorted/                   ← 未归类兜底
    └── random-article.md
```

## 预定义分类体系

| 分类 | 说明 |
|------|------|
| `investing` | 投资分析与估值 |
| `programming` | 编程与工程 |
| `ai-ml` | AI 与机器学习 |
| `product` | 产品与运营 |
| `career` | 职业与成长 |
| `reading` | 阅读与笔记 |
| `tools` | 工具与效率 |
| `life` | 生活与其他 |
| `_unsorted` | 未归类兜底 |

## 知识条目格式

```markdown
---
url: https://example.com/article
imported: 2026-05-26
category: investing
tags: [python, async]
---

# 文章标题

## 摘要
3-5 句总结

## 关键要点
- 要点1
- 要点2
```

## 依赖

- `inv-web-crawler`：Playwright 无头浏览器抓取
- `_shared/proxy.py`：代理检测
- 远程仓库：`git@github.com:shunchengGit/knowledge.git`
