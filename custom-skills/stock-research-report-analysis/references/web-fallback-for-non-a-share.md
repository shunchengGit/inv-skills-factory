# 非 A 股标的的研报分析 Web 降级策略

## 问题

本地研报 PDF 目录（`~/Desktop/股票研报`）以 A 股/港股券商研报为主。对于美股（如 TSM、AAPL）或台股（如 2330.TW），本地 PDF 通常为空，`/research_pdf list` 返回无匹配。

## 降级策略

当本地 PDF 为空时，按以下优先级补充：

### 1. Yahoo Finance 分析师数据（首选）
通过 `cs-stock` 的 `financial` 和 `profile` 子命令获取：
- `targetMeanPrice` / `targetHighPrice` / `targetLowPrice`（分析师目标价）
- `recommendationMean` / `recommendationKey`（评级共识）
- `numberOfAnalystOpinions`（覆盖分析师数量）
- `trailingPE` / `forwardPE` / `priceToBook`（估值指标）
- `revenue_growth` / `earnings_growth`（增长指标）

### 2. 搜狗微信搜索（中文财经内容）
- URL: `https://wx.sogou.com/weixin?type=2&query={公司名+研报+目标价}`
- **注意**：频繁请求会触发验证码（CAPTCHA），需间隔使用
- 编码：返回 GBK，需 `iconv -f gbk -t utf-8` 或 Python requests 处理
- 适合搜索外资投行研报的中文翻译/摘要

### 3. Brave Search（英文关键词）
- URL: `https://search.brave.com/search?q={KEYWORD}`
- 需 `-A` 伪装 UA
- 英文关键词效果好（如 `TSMC analyst target price 2025`），中文效果差
- 实测可能返回空结果，不稳定

### 4. 浏览器直接访问
- 财经网站（TipRanks、MarketWatch、Seeking Alpha）常触发 Cloudflare 验证
- Google 搜索几乎必触发 CAPTCHA
- 可尝试但不可靠

### 5. 直接用 yfinance Python API
```python
import yfinance as yf
tsm = yf.Ticker('TSM')
info = tsm.info  # 含 currentPrice, targetMeanPrice 等
rec = tsm.recommendations  # 分析师评级分布
up = tsm.upgrades_downgrades  # 升降级记录（可能数据很旧）
news = tsm.news  # 新闻标题
```

## 输出格式调整

当使用 Web 降级策略时：
- 在「覆盖文件清单」节注明「本地无 PDF，以下基于 Yahoo Finance + 网络公开信息」
- 在「分报告摘要」节改为「分析师共识与关键观点」
- 数据来源与时点必须标注
- 明确说明与本地 PDF 研报分析的差异（缺少卖方分篇对比、缺少详细盈利预测表等）

## 搜索引擎实测可用性（2026-05 更新）

| 引擎 | curl 可用性 | 中文财经 | 英文财经 | 备注 |
|------|:---:|:---:|:---:|------|
| 搜狗微信 | ⚠️ GBK+验证码 | ⭐⭐⭐⭐⭐ | ❌ | 最佳中文财经来源，但易触发 CAPTCHA |
| Brave | ⚠️ 不稳定 | ⭐⭐ | ⭐⭐⭐ | 英文关键词偶尔有效 |
| Ecosia | ⚠️ 未验证 | — | — | 可能可用 |
| Google | ❌ CAPTCHA | — | — | curl 几乎不可用 |
| DuckDuckGo | ❌ 超时 | — | — | HTML 版频繁超时 |
| Baidu | ❌ 拦截 | — | — | curl 被拦截 |
