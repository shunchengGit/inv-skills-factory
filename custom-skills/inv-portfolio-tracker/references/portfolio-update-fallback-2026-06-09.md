# 持仓更新降级策略参考（2026-06-09 会话总结）

## 背景

本次持仓更新（7只标的：A股×3 + 港股×2 + 美股×2）遇到多个数据源问题，最终通过 QQ Finance 批量查询完成更新。

## 遇到的问题

### 1. Yahoo 限流（单个 snapshot 也触发）

**现象**：
- `cs_stock_info.py snapshot AAPL` → `YFRateLimitError: possibly delisted; no price data found`
- `cs_stock_info.py snapshot TSM` → 同样错误
- 代理 7890 能通 Google，说明代理本身正常
- 这是 Yahoo 对当前节点/IP 的限流，非代理问题

**处理**：
- 不逐个重试（会加剧限流）
- 直接切换到 QQ Finance 批量查询

### 2. ETF snapshot 返回空数据

**现象**：
- `cs_stock_info.py snapshot 588000` → `daily: [], nav: null`
- `cs_stock_info.py snapshot 513010` → `daily: [], nav: null`
- AkShare 的 ETF 数据源不稳定

**处理**：
- QQ Finance `sh588000` 和 `sh513010` 可正常获取现价和涨跌幅

### 3. 港股 Yahoo 降级到新浪

**现象**：
- `cs_stock_info.py snapshot 00700` → 降级到新浪港股源，有价格但无 PE/52周数据
- `cs_stock_info.py snapshot 07709` → 同样降级

**处理**：
- QQ Finance `hk00700` 和 `hk07709` 提供 PE（field 39）和 52周高/低（fields 35/36）

## QQ Finance 批量查询方案

### 请求 URL

```
https://qt.gtimg.cn/q=usAAPL,usMSFT,usTSM,hk00700,hk07709,sh600660,sh588000,sh513010
```

### 必需 Header

```
Referer: https://gu.qq.com
```

### 美股字段索引（扩展）

| 索引 | 字段 | 示例（usAAPL） |
|------|------|----------------|
| 3 | 现价 | "292.84" |
| 4 | 昨收 | "301.54" |
| 5 | 今开 | "300.28" |
| 32 | 涨跌幅% | "-2.88" |
| 35 | 52周最高 | "317.40" |
| 36 | 52周最低 | "194.31" |
| 39 | PE | "35.45" |
| 44 | 股息率 | "0.36" |
| 46 | 总股本 | "14687356000" |

### A股/港股字段索引（标准）

| 索引 | 字段 | 示例（sh600660） |
|------|------|------------------|
| 3 | 现价 | "53.41" |
| 4 | 昨收 | "53.15" |
| 5 | 今开 | "53.14" |
| 32 | 涨跌幅% | "0.49" |
| 33 | 最高价 | "53.98" |
| 34 | 最低价 | "52.76" |

港股（hk00700）字段与 A 股类似，PE 在 field 39。

## Python 解析示例

```python
import requests

def parse_qq_finance(text):
    """解析 QQ Finance 返回文本"""
    results = {}
    for line in text.strip().split(';'):
        line = line.strip()
        if not line or '~' not in line:
            continue
        # 提取变量名，如 v_usAAPL
        if '=' in line:
            var_name = line.split('=')[0].strip()
            code = var_name.replace('v_', '')
        else:
            continue
        # 提取引号内的值
        if '"' in line:
            value = line.split('"')[1]
            parts = value.split('~')
            if len(parts) > 5:
                results[code] = {
                    'name': parts[1],
                    'price': float(parts[3]) if parts[3] else None,
                    'prev_close': float(parts[4]) if parts[4] else None,
                    'open': float(parts[5]) if len(parts) > 5 and parts[5] else None,
                    'chg_pct': float(parts[32]) if len(parts) > 32 and parts[32] else None,
                    'high': float(parts[33]) if len(parts) > 33 and parts[33] else None,
                    'low': float(parts[34]) if len(parts) > 34 and parts[34] else None,
                    'pe': float(parts[39]) if len(parts) > 39 and parts[39] else None,
                    '52w_high': float(parts[35]) if len(parts) > 35 and parts[35] else None,
                    '52w_low': float(parts[36]) if len(parts) > 36 and parts[36] else None,
                }
    return results

# 使用
codes = ['usAAPL', 'usMSFT', 'usTSM', 'hk00700', 'hk07709', 'sh600660', 'sh588000', 'sh513010']
url = f'https://qt.gtimg.cn/q={",".join(codes)}'
r = requests.get(url, headers={'Referer': 'https://gu.qq.com'}, timeout=10)
data = parse_qq_finance(r.text)

for code, info in data.items():
    print(f"{code}: {info['name']} 现价={info['price']} 涨跌幅={info['chg_pct']}% PE={info['pe']}")
```

## 关键结论

1. **美股 us 前缀已实测可用**（2026-06-09）：usAAPL、usMSFT、usTSM 均成功返回数据
2. **QQ Finance 是持仓更新的首选降级方案**：一次请求覆盖所有市场，避免代理切换和 Yahoo 限流
3. **ETF 数据始终走 QQ Finance**：AkShare 的 ETF snapshot 经常返回空，不要依赖
4. **港股 PE 从 QQ Finance 获取**：Yahoo 降级到新浪后无 PE 数据，QQ Finance field 39 有值
5. **批量查询优于逐个 CLI 调用**：8 只标的一次请求 <2s，逐个 snapshot 调用需 50s+ 且易出错

## 待修复（inv-stock-data 技能）

- `references/qq-finance-realtime-api.md` 仍标记"美股 ❌ 不支持"，需更新为"us 前缀已实测可用"
- `skill_manage` 无法访问 inv-stock-data（路径问题），需手动或通过其他方式更新
