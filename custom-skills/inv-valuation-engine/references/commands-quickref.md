# 估值脚本快速命令参考

路径中 `{baseDir}` = 本技能目录，`{stockDir}` = `{baseDir}/../inv-stock-data`，`{researchDir}` = `{baseDir}/../inv-knowledge-curator`。

```bash
# ===== 代理 =====
# 美股/港股走 Yahoo 需代理：inv-stock-data 先读 HTTPS_PROXY/HTTP_PROXY，再探测本地 Clash 端口；
# 仍失败时加 --proxy <地址>。A 股/ETF 先 unset 代理。规则以 inv-stock-data/SKILL.md 为准。

# ===== 首选：获取三个核心组件 =====
# v1 all.data.components 固定为 snapshot + financial + financials，不含日线/公告/关联
uv run {stockDir}/scripts/cs_stock_info.py all AAPL --output json
uv run {stockDir}/scripts/cs_stock_info.py all 600519 --output json
# 长期指标必须显式请求历史窗口；实际覆盖见 window
uv run {stockDir}/scripts/cs_stock_info.py daily AAPL --period 5y --output json

# ===== 具体命令 =====
# 1) 抓取估值快照（文本）
uv run {baseDir}/scripts/valuation_snapshot.py AAPL

# 2) 抓取估值快照（JSON，便于后续自动化）
uv run {baseDir}/scripts/valuation_snapshot.py 600519 --output json
uv run {baseDir}/scripts/valuation_snapshot.py 0700.HK --output json

# 可选背景仅 snapshot CLI 支持，默认均不抓取；实际覆盖仍需检查 window
# report/compare 使用这些背景时，先保存 snapshot --output json，再离线读取
uv run {baseDir}/scripts/valuation_snapshot.py AAPL --history-period 5y --output json
uv run {baseDir}/scripts/valuation_snapshot.py 600519 --include-announcements --include-relations --output json

# 3) 输出诊断报告；没有核验主估值时不自动评级
uv run {baseDir}/scripts/valuation_report.py 600660

# 离线演示（仅测试数据，不是市场事实）
uv run {baseDir}/scripts/valuation_report.py TEST --snapshot-input {baseDir}/examples/offline-snapshot.json --primary-input {baseDir}/examples/reviewed-primary.json --output json

# 4) 指定公司类型，避免自动识别偏差
uv run {baseDir}/scripts/valuation_report.py 002475 --company-type tech

# 5) 同行诊断并列，不按五档/PE自动排序
# 核验主估值比较：--input bundle.json；snapshots 与 primary_inputs 均以原始代码为键
# bundle = {"snapshots": {"TEST": <Snapshot对象>}, "primary_inputs": {"TEST": <核验主估值对象>}}
# 省略 snapshots 可在线取核心数据；离线须提供所有请求代码的完整 Snapshot（不是数据层 v1 envelope）
# 键及 Snapshot.symbol 必须与命令原始代码完全一致；缺键/不匹配返回2，不会偷偷联网补齐
# primary_inputs 可缺省；缺主估值则该行仅诊断，conclusion 可省略/null，不排序、不输出动作
uv run {baseDir}/scripts/valuation_compare.py TEST --input bundle.json --output markdown

# 默认只展示诊断
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
