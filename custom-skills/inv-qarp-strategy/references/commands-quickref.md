# QARP 估值脚本快速命令

估值脚本统一走 `inv-valuation-engine`，路径中 `{valuationDir}` = `{baseDir}/../inv-valuation-engine`，`{researchDir}` = `{baseDir}/../inv-knowledge-curator`。

```bash
# 代理设置（美股/港股需要）
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# 1) 抓取估值快照（文本）
uv run {valuationDir}/scripts/valuation_snapshot.py AAPL

# 2) 抓取估值快照（JSON）
uv run {valuationDir}/scripts/valuation_snapshot.py 600519 --output json
uv run {valuationDir}/scripts/valuation_snapshot.py 0700.HK --output json

# 3) 直接输出五档估值报告
uv run {valuationDir}/scripts/valuation_report.py 600660

# 4) 指定公司类型
uv run {valuationDir}/scripts/valuation_report.py 002475 --company-type tech

# 5) 同行相对估值比较
uv run {valuationDir}/scripts/valuation_compare.py 002475 601138 002241 --company-type tech

# 6) Markdown 表格版
uv run {valuationDir}/scripts/valuation_report.py AAPL --output markdown

# 7) 手动估值计算（脚本失败时降级）
uv run {valuationDir}/scripts/valuation_manual_compute.py \
  --price 98.78 --shares 14.82 --fx 7.15 \
  --ni-gaap 978.43 --ni-nongaap 1073 --eps-fy1 82.08 \
  --equity 4133.85 --equity-prev 3133.13 \
  --revenue 4318.46 --gross-profit 2430.44 --op-income 931.02 \
  --fcf 1057.94 --cash 1089 --investments 3134 --debt 54 \
  --scenario-profit "悲观,1127,8|基准,1300,10|乐观,1500,12"
```
