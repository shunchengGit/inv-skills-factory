# 数据源与降级

## 跨市场支持

- **A股**：`600519` / `000001` / `300750`
- **港股**：`0700.HK` / `1810.HK`
- **美股**：`AAPL` / `MSFT` / `NVDA`

## 脚本优先级

1. 用户给了代码但没给完整数据：先运行 `{valuationDir}/scripts/valuation_snapshot.py`
2. 用户要直接结论：优先运行 `{valuationDir}/scripts/valuation_report.py`
3. 用户要比较几家公司：优先运行 `{valuationDir}/scripts/valuation_compare.py`
4. **脚本超时降级**：若 `uv run` 因依赖下载超时，降级为 inv-stock-data `financials` 子命令获取财务三表数据，再按估值框架手动计算。不得因脚本超时而放弃数据获取
5. 脚本返回后，先检查 `data_gaps`，明确缺口和置信度影响
6. 定量判断按 `inv-valuation-engine` 的 `references/scoring-rules.md` 执行，定性解释再用 `inv-valuation-engine` 的 `references/master-frameworks.md`
7. 如果用户已给高质量最新数据，可跳过抓取直评估，但需标注数据时点

## 美股/港股 data_gaps 降级

当 `valuation_snapshot.py` 对美股/港股返回超过5项 data_gaps 时，按 `inv-valuation-engine` 的 `references/us-hk-data-workaround.md` 执行手动补全，含 inv-stock-data financials 子命令、`valuation_manual_compute.py` 两条补全链路。

**港股 snapshot 全空降级**（实测 0700.HK 返回 41 项 data_gaps，所有字段 null）：当 snapshot 对港股返回全部 null 时，跳过 snapshot 降级流程，直接用 inv-stock-data `financials` 子命令获取财务三表数据：
1. `inv-stock-data financials 0700.HK --output json` 获取利润表/资产负债表/现金流量表
2. 结合 `inv-stock-data snapshot 0700.HK` 中可用的估值指标（若 info 端点部分可用）
3. 按 `inv-valuation-engine` 的 `references/us-hk-data-workaround.md` 中的字段映射表补全

## 搜索与增量信息策略

搜索补充的触发条件、工具选择、数据源映射和实践案例见 `web-search-supplement.md`（本节仅讲数据源降级，搜索增量归该文件）。对美股/港股字段缺口，优先直抓 Yahoo Finance、MacroTrends 等已验证白名单；不要默认先走 `web_search`。
