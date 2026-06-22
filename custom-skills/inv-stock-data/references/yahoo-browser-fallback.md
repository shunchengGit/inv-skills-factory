# Yahoo Finance Web 降级方案

当 yfinance API 全端点限流时，使用 Agent WebFetch 抓取 Yahoo Finance 网页。

## 用法

Agent 使用内置 WebFetch 工具直接抓取 Yahoo Finance 页面：

```
# Agent 调用 WebFetch 抓取股票页面
WebFetch "https://finance.yahoo.com/quote/AAPL/"
```

WebFetch 会将页面转换为 Markdown，Agent 从中提取关键数据：
- 当前价格、涨跌幅
- PE (TTM)、EPS (TTM)
- 52 周范围
- 市值、成交量
- 分析师目标价

## 提取技巧

从 WebFetch 返回的 Markdown 中提取结构化数据时，关注以下关键词：
- `Previous Close`、`Open`、`Day's Range`
- `52 Week Range`、`Volume`
- `PE Ratio (TTM)`、`EPS (TTM)`
- `Forward Dividend & Yield`、`1y Target Est`
- `Market Cap`

**实测**：TSM 在 yfinance 全端点超时/失败时，WebFetch 可在数秒内获取价格、PE(TTM)、EPS、52周范围等关键数据。

## 注意

- Yahoo Finance 有反爬机制，频繁请求可能触发验证码
- 建议每次抓取间隔 3-5 秒
- 如果触发验证码，等待几分钟后重试
