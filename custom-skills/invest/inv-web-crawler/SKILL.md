---
name: inv-web-crawler
description: 当需要抓取指定 URL 的网页内容时使用，基于 Playwright 无头浏览器。仅支持抓取（需提供 URL），不支持搜索
version: 5.0.0
commands:
  - /pwright_scrape - Playwright JS 渲染抓取 → Markdown
  - /pwright_text - Playwright JS 渲染抓取 → 纯文本
---

# inv-web-crawler：Playwright 网页抓取

> **定位**：纯抓取工具，输入 URL → 输出 Markdown/纯文本。**不支持搜索**（原因见下方）。

## 为什么没有搜索

| 方案 | 问题 |
|------|------|
| SearXNG（原方案） | 对金融术语（"10年期国债"）、英文缩写（CPI/FOMC）、中英混合查询经常返回空结果 |
| 无头浏览器搜 Google/Bing/DuckDuckGo | 全部触发 CAPTCHA，无法使用 |

**替代方式**：浏览器手动搜索 → 找到目标 URL → 用本技能抓取。或直接访问已知站点（CNBC/Investopedia/Yahoo Finance 等）。

## 快速命令

```bash
# Markdown 输出（推荐，保留链接和结构）
uv run --with playwright --with html2text \
  {baseDir}/scripts/pwright_scrape.py scrape <url>

# 纯文本输出（更快，适合只需文字内容的场景）
uv run --with playwright --with html2text \
  {baseDir}/scripts/pwright_scrape.py text <url>

# 指定 CSS 选择器（只提取匹配元素）
uv run --with playwright --with html2text \
  {baseDir}/scripts/pwright_scrape.py scrape <url> --selector "article"

# 延长 JS 等待时间（SPA / 慢页面）
uv run --with playwright --with html2text \
  {baseDir}/scripts/pwright_scrape.py scrape <url> --wait 5000

# 指定加载等待策略
uv run --with playwright --with html2text \
  {baseDir}/scripts/pwright_scrape.py scrape <url> --wait-until networkidle
```

## 脚本参数

| 子命令 | 参数 | 说明 |
|--------|------|------|
| `scrape <url>` | `--selector <css>` | CSS 选择器，只提取匹配元素 |
| | `--wait <ms>` | 页面加载后额外等待毫秒数（默认 3000） |
| | `--wait-until <strategy>` | 加载等待策略：`domcontentloaded`（默认）/ `load` / `networkidle` |
| | `--proxy <url>` | 代理地址（默认自动检测本地 Clash） |
| `text <url>` | `--wait <ms>` | 同 scrape |
| | `--proxy <url>` | 同 scrape |

## 抓取可用性

以下为 2026-05 Playwright 实测：

| 可抓取 | 不可抓取 |
|--------|----------|
| CNBC（实时行情+新闻） | Reuters / Barrons（DataDome 反爬） |
| Investopedia（JS 渲染） | Macrotrends（Cloudflare 拦截） |
| Yahoo Finance（JS 渲染，含实时数据） | 所有搜索引擎（CAPTCHA） |
| BBC / Wikipedia / CFI | — |

## 降级策略

无法抓取的页面按以下优先级降级：

1. **代理重试**：直连超时 → 走 Clash 代理（`--proxy http://127.0.0.1:7890`，脚本自动检测）
2. **延长等待**：SPA 页面内容为空 → `--wait 8000 --wait-until networkidle`
3. **换子页面**：首页被拦截 → 尝试 `/about/`、`/contact/` 等子路径（Cloudflare 常对首页严格但内页宽松）
4. **放弃**：DataDome / Cloudflare 无解，标注"无法抓取，需人工查看"

## 正文提取逻辑

`lib/pwright.py` 内置智能正文提取：按顺序遍历语义选择器，首个 >200 字符命中即为正文：

```
main → article → [role='main'] → .post-content → .article-content
  → .content → #content → #main → .markdown-body → 回退 body 全页
```

- `scrape` 子命令先提取 HTML → `html2text` 转 Markdown（保留链接、忽略图片）
- `text` 子命令直接提取 `inner_text()`，跳过 html2text，速度更快
- 输出截断 60,000 字符

## 代理

脚本启动时自动调用 `lib/proxy.py` 的 `detect_proxy()`，按以下顺序检测：

1. 环境变量 `HTTPS_PROXY` / `HTTP_PROXY`
2. 本地 Clash 端口扫描（7890 → 7891 → 7897）
3. 无可用代理时直连

也可手动指定：`--proxy http://127.0.0.1:7890`。

## 常见问题

| 问题 | 解决 |
|------|------|
| `playwright not installed` | 需要浏览器引擎，先跑一次 `uv run playwright install chromium` |
| 返回空内容 / markdown 为 `\n` | 可能是 SPA 页面，延长等待 `--wait 8000 --wait-until networkidle` |
| `Connection reset` / SSL 错误 | 代理不稳定，检查 Clash 是否正常运行 |
| 境外网站超时 | 确保代理已启动（Clash 7890 端口），脚本应自动检测 |
| 被 Cloudflare/DataDome 拦截 | 无解，标注"无法抓取"，走降级策略 |
| `uv run` 每次下载依赖 | 可在项目级 pyproject.toml 预声明依赖避免重复下载 |
