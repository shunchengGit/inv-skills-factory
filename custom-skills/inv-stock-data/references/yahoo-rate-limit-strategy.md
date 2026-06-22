# Yahoo Finance API 限流与降级策略（2026-05 实测）

## `yf.Ticker().history()` vs `yf.download()` 行为差异

| 方法 | ^TNX / ^TYX 等指数 | 个股（TSM/0700.HK等） | 备注 |
|------|:---:|:---:|------|
| `yf.Ticker('^TNX').history(period='1mo')` | ⚠️ 有时可用，有时返回 "possibly delisted" | ⚠️ 同上 | 受 Yahoo 端点限流影响大，短周期（1mo）成功率高于长周期（1y） |
| `yf.download('^TNX', period='1y', interval='1d')` | ✅ 更稳定 | ⚠️ 单独可用，批量多标的易失败 | 批量下载端点与 Ticker.history() 走不同 API，限流策略不同 |
| `yf.Ticker('^TNX').history(period='5y', interval='1mo')` | ❌ 几乎必返回 "possibly delisted" | ⚠️ 不确定 | 长周期+月频对指数标的极易触发限流 |

**推荐策略**：
1. 对 ^TNX/^TYX/^FVX/^IRX 等利率指数，**优先用 `yf.download()`**
2. 若 `yf.download()` 也失败，降级到 `yf.Ticker().history(period='1mo')`（短周期成功率更高）
3. 对个股，两种方法均可，但 `yf.download()` 在限流环境下更可靠
4. `yf.download()` 返回的 DataFrame 列可能是 MultiIndex（如 `('Close', '^TNX')`），需用 `.iloc[:, 0]` 或 `['Close']['^TNX']` 提取单列
5. **⚠️ `yf.download()` 批量多标的（如 `yf.download(['TSM','0700.HK'], ...)`）在限流环境下反而更容易全部失败**；逐个请求+间隔3-5s更可靠

## 限流的「连续请求触发」模式（关键发现）

**现象**：同一进程内连续请求多个 Yahoo 标的时，第2-3个请求极易触发 "possibly delisted" 限流，导致超时（实测0700.HK单次51s超时失败）。但**间隔数秒后单独请求同一标的**可在3-5s内成功。

**实测数据**：
| 场景 | TSM | 0700.HK | 说明 |
|------|-----|---------|------|
| 单独请求（首次） | 5.1s ✅ | 3.3s ✅ | 无前序请求，正常 |
| 连续请求第2-3个 | 11s ❌→重试3.8s ✅ | 51s ❌→重试3.0s ✅ | 前序请求消耗了限额 |
| `yf.download` 批量2标的 | ❌ 全部失败 | ❌ 全部失败 | 批量端点更易触发 |

**应对策略**：
1. **美港股请求间加 3-5s 间隔**（`time.sleep(3)`），比失败重试省大量时间（3s vs 51s）
2. **优先级排序**：先请求最重要的标的，确保关键数据拿到后再请求次要标的
3. **失败后等 30-60s 再重试**，不要立即重试（立即重试大概率继续失败）
4. **批量持仓更新时**：A股/ETF（AkShare，无限制）可连续请求；美港股需间隔

## 代码示例

```python
import yfinance as yf, os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

# 方法1（推荐）：yf.download
tnx_data = yf.download('^TNX', period='1y', interval='1d')
tnx_close = tnx_data['Close']
if isinstance(tnx_close, pd.DataFrame):
    tnx_close = tnx_close.iloc[:, 0]  # 处理 MultiIndex

# 方法2（降级）：Ticker.history 短周期
tnx = yf.Ticker('^TNX')
tnx_hist = tnx.history(period='1mo')  # 短周期成功率更高
```
