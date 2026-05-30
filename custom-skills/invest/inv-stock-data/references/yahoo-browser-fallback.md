# Yahoo Finance pwright 降级方案

当 yfinance API 全端点限流时，使用 pwright_scrape 抓取 Yahoo Finance 网页。

## 用法

```bash
# 抓取股票页面 → Markdown
uv run custom-skills/inv-web-crawler/scripts/pwright_scrape.py scrape "https://finance.yahoo.com/quote/AAPL/"

# 抓取纯文本（更快）
uv run custom-skills/inv-web-crawler/scripts/pwright_scrape.py text "https://finance.yahoo.com/quote/AAPL/"
```

## 在 Claude Code 中调用

```
# 先用 pwright_scrape 抓取页面
uv run custom-skills/inv-web-crawler/scripts/pwright_scrape.py scrape "https://finance.yahoo.com/quote/AAPL/"

# 从返回的 markdown 中提取数据
# 返回 JSON 格式：
# {"success": true, "title": "...", "markdown": "...", "url": "..."}
```

## 与 Firecrawl adapter 对比

| 特性 | Firecrawl | pwright_scrape |
|------|-----------|----------------|
| JS 渲染 | 无 | 有 |
| Yahoo Finance | ❌ 部分数据缺失 | ✅ 完整 |
| 代理支持 | 需手动设置 | 自动检测 |
| 输出格式 | Markdown | Markdown / 纯文本 |

## JS 提取技巧（补充）

当 yfinance API 全端点限流时，用 pwright_scrape 抓取后直接提取结构化数据更高效：

```javascript
// 在 pwright_scrape 抓取 Yahoo Finance 页面后，从 markdown 中提取
const result = {};
document.querySelectorAll('li').forEach(li => {
  const spans = li.querySelectorAll('span');
  if (spans.length >= 2) {
    const label = spans[0].textContent.trim();
    const value = spans[1].textContent.trim();
    if (['Previous Close','Open','Day\'s Range','52 Week Range','Volume',
         'PE Ratio (TTM)','EPS (TTM)','Forward Dividend & Yield',
         '1y Target Est','Market Cap'].includes(label)) {
      result[label] = value;
    }
  }
});
JSON.stringify(result);
```

**实测**：TSM 在 yfinance 全端点超时/失败时，浏览器页面 + JS 提取可在 10s 内获取价格、PE(TTM)、EPS、52周范围等关键数据。

## 注意

- Yahoo Finance 有反爬机制，频繁请求可能触发验证码
- 建议每次抓取间隔 3-5 秒
- 如果触发验证码，等待几分钟后重试
