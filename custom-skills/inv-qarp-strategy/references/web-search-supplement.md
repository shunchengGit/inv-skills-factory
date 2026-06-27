# QARP 搜索增量信息补充

搜索补充的详细工具选择规则、流程和数据源映射。

## 何时触发搜索补充

任一满足即可触发（数据源降级本身见 `data-fallback.md`，本节聚焦搜索增量）：

- 本地研报时效性 > 1 个月，需最新行业数据
- 政策/地缘风险：关税、制裁、监管变化等实时事件
- 管理层/公司动态：股东会发言、重大公告、媒体报道
- 用户明确要求搜索补充或二次验证
- 持仓检查需要交叉验证：官方财报 vs 脚本数据、分析师共识 vs 自建估值

**增量信息获取优先级**：
1. yfinance info + financials + history（已覆盖 90% 需求）
2. 本地券商研报 PDF（inv-knowledge-curator）
3. Agent WebFetch / browser_navigate 直抓特定页面（仅当上述不够时）
4. web_search（最后手段，预期低效）

## 工具选择规则

| 网站类型 | 首选工具 | 说明 |
|----------|---------|------|
| 中国财经/新闻（新浪、东财、腾讯新闻、澎湃、雪球、工信部） | **`browser_navigate`** | `web_extract` 几乎全部返回 Blocked |
| 英文财经（Yahoo Finance、Reuters） | `web_extract` | 成功率较高 |
| 搜索发现链接 | `web_search` → `browser_navigate` | 先搜后打开，不要直接用 web_extract |

**硬规则**：对中国 `.sina.com.cn` / `.eastmoney.com` / `.qq.com` / `.thepaper.cn` / `.xueqiu.com` / `miit.gov.cn` 等域名，**永远不要用 web_extract**，直接用 browser_navigate。浪费时间去重试是无效的。

## 搜索补充流程

1. `web_search` 搜 2-3 个方向（行业数据、政策风险、公司动态）
2. 对搜索结果中的关键链接用 `browser_navigate` 打开获取全文
3. 用 `browser_scroll` + `browser_snapshot` 获取完整页面内容
4. 将搜索发现与 QARP 分析结论对照，修正风险判断
5. 在输出中明确标注"搜索补充"部分，区分原始分析与增量信息

## 可靠的数据源映射

| 数据需求 | 搜索关键词 | 预期来源 |
|----------|-----------|----------|
| 美股财报/分析师 | "MSFT earnings Q3 FY2026 revenue Azure" / "MSFT analyst rating target price" | Microsoft Investor Relations / MarketBeat |
| 美股AI/云数据 | "Microsoft Copilot subscribers 2026 paid seats" | AI Business Weekly |
| 中国汽车产销 | "2026年X月 汽车产销 工信部" | 工信部 wap.miit.gov.cn |
| 乘用车市场展望 | "乘联分会 X月 乘用车市场" | 新浪财经 finance.sina.com.cn |
| 关税/贸易政策 | "福耀玻璃 美国 关税 曹德旺" | 澎湃新闻 m.thepaper.cn |
| 公司最新动态 | "福耀玻璃 最新消息 公告" | 新浪/东财/腾讯新闻 |
| 美股数据补充 | (直接用 inv-stock-data or Yahoo) | — |

## 实践案例

### 福耀玻璃 600660（2026-06-21）
- 本地研报：5篇，2026-04-21~22（约2个月时效性可接受）
- 用户要求搜索补充后，用 web_search 搜了3个方向
- browser_navigate 成功获取：工信部5月汽车数据、澎湃新闻曹德旺专访、新浪财经乘联分会6月展望
- web_extract 全部失败（腾讯新闻、东方财富、雪球、新浪财经均被拦截）
- 关键发现：5月乘用车 -4.2%（较Q1 -10%收窄），曹德旺"大不了关厂"表态——未改变"持有"结论但强化风险判断

### 微软 MSFT（2026-06-21）
- 本地研报：10篇，2026-04-27~06-02（近2个月）
- 用户要求"二次验证"，用 web_search 搜了3个方向
- 关键成果：
  - 微软官方 Q3 FY2026 财报页面：Q3 实际 $829亿营收（超预期$814亿），Azure +40%（超指引37-38%），EPS $4.27（超预期 $4.06），AI 年化营收 $370亿（+123%）
  - MarketBeat：47位分析师共识 Moderate Buy（41 Buy / 6 Hold / 0 Sell），平均目标价 $561.20（上涨空间 48%）
  - TradingKey：FTC 反垄断调查扩大、$1900亿 AI 投资压缩 FCF、6/1 Copilot 宕机
  - AI Business Weekly：Copilot 1500万付费席位，M365 渗透率仅 3.3%
- 修正了之前分析中的偏差：Azure 实际 40% 而非指引 37-38%，EPS 超预期——强化了"好公司被错杀"的判断
