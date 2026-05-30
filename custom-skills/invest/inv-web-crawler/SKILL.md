---
name: inv-web-crawler
description: 当需要搜索网页或抓取页面数据时使用，支持搜索引擎和浏览器模拟抓取
version: 4.0.0
commands:
  - /cs_crawl_search - Web search via SearXNG
  - /cs_crawl_scrape - Full-page scrape → markdown
  - /cs_crawl_crawl - Async multi-page crawl
  - /cs_crawl_extract - Batch URL extraction → markdown
  - /cs_crawl_pwright - Playwright JS-rendered scrape → markdown
---

# inv-web-crawler：搜索与抓取工具箱

## 命令

| 命令 | 用途 |
|------|------|
| `/cs_crawl_search <query>` | Web 搜索（SearXNG） |
| `/cs_crawl_scrape <url>` | 全页抓取 → Markdown（Firecrawl，无 JS） |
| `/cs_crawl_crawl <url>` | 异步多页爬取 |
| `/cs_crawl_extract <url1> <url2> ...` | 批量 URL 抓取 |
| `/cs_crawl_pwright <url>` | Playwright 抓取 → Markdown（有 JS 渲染） |

## 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/pwright_scrape.py scrape <url>` | Playwright 抓取 → Markdown |
| `scripts/pwright_scrape.py scrape <url> --selector article` | 指定 CSS 选择器提取 |
| `scripts/pwright_scrape.py scrape <url> --wait 5000` | 延长 JS 等待时间 |
| `scripts/pwright_scrape.py text <url>` | Playwright 抓取 → 纯文本（更快） |

## 接口

本地 Firecrawl adapter：

```
POST http://localhost:3672/v1/search    — 搜索
POST http://localhost:3672/v1/scrape    — 抓取
POST http://localhost:3672/v1/crawl     — 爬取
POST http://localhost:3672/v1/extract   — 批量提取
```

## SearXNG 限制

对含数字的专业术语（"10年期国债"、"S&P 500"）、金融缩写（"CPI"、"FOMC"）、中英混合查询经常失效。换英文关键词或直接抓已知URL。

## 搜索引擎可用性（2026-05 实测）

所有主流搜索引擎在无头浏览器下都触发 CAPTCHA（Google/Bing/DuckDuckGo/Brave/Ecosia/Yandex），不能用来做搜索。

## 网站抓取可用性（2026-05 实测）

### Firecrawl scrape

| 可抓取 | 不可抓取 |
|--------|----------|
| CNBC 行情页（实时数据+新闻） | Yahoo Finance（JS渲染） |
| BBC Business / Guardian Markets | Investopedia（JS渲染） |
| CFI（金融教育，完整） | MarketWatch（JS+反爬） |
| Wikipedia（完整） | NerdWallet/Forbes/Fidelity/Schwab |

### browser → pwright_scrape（有JS渲染）

| 可抓取 | 不可抓取 |
|--------|----------|
| CNBC | Reuters/Barrons（DataDome） |
| Investopedia | Macrotrends（Cloudflare） |
| BBC / Wikipedia / CFI | 所有搜索引擎（CAPTCHA） |

## 抓取工具选择

| 工具 | JS渲染 | 速度 | 适用 |
|------|--------|------|------|
| Firecrawl scrape | 无 | 快 | 静态页面 |
| web_extract | 无 | 中 | 需LLM摘要 |
| pwright_scrape | 有 | 中 | SPA/JS渲染页面（Investopedia等） |
| pwright_scrape text | 有 | 中 | 只需纯文本时更快 |

## 代理配置

部分境外网站直连不可达，需走代理。代理地址 `http://127.0.0.1:7890`。

**Firecrawl 请求走代理**：
```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

**pwright_scrape 走代理**：自动检测本地 Clash 代理，无需手动配置。

**降级链路**：直连失败 → 走代理 → 回退 Tinybird 代理

## 常见问题

| 问题 | 解决 |
|------|------|
| `Connection refused` | 本地 Firecrawl 未启动，用 pwright_scrape 替代 |
| `Connection reset` / SSL 错误 | 代理不稳定，检查代理是否正常 |
| 境外网站超时 | 检查代理是否启动，设置 HTTP_PROXY/HTTPS_PROXY |
| 返回空内容 | 页面可能是 SPA，用 pwright_scrape 代替 |
| 中文搜索结果差 | 换英文关键词重试 |
