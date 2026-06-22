# Portfolio Tracker 常见错误与陷阱

## 表行补丁规则 (CRITICAL)

When updating the holdings table via `patch`:
- **Start with `| `** (pipe + space) — NOT `||`
- **End with ` |`** (space + pipe)
- **Verify after EVERY patch**: Re-read the file and visually confirm no `||` patterns exist

## Cascading rounding

When updating multiple positions, do NOT patch one row at a time and recalculate 仓位% incrementally. Calculate ALL positions in one code block, then patch with consistent numbers.

## Cash data verification

When user reports cash figures (especially multi-currency), ALWAYS ask for explicit confirmation of EACH currency amount before calculating totals. Do NOT assume or infer cash from prior records — cash is the most error-prone field and a single mistake cascades through all 仓位% and 总资产.

**Common cash error patterns to avoid:**
- Misreading "A+B" as a single number (e.g., 38,500+6,800 → mistakenly using 83,800)
- Forgetting to convert HKD to CNY before adding to RMB cash
- Using stale cash figures from prior sessions

## Duplicate rows after patch

If a `patch` replaces text that overlaps with another row (especially the cash row), old rows may persist. Always re-read and clean up duplicates immediately.

## Data freshness

The `行情数据截至` timestamp must be updated on every edit, even for cash-only changes.

## Exchange rates

Use the rates recorded in `PORTFOLIO.md` header; do NOT guess current rates for 仓位 updates unless user explicitly provides them.

## QARP check numbering

When adding a new stock, renumber all subsequent entries in the QARP section.

## 美股盘中 vs 收盘标注

更新行情时若美股尚未收盘，`行情数据截至` 必须写明"美股盘中XX:XX ET，未收盘"，持仓表备注列写"盘中"而非"收盘"。

## 止损触发处理

QARP检查中设定了止损位的标的（如杠杆ETF），当价格跌破止损位时：
1. 纪律检查中标注为⚠️关注项而非✅达标
2. QARP检查中结论改为🔴已触发止损
3. 持仓表备注列标注🔴已跌破止损位
4. 输出末尾单独提醒用户决策，不自动执行止损

## inv-stock-data CLI timeout fallback

When `uv run scripts/cs_stock_info.py snapshot` times out, use QQ Finance API via browser as fallback:
`browser_navigate(url="http://qt.gtimg.cn/q=sh600660,hk00700,usTSM")` → `browser_console(expression="document.body.innerText")` → parse `v_xxx="..."` strings.

## Yahoo fundamentals empty for HK stocks

Yahoo snapshot may return `trailingPE=0`, `fiftyTwoWeekHigh=0`, `fiftyTwoWeekLow=0` for HK stocks. When this happens, use QQ Finance (`hk00700,hk07709,hk06809`) to get PE (field index 39) and 52wH/L (indices 42/43).

## 52-week data field positions

- **ETF 52-week data**: fields [67,68], NOT [47,48] (which are YTD-only). Verified 2026-06-14.
- **A股 52-week data**: ALSO at fields [67,68], NOT [47,48]. Verified 2026-06-15 宁波银行002142.
- **Rule**: For all ETF and A-shares, true 52-week high/low is at [67]/[68]. [47]/[48] is YTD-only.

## Yahoo 限流批量处理

When Yahoo triggers `YFRateLimitError` even for single snapshot calls, switch to QQ Finance batch query:
`http://qt.gtimg.cn/q=sh600660,sh588000,sh513010,hk00700,hk07709,usMSFT,usTSM`

## read_file 行号前缀导致 patch 失败

`hermes_tools.read_file` 返回的内容可能带有行号前缀，直接用 `patch` 工具匹配会失败。Workaround: 使用 Python 原生 `open()` 读写文件。
