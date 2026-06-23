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

增量信息获取优先级：
1. yfinance info + financials + history（已覆盖 90% 需求）
2. 本地券商研报 PDF（inv-knowledge-curator）
3. Agent WebFetch / browser_navigate 直抓特定页面（仅当上述不够时）
4. web_search（最后手段，预期低效）

**何时触发搜索补充**（任一满足即可）：
- 本地研报时效性 > 1 个月，需最新行业数据
- 政策/地缘风险：关税、制裁、监管变化等实时事件
- 管理层/公司动态：股东会发言、重大公告、媒体报道
- 用户明确要求搜索补充或二次验证
- 持仓检查需要交叉验证：官方财报 vs 脚本数据、分析师共识 vs 自建估值

详细的工具选择规则、搜索流程、数据源映射和实践案例见 `web-search-supplement.md`。
