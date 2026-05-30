# QQ Finance 实时行情 API（盘中降级方案）

## 概述

QQ Finance API（`qt.gtimg.cn`）是 A 股和港股盘中实时行情的可靠降级数据源。
当 AkShare 东财源因代理干扰失败、新浪 `hq.sinajs.cn` 返回 0.000 时，此 API 仍可正常工作。

## 接口说明

- **URL**: `https://qt.gtimg.cn/q=<codes>`
- **方法**: GET
- **必需 Header**: `Referer: https://gu.qq.com`
- **无需代理**：国内直连，响应快（<2s）

## 代码格式

| 市场 | 前缀 | 示例 |
|------|------|------|
| 沪市 A 股 | sh | sh600660, sh588000 |
| 深市 A 股 | sz | sz159915 |
| 港股 | hk | hk00700, hk07709 |
| 美股 | ❌ 不支持 | — |

## 返回格式

返回文本，每行一个标的，以 `;` 分隔。每行格式：
```
v_sh600660="1~福耀玻璃~600660~55.14~55.08~...";
```
字段以 `~` 分隔，关键字段索引：

| 索引 | 字段 | 示例 |
|------|------|------|
| 0 | 市场 | "1"(沪)/"51"(港) |
| 1 | 名称 | "福耀玻璃" |
| 2 | 代码 | "600660" |
| 3 | 现价 | "55.14" |
| 4 | 昨收 | "55.08" |
| 5 | 今开 | "55.20" |
| 6 | 成交量（手） | "98656" |
| 7 | 成交额（万） | "54320" |
| 8~30 | 买卖盘等 | — |
| 31 | 涨跌额 | "0.06" |
| 32 | 涨跌幅% | "0.11" |
| 33 | 最高价 | "55.70" |
| 34 | 最低价 | "54.90" |

## Python 示例

```python
import requests

codes = ['sh600660', 'sh588000', 'sh513010', 'hk00700', 'hk07709']
url = f'https://qt.gtimg.cn/q={",".join(codes)}'
r = requests.get(url, headers={'Referer': 'https://gu.qq.com'}, timeout=10)

for line in r.text.strip().split(';'):
    line = line.strip()
    if not line or '~' not in line:
        continue
    parts = line.split('~')
    if len(parts) > 5:
        code = parts[2]
        name = parts[1]
        curr = parts[3]
        prev = parts[4]
        chg_pct = parts[32] if len(parts) > 32 else '?'
        print(f'{code}|{name}|现价={curr}|昨收={prev}|涨跌幅={chg_pct}%')
```

## 实测记录

### 2026-05-20 盘中（09:17 CST）

- **背景**：AkShare `stock_zh_a_spot_em()` 因 Clash 代理干扰报 `ProxyError`；新浪 `hq.sinajs.cn` 返回现价 0.000（集合竞价阶段）
- **QQ Finance 结果**：
  - 600660 福耀玻璃: 现价=55.14, 昨收=55.08 ✅
  - 588000 科创50ETF: 现价=1.851, 昨收=1.871 ✅
  - 513010 恒生科技ETF: 现价=0.636, 昨收=0.639 ✅
  - 00700 腾讯控股: 现价=468.00, 昨收=460.00 ✅
  - 07709 南方海力士: 现价=81.16, 昨收=81.14 ✅

## 局限性

- 无 PE/PB/市值/ROE 等基本面数据
- 港股为延迟报价（非实时盘口）
- 不支持美股
- 不支持 ETF 净值（NAV）
- 字段索引可能随腾讯接口改版变化
