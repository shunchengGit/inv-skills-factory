---
name: inv-topic-researcher
description: 对投资主题持续搜索研究，结果存入知识库。串联 inv-web-crawler 和 gen-knowledge-curator
version: 1.0.0
trigger:
  - 研究主题
  - 主题研究
  - 调研
  - 搜索并整理
  - research
dependencies:
  - inv-web-crawler
  - gen-knowledge-curator
---

# inv-topic-researcher：投资主题持续研究

串联 `inv-web-crawler`（搜索+抓取）和 `gen-knowledge-curator`（存储），
对某个投资主题持续采集、整理、入库。

## 命令

| 命令 | 用途 |
|------|------|
| `/research <主题>` | 研究投资主题，搜索并整理到知识库 |
| `/research-batch <url1> <url2> ...` | 批量抓取已知 URL 到知识库 |

## 适用场景

- "研究腾讯 AI 战略"
- "调研纯碱价格走势"
- "搜索福耀玻璃竞争格局"
- "研究光伏行业政策变化"

## 完整流程

### 1. 搜索

优先用英文关键词（SearXNG 中文搜索效果差）：

```bash
curl -s -X POST http://localhost:3672/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "<english keywords>"}'
```

搜索策略：
- 公司研究：`"<公司名> stock analysis strategy 2026"`
- 行业研究：`"<行业> industry outlook trend 2026"`
- 宏观研究：`"<主题> macro economy impact 2026"`
- 估值相关：`"<公司> valuation DCF PE comparison"`

SearXNG 不可用时（Connection refused），提示用户提供 URL，用 `/research-batch`。

### 2. 去重

```bash
uv run custom-skills/general/gen-knowledge-curator/scripts/km_init.py
```

从 Index 输出中提取所有已导入 URL，跳过重复。

### 3. 逐条处理（抓取 → 分析 → 存储，一条一条来）

**每抓到一条有效内容，立即分析存储，不批量积攒。**
后续 URL 失败不影响已入库的内容。

对每个新 URL：

```
┌─ 抓取 ─────────────────────────────────────────┐
│ 1. Firecrawl POST :3672/v1/scrape              │
│    → 成功（≥500字符且非拦截页）→ 跳到分析      │
│    → 失败 → 步骤 2                             │
│ 2. pwright 兜底                                │
│    uv run .../pwright_scrape.py scrape "<url>"  │
│    → 成功（≥100字符）→ 跳到分析                │
│    → 失败 → 记录失败原因，继续下一个 URL        │
├─ 分析 ─────────────────────────────────────────┤
│ 3. 投资视角分析：                              │
│    - 摘要：核心论点 + 关键数据 + 信号方向       │
│    - 分类：investing / company-analysis /       │
│            industry-trends / macro / valuation   │
│    - 标题：简洁中文标题                         │
├─ 存储 ─────────────────────────────────────────┤
│ 4. 立即入库：                                  │
│    uv run .../km_import.py store \              │
│      --title "..." --category "..." \           │
│      --url "..." --content "..."                │
│    → git.sync() 自动 push                      │
└────────────────────────────────────────────────┘
```

抓取工具选择：

| 优先级 | 工具 | 适用站点 |
|--------|------|---------|
| 1 | Firecrawl (`:3672/v1/scrape`) | CNBC、BBC、Wikipedia、CFI |
| 2 | pwright (`pwright_scrape.py scrape`) | Investopedia、Yahoo Finance 等 JS 渲染页面 |

内容质量检查：
- 正文 ≥ 500 字符（Firecrawl）或 ≥ 100 字符（pwright）
- 排除 Cloudflare 拦截页（含 "Just a moment"、"Checking your browser"）
- 排除纯导航页（链接密度过高）

## 异常处理

| 异常 | 处理 |
|------|------|
| 某条 URL 失败 | 记录原因，**继续下一条**，不影响已入库内容 |
| 某条分析/存储失败 | 记录原因，继续下一条 |
| SearXNG 不可用 | 提示用户给 URL，切 `/research-batch` |
| 搜索无结果 | 换英文关键词重试 1 次；仍无结果则提示扩大搜索词 |
| 结果全为已导入 | 输出"无新内容"，结束 |
| Firecrawl 不可用 | 全部降级到 pwright |
| 超时（30s） | 重试 1 次，仍失败则标记 failed |
| 反爬拦截 | 跳过，标记 blocked（Reuters、Macrotrends 等已知拦截站） |
| 内容过短 | 跳过，标记 low_content |
| git push 失败 | 本地已保存，稍后 `km_init` 同步 |
| 全部失败 | 输出失败原因汇总，不写入空条目 |

## 输出格式

```
# 投资主题研究：{topic}
> 研究时间：{timestamp}

## 结果汇总
| 状态 | 数量 |
|------|------|
| 新增入库 | {imported} |
| 跳过（重复）| {duplicates} |
| 抓取失败 | {failed} |
| 搜索命中 | {total} |

## 新增条目
- [{title}]({rel_path}) — {url}
...

## 失败明细
| URL | 原因 |
|-----|------|
| https://... | timeout |
| https://... | blocked (Cloudflare) |
```

## 依赖

- `inv-web-crawler` — 搜索 + Firecrawl/pwright 抓取
- `gen-knowledge-curator` — 知识库存储 + git 同步
- `lib/pwright.py` — JS 渲染页面兜底
- `lib/git.py` — git 操作
