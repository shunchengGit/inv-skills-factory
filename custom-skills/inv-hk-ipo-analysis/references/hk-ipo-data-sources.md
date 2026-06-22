# 港股IPO数据源清单与抓取可用性

整理自实际工作经验，按"招股期/暗盘期/上市后"三个阶段列出可用源，标注是否需要降级。

## 招股期信息源（招股价/孖展/基石/认购倍数）

### 一级源（优先，结构化数据全）
| 源 | URL模式 | 抓取状态 | 备注 |
|---|---------|----------|------|
| 新浪财经"活报告" | finance.sina.com.cn/cj/ | ✅ 直接可抓 | 孖展数据更新最快(TradeGo接口) |
| 证券时报STCN | stcn.com/article/ | ✅ 直接可抓 | 内地角度公司分析 |
| 东方财富 | finance.eastmoney.com | ✅ 直接可抓 | 招股书递表新闻 |
| 港交所披露易 | hkexnews.hk | ✅ 直接可抓 | 招股书原文权威源 |

### 二级源（散户视角IPO攻略，含打和点/中签率预测）
| 源 | URL模式 | 抓取状态 | 备注 |
|---|---------|----------|------|
| talkmoney.com.hk | talkmoney.com.hk/{ticker-hk-ipo} | ✅ 可抓 | 含孖展利率比较、暗盘攻略 |
| Facebook券商公告 | facebook.com/UOBKayHian等 | ✅ 可抓 | 大华继显/辉立等公告 |
| 123.com.cn | 123.com.cn/kline/ | ⚠️ 偶尔限流 | IPO追踪深度文 |
| **辉立证券快速摘要PDF** | **research.cyberquote.com.hk/page/htm/kc/share_recommend/pdf/{code}.pdf** | **✅ 可下载** | **券商整理1页摘要：发售价/集资额/市值/孖展息率/回拨机制/集资用途/风险因素/截止时间。`{code}`填4位数字股票代码（如1956、9630），HTTP明文URL需用curl下载后pymupdf解析。抓500页招股书前先看这个，能省3-5次工具调用** |
| **新浪财经孖展统计** | **finance.sina.com.cn/stock/hkstock/ggscyd/{YYYY-MM-DD}/doc-XXX.shtml** | **✅ 可抓** | **每日所有正在招股新股的孖展统计汇总表（股票名/代码/孖展额/超购倍数），一次提取覆盖同期所有新股，比逐只搜索高效。搜"新股孖展统计 {日期}"即可定位** |

### 三级源（已知拦截，避免）
| 源 | URL模式 | 状态 | 降级方案 |
|---|---------|------|----------|
| 经济通etnet | etnet.com.hk/www/tc/stocks/ipo-info | ❌ JS渲染 SPA，正文空 | 改用aastocks |
| hket.com | inews.hket.com | ❌ CloudFront 403 | 改用搜索结果摘要 |
| sl886.com | sl886.com/ipo/{code} | ❌ Cloudflare Challenge | 改用talkmoney.com.hk |

## 暗盘/首日数据源

| 源 | 用途 | 抓取状态 |
|---|------|----------|
| AAStocks暗盘 | aastocks.com/tc/stocks/market/ipo/darktrade | ✅ |
| 富途暗盘 | futunn.com | ⚠️ 部分需登录 |
| 辉立暗盘 | poems.com.hk | ⚠️ 需账户 |

## 抓取顺序建议

1. **券商快速摘要**（30秒可得）：先下载辉立 `research.cyberquote.com.hk/page/htm/kc/share_recommend/pdf/{code}.pdf` 获取发售价/集资额/市值/孖展息率/回拨机制/集资用途/风险因素，作为后续分析的脚手架
2. **招股书原文**：用 PyMuPDF 抓港交所披露易PDF，按 SKILL.md 第一步建立关键词地图，定向提取财务/基石/风险（最权威）
3. **市场热度**：新浪财经"新股孖展统计"日表（一次拿到所有同期新股孖展） + 搜"{ticker} 孖展 倍数"补最新数据
4. **散户视角**：talkmoney.com.hk → 获取打和点、暗盘攻略、首日预测
5. **交叉验证**：至少2源核对孖展倍数（新浪 vs talkmoney vs 券商Facebook vs 辉立摘要）

## 关键数据项的多源核对

按用户 USER.md 中"交叉验证至少2源"硬规则，以下数据必须双源确认：
- 孖展超购倍数（市场冷热风向标，单源误差大）
- 基石占比（招股书 vs 第三方汇总）
- 入场费与每手股数（招股书附录1 vs etnet/aastocks）
- 上市日期（招股书"预期时间表" vs 港交所公告）

## 数据时点标注规范

按用户偏好，输出中必须写明：
- 数据快照时间："截至 YYYY-MM-DD HH:MM"
- 招股期内孖展数据可能小时级变化，超过6小时未更新需重新抓取
- 招股书递表日 vs 招股启动日 vs 上市日，三者不要混用
