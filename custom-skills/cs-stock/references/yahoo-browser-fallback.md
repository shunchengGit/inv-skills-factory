# Yahoo Finance 浏览器降级方案

## 触发条件

当所有 yfinance API 端点（snapshot/daily/financial/profile）均返回 "possibly delisted; no price data found" 时，且：
- 代理已正确设置（`_proxy_ok: true`）
- 换代理端口（7890→7891→7897）无效
- 等待数分钟后重试仍失败

## 操作步骤

1. 用 `browser_navigate` 访问 `https://finance.yahoo.com/quote/<ticker>/`
2. 从页面 snapshot 中提取关键字段：
   - 当前价格：主区域大字数字（如 "449.200"）
   - 涨跌幅：紧随价格的括号内百分比
   - PE Ratio (TTM)：右侧列表中 "PE Ratio (TTM)" 对应值
   - EPS (TTM)：右侧列表中 "EPS (TTM)" 对应值
   - 52 Week Range：右侧列表中 "52 Week Range" 对应值（格式 "low - high"）
   - Previous Close：右侧列表中 "Previous Close" 对应值
   - Market Cap：右侧列表中 "Market Cap" 对应值
   - Volume：右侧列表中 "Volume" 对应值

3. 数据标注规则：
   - 来源标注为 "Yahoo Finance 网页"
   - 港股报价为延迟报价（非实时盘口）
   - 美股报价可能有15分钟延迟

## 实测记录

### 2026-05-19 腾讯 0700.HK

- yfinance 全端点失败（info/history 均返回 "possibly delisted"）
- 代理端口切换无效
- AkShare `stock_hk_spot_em()` 因系统代理干扰失败
- 浏览器成功抓取：价格 449.200, PE(TTM) 16.14, 52周范围 445.800-683.000

### 港股特殊注意

- 港股页面显示 "HKSE - Delayed Quote"
- 收盘时间标注为 GMT+8（如 "At close: 4:08:27 PM GMT+8"）
- 52周范围可直接从页面读取，无需额外计算

## 高效提取方法：browser_console JS

比解析 snapshot 更快的方式是用 `browser_console` 执行 JS 直接提取结构化数据：

```javascript
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

**实测 2026-05-20**：TSM 在 yfinance 全端点超时（snapshot 300s timeout, financial 返回空），浏览器 + JS 提取 10s 内获取：
- `{"Previous Close":"395.95","52 Week Range":"190.03 - 421.97","PE Ratio (TTM)":"33.79","EPS (TTM)":"11.62","1y Target Est":"467.84"}`

## 局限性

- 无法获取完整财务报表（income_stmt/balance_sheet/cash_flow）
- 无法获取历史日线序列
- PE 为 TTM 口径，无法获取 forward PE
- 页面结构可能随 Yahoo 改版变化
