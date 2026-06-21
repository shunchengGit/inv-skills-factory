# QQ Finance 行情更新 — 字段索引与脚本

## 快速命令

```bash
# 一键更新持仓（直接写回 PORTFOLIO.md）
python3 ~/.hermes/skills/invest/inv-portfolio-tracker/scripts/qq_update_portfolio.py --write

# 预览（不写文件）
python3 ~/.hermes/skills/invest/inv-portfolio-tracker/scripts/qq_update_portfolio.py

# 检查数据可用性
python3 ~/.hermes/skills/invest/inv-portfolio-tracker/scripts/qq_update_portfolio.py --check

# JSON 格式输出
python3 ~/.hermes/skills/invest/inv-portfolio-tracker/scripts/qq_update_portfolio.py --json
```

## API 请求格式

```
https://qt.gtimg.cn/q=<code1>,<code2>,...
```

- A股：`sh600519`（上证）/ `sz000001`（深证）
- ETF：`sh510050` / `sz159915`
- 港股：`hk00700`（5位代码）
- 美股：`usAAPL`

响应编码：GB2312。格式：`v_前缀代码="字段1~字段2~..."`，以 `~` 分隔。

## 字段索引（按市场分类，0-based）

### A股（88字段，market=1）

| 索引 | 字段 | 说明 |
|------|------|------|
| 3 | 当前价 | 收盘/最新价 |
| 4 | 昨收 | 前收盘 |
| 32 | 涨跌幅% | 百分比 |
| 33 | 当日高 | — |
| 34 | 当日低 | — |
| 47 | 年内高 | ⚠️ 非52周，是年内最高 |
| 48 | 年内低 | ⚠️ 非52周，是年内最低 |
| **67** | **52周高** | **✅ 真52周高（2026-06-15 实测）** |
| **68** | **52周低** | **✅ 真52周低（2026-06-15 实测）** |
| 52 | PE(TTM) | 滚动市盈率 |
| 53 | PE(静) | 静态市盈率 |

### 港股（78字段，market=100）

| 索引 | 字段 | 说明 |
|------|------|------|
| 3 | 当前价 | 收盘/最新价 |
| 4 | 昨收 | 前收盘 |
| 32 | 涨跌幅% | 百分比 |
| 33 | 当日高 | — |
| 34 | 当日低 | — |
| 39 | PE(TTM) | 滚动市盈率 |
| 48 | 52周高 | ✅ 标准52周 |
| 49 | 52周低 | ✅ 标准52周 |

### 美股（71字段，market=200）

| 索引 | 字段 | 说明 |
|------|------|------|
| 3 | 当前价 | 实时价 |
| 4 | 昨收 | 前收盘 |
| 32 | 涨跌幅% | 百分比 |
| 33 | 当日高 | — |
| 34 | 当日低 | — |
| 39 | PE(TTM) | 滚动市盈率 |
| 48 | 52周高 | ✅ 标准52周 |
| 49 | 52周低 | ✅ 标准52周 |

## 52周位置计算

```python
pos = (price - low_52w) / (high_52w - low_52w) * 100
```

## 市值计算

```python
# 汇率 (from PORTFOLIO.md header)
usd_cny = 6.77
hkd_cny = 0.863

# A股: shares * price / 10000
# 港股: shares * price * hkd_cny / 10000
# 美股: shares * price * usd_cny / 10000
```

## 注意事项

- **A股52周数据**：字段 `[67]`/`[68]` 才是真52周高/低，`[47]`/`[48]` 只是年内高/低。此前文档和脚本均误用 `[47]`/`[48]` 作为52周数据（导致513010等ETF 52w位计算错误）。
- **ETF 52周数据**：同样使用 `[67]`/`[68]`，不是 `[47]`/`[48]`。
- ETF 无 PE 数据，标记为 `—`
- 港股需5位数代码（如 `hk00700` 而非 `hk0700`）
- 美股代码去掉交易所后缀（如 `usTSM` 而非 `usTSM.N`）
- 详细字段参考见 `qq-finance-field-reference.md`
