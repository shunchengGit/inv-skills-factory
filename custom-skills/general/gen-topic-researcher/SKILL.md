---
name: gen-topic-researcher
description: 持续搜索某个主题并将结果存入知识库。串联 inv-web-crawler 和 gen-knowledge-curator
version: 1.0.0
trigger:
  - 研究主题
  - 主题研究
  - 搜索并整理
  - research topic
---

# gen-topic-researcher：主题持续研究

串联 `inv-web-crawler`（搜索+抓取）和 `gen-knowledge-curator`（存储），
将某个主题的网络资料持续采集到知识库。

## 命令

| 命令 | 用途 |
|------|------|
| `/research <topic>` | 搜索主题并整理到知识库 |
| `/research-batch <url1> <url2> ...` | 批量抓取已知 URL 到知识库 |

## 完整流程

### 1. 搜索（SearXNG）

```bash
curl -s -X POST http://localhost:3672/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "<topic>"}'
```

如果 SearXNG 不可用（Connection refused），跳过搜索，直接用 `/research-batch` 手动 URL。

### 2. 去重

读取知识库已有条目，提取所有 URL，跳过已存在的：

```bash
uv run custom-skills/general/gen-knowledge-curator/scripts/km_init.py
```

从输出的 `index.categories` 中收集所有 `url` 字段，构建已导入 URL 集合。

### 3. 批量抓取（Firecrawl → pwright 兜底）

对搜索结果中每个新 URL：

```
1. Firecrawl POST http://localhost:3672/v1/scrape {"url": "..."}
   └── 成功且 content ≥ 500 字符 → 跳步骤 4
   └── 失败/空/被拦截 → 步骤 2

2. pwright 兜底
   uv run custom-skills/invest/inv-web-crawler/scripts/pwright_scrape.py scrape "<url>"
   └── 成功且 markdown ≥ 100 字符 → 跳步骤 4
   └── 失败 → 记录失败，继续下一个

3. 附加元数据：title、source（firecrawl/pwright）、fetched_at
```

### 4. Claude 总结分类

对每个成功抓取的内容：
- **摘要**：3-5 句话总结核心内容
- **分类**：从已有分类中选最匹配的，新主题则新建分类
- **标题**：提取或生成简洁中文标题

### 5. 存储到知识库

```bash
uv run custom-skills/general/gen-knowledge-curator/scripts/km_import.py store \
  --title "<标题>" \
  --category "<分类>" \
  --url "<原始URL>" \
  --content "<Markdown正文>"
```

## 异常处理

| 异常 | 处理 |
|------|------|
| SearXNG 不可用 | 提示用户手动提供 URL 列表，用 `/research-batch` |
| 搜索无结果 | 换英文关键词重试；仍无结果则提示用户 |
| Firecrawl 不可用 | 全部走 pwright 兜底 |
| URL 抓取超时（30s） | 重试 1 次，仍失败则跳过 |
| 抓取内容过短（< 100 字符） | 视为失败，记录原因 |
| 反爬拦截（Cloudflare/DataDome） | 跳过，标记为 blocked |
| URL 已存在 | 跳过，标记为 duplicate |
| km_init 未初始化 | 先执行 `/km_init` |
| git push 失败 | 本地已保存，稍后手动同步 |
| 全部 URL 失败 | 输出失败摘要，不写入空条目 |

## 输出摘要

执行完成后输出：

```
# 主题研究：{topic}
搜索命中: {total} 篇
新增入库: {imported} 篇
跳过（重复）: {duplicates} 篇
抓取失败: {failed} 篇（{原因列表}）
```

## 依赖

- `inv-web-crawler`：搜索 + 抓取
- `gen-knowledge-curator`：存储 + git 同步
