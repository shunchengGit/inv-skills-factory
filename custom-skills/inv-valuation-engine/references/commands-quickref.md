# 估值脚本快速命令参考

路径中 `{baseDir}` = 本技能目录，`{stockDir}` = `{baseDir}/../inv-stock-data`，`{researchDir}` = `{baseDir}/../inv-knowledge-curator`。

```bash
# ===== 代理设置说明 =====
# 美股/港股数据依赖 Yahoo Finance，国内网络需要代理
# 通过环境变量设置代理（inv-stock-data CLI 自动读取）
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# ===== 首选：一次获取全量数据 =====
# cs_stock_all 合并 snapshot + financial + financials，减少跨进程调用和限流风险
uv run {stockDir}/scripts/cs_stock_info.py all AAPL --output json
uv run {stockDir}/scripts/cs_stock_info.py all 600519 --output json

# ===== 具体命令 =====
# 1) 抓取估值快照（文本）
uv run {baseDir}/scripts/valuation_snapshot.py AAPL

# 2) 抓取估值快照（JSON，便于后续自动化）
uv run {baseDir}/scripts/valuation_snapshot.py 600519 --output json
uv run {baseDir}/scripts/valuation_snapshot.py 0700.HK --output json

# 3) 直接输出五档估值报告
uv run {baseDir}/scripts/valuation_report.py 600660

# 4) 指定公司类型，避免自动识别偏差
uv run {baseDir}/scripts/valuation_report.py 002475 --company-type tech

# 5) 同行相对估值比较
uv run {baseDir}/scripts/valuation_compare.py 002475 601138 002241 --company-type tech

# 6) 输出 Markdown 表格版，便于直接阅读
uv run {baseDir}/scripts/valuation_report.py AAPL --output markdown

# 7) 手动估值计算（当自动化脚本失败时降级）
uv run {baseDir}/scripts/valuation_manual_compute.py \
  --price 98.78 --shares 14.82 --fx 7.15 \
  --ni-gaap 978.43 --ni-nongaap 1073 --eps-fy1 82.08 \
  --equity 4133.85 --equity-prev 3133.13 \
  --revenue 4318.46 --gross-profit 2430.44 --op-income 931.02 \
  --fcf 1057.94 --cash 1089 --investments 3134 --debt 54 \
  --scenario-profit "悲观,1127,8|基准,1300,10|乐观,1500,12"
```
