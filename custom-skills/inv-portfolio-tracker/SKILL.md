---
name: inv-portfolio-tracker
description: 管理投资组合持仓主数据，更新持仓/现金，支持 T1-T4 自动化日报/周报流程。用于跟踪持仓变化、生成投资组合报告时
category: invest
tags: [portfolio, holdings, tracking, daily-report, cron]
version: 1.2.0
trigger:
  - 持仓管理
  - 投资组合
  - 调仓
  - 持仓日报
  - portfolio
---

# Portfolio Tracker

## Purpose

Manage the user's investment portfolio master data and understand the automated daily/weekly reporting workflow.

## When to Load This Skill

**Load this skill FIRST when the user asks to:**
- Update portfolio holdings / 更新持仓 / 更新仓位
- Change share counts / 调整股数 / 增减持
- Update cash balances / 更新现金 / 现金变动
- Add or remove stocks from portfolio / 新增或删除标的
- Review portfolio constraints / 检查纪律 / 检查仓位

**Always load `inv-stock-data` alongside this skill for price fetching.**
- Portfolio updates require current prices → use `inv-stock-data` snapshot
- Do NOT attempt to update PORTFOLIO.md without loading this skill first

## Master Data Source

- **File**: `~/.hermes/memories/PORTFOLIO.md`
- **Role**: Single source of truth for all holdings, share counts, cash balances, and 仓位%
- **Do NOT** maintain portfolio data elsewhere without updating this file
- **Always read this file first** before answering portfolio-related questions

## File Structure

- `当前持仓`: Table with columns — 标的, 代码, 市场, 板块, 股数, 价格, 币种, 市值(万CNY), 仓位, PE, 52w位, 核心风险, 备注
- `调仓记录`: Chronological log of all trades and cash movements
- `纪律检查`: Portfolio constraint checks (single stock limit, cash ≥2%, sector ≤40%). **Constraint values are user-defined in USER.md — always read latest USER.md rather than hardcoding limits here.**
- `数据缺口说明`: Known data gaps and workarounds

## 输出持仓概览格式（给用户看时必须遵守）

当用户要求"输出持仓""查看持仓""我的持仓"时，输出表格**必须包含股数列**：

```
| 标的 | 代码 | 股数 | 价格 | 市值(万) | 仓位 | PE | 52w位 | 备注 |
```

- **股数是必显字段**，不可省略。用户需要看到每只标的持有多少股。
- 价格保留原始币种标记（如 HK$421.4、$434.99、¥48.01）
- 市值统一为万CNY
- 备注列可精简（涨跌幅 + 风险标记，如 "🔴透支""🟡高位"）
- 表格下方跟 纪律检查 + 关键关注，用简洁的关键点列出

## Automated Reporting Workflow (T1–T4)

Defined in `~/.hermes/memories/CRONTASK.md`:

| Task | Time | Cron | Output |
|------|------|------|--------|
| T1 持仓晨报 | 工作日 08:30 | `30 8 * * 1-5` | 当日 `YYYY-MM-DD.md` + 飞书 |
| T2 日常回顾 | 每日 22:30 | `30 22 * * *` | 当日 `YYYY-MM-DD.md` + 飞书 |
| T3 周中回顾 | 周三 21:00 | `0 21 * * 3` | 当日主记录 + 飞书 |
| T4 周复盘 | 周日 21:00 | `0 21 * * 0` | `YYYY-MM-DD-weekly-review.md` + 飞书 |

- **Skill used**: `inv-stock-data` (snapshot/price/PE data) + `inv-portfolio-tracker` (portfolio structure & workflow)
- **Key rule**: All `inv-stock-data snapshot` calls must be parallel via `&` and `wait`
- **Delivery**: Via cron delivery to Feishu; do NOT manually call message/send

## Updating Portfolio Data

When the user reports a cash change or trade:

1. **Load `inv-stock-data`** for current prices (if price-dependent)
2. **Read** `PORTFOLIO.md` first
3. **Calculate all changes in one code block** — compute every holding's new 市值, 仓位%, total assets, cash%, sector concentrations. This avoids cascading rounding errors from incremental patches.
   - **CRITICAL**: Before calculating, verify cash amounts with the user if there's ANY ambiguity. Cash errors propagate to ALL position percentages.
4. **Apply all patches in sequence**: holdings table → cash → 调仓记录 → 纪律检查 → QARP check → 数据缺口
5. **Re-read the file** after patching to catch duplicates or formatting breaks (especially `||` from table row mismatches)
6. **Add QARP check entry** for any new stock (买入理由/逻辑检查/打脸条件/估值检查/结论)

### Table Row Patching Rules (CRITICAL)

When updating the holdings table via `patch`:
- **Start with `| `** (pipe + space) — NOT `||`
- **End with ` |`** (space + pipe)
- **Verify after EVERY patch**: Re-read the file and visually confirm no `||` patterns exist
- **Example of CORRECT replacement**:
  ```
  | 微软 | MSFT | US | 软件与服务 | **70** | **$386.66** | USD | **18.32** | **18.3%** | ...
  ```
- **Example of WRONG replacement** (note the `||` at start):
  ```
  || 微软 | MSFT | US | 软件与服务 | **70** | **$386.66** | USD | **18.32** | **18.3%** | ...
  ```

### Cash-only changes

Adding cash without changing stock positions **dilutes all stock 仓位% proportionally**. Recalculate every position's percentage against the new total asset base.

### Cash verification protocol

Cash is the single most error-prone field in portfolio updates. A miscalculation here cascades through **all** downstream numbers (total assets, every position's 仓位%, industry concentrations, discipline checks).

**When user reports cash changes:**
1. **Explicitly confirm EACH currency amount** — do NOT infer from prior records or assume you understand shorthand like "38,500+6,800" means 45,300 total.
2. **Repeat back the confirmed amounts** before calculating: "确认：港币现金 45,300 HKD，人民币现金 20,000 CNY，对吗？"
3. **Only then** compute total cash in CNY and recalculate all 仓位%
4. **Verify the math**: total_cash = (hkd_amount * hkd_cny_rate) + rmb_amount. Round to 2 decimal places.

**Common cash error patterns to avoid:**
- Misreading "A+B" as a single number (e.g., 38,500+6,800 → mistakenly using 83,800)
- Forgetting to convert HKD to CNY before adding to RMB cash
- Using stale cash figures from prior sessions when user has already made changes

## Batch Update Workflow (Multiple Changes at Once)

When the user reports multiple changes simultaneously (e.g., new stock + share increase + cash changes):

1. **Read** `PORTFOLIO.md` first
2. **Fetch prices** for any new/changed tickers via `inv-stock-data`
3. **Calculate all changes in one code block** — compute every holding's new 市值, 仓位%, total assets, cash%, sector concentrations. This avoids cascading rounding errors from incremental patches.
   - **CRITICAL**: Before calculating, verify cash amounts with the user if there's ANY ambiguity. Cash errors propagate to ALL position percentages.
4. **Apply all patches in sequence**: holdings table → cash → 调仓记录 → 纪律检查 → QARP check → 数据缺口
5. **Re-read the file** after patching to catch duplicates or formatting breaks (especially `||` from table row mismatches)
6. **Add QARP check entry** for any new stock (买入理由/逻辑检查/打脸条件/估值检查/结论)

### Key Calculations (Code Block Pattern)

Use `execute_code` with this template:

```python
# 汇率 (from PORTFOLIO.md header)
usd_cny = 6.77
hkd_cny = 0.863

# Prices & shares — update for current tickers
# ... (set all prices and share counts)

# 市值计算（万CNY）
# A股: shares * price_cny / 10000
# 港股: shares * price_hkd * hkd_cny / 10000
# 美股: shares * price_usd * usd_cny / 10000

# 现金
hkd_cash = xxx * hkd_cny / 10000
rmb_cash = xxx / 10000
total_cash = hkd_cash + rmb_cash

# 总资产 & 仓位%
total = sum(all_mv) + total_cash
for each holding: weight = mv / total * 100

# 行业集中度
semi = sum(semiconductor holdings mv)
internet = sum(internet holdings mv)
auto = sum(auto holdings mv)

# 纪律检查
# - 单只上限: read from USER.md (currently ≤40%)
# - 现金 >= 2% (理想 5-10%)
# - 行业 <= 40%
```

### New Stock Entry Template

When adding a new stock to the holdings table and QARP check:

- Holdings row: fill all columns including PE, 52w位, 核心风险, 备注
- QARP check: 买入理由 / 逻辑检查 / 打脸条件 / 估值检查 / 组合检查 / 结论
- If PE > 100x or stock is speculative, mark as 🔴卫星仓位 and set a stop-loss level

## Quick Update Workflow (行情刷新，无调仓)

当用户说"更新持仓/行情"且无调仓时，直接运行内置脚本：

```bash
python3 ~/.hermes/skills/inv-skills/inv-portfolio-tracker/scripts/qq_update_portfolio.py --write
```

纯 QQ Finance 方案，~0.4秒完成，覆盖 A股/港股/美股/ETF。脚本自动完成：拉取行情 → 计算市值/仓位/行业集中度 → 更新 PORTFOLIO.md 的「当前持仓」「纪律检查」「数据缺口说明」三个 section。

字段索引详见 `references/qq-finance-batch-update.md`。

## Manual Trade Update Workflow (有调仓)

When the user reports a trade (buy/sell) or cash change:

1. **Load `inv-stock-data`** for current prices
2. **Read** `PORTFOLIO.md`
3. **Calculate in one code block**: new market values, position weights, total assets, cash%, sector concentrations
4. **Apply patches in sequence**: holdings table → cash → 调仓记录 → 纪律检查 → QARP check
5. **Re-read and verify**: Check for `||`, duplicate rows, broken tables
6. **Update 数据缺口说明** with new price data

### Key Calculations (Code Block Pattern)

Use `execute_code` with this template:
  - **Replacement verification**: After any table patch, immediately re-read the affected lines and visually confirm no `||` patterns exist.
  - **Duplicate rows after patch**: If a `patch` replaces text that overlaps with another row (especially the cash row), old rows may persist. Always re-read and clean up duplicates.

> 更完整的常见错误、字段位置、限流降级等踩坑记录见 `references/common-pitfalls.md`。
