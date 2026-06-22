# 宏观利率数据获取指南

## 10Y 美债收益率

```bash
# yfinance ^TNX（需代理）
cd {baseDir} && uv run python3 -c "
import yfinance as yf, os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
tnx = yf.Ticker('^TNX')
hist = tnx.history(period='1mo')
print(hist.tail(10).to_string())
"
# ^TNX = 10Y, ^IRX = 13周T-bill, ^FVX = 5Y, ^TYX = 30Y
# Close 列即为收益率（如 4.595 = 4.595%）
```

- **注意**：`^TNX` 的 `info` 端点经常失败，但 `history` 端点通常可用；优先用 `history` 获取最近收盘值
- **注意**：收益率数据为百分比数值（4.595 = 4.595%），不是价格
- 详细的 Yahoo Finance 限流应对策略见 `references/yahoo-rate-limit-strategy.md`

## A 股利率

中国10年国债收益率无免费稳定API，可用 `akshare.bond_china_yield(start_date="20260501")` 获取中债收益率曲线。
