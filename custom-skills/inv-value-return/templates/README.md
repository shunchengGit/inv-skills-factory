# inv-value-return 输入契约

标准库、离线、每股单一币种的确定性敏感性计算器。只读取 `--input` 指定的 JSON 文件并输出 stdout；不联网，不读取 USER、持仓或判断台账，不拟合参数，不自动给概率或买卖建议。Agent 在外部做行业适用口径、来源核验、用户收益目标及组合限制研究；本程序不内置个人目标或现金门禁。

```sh
python3 -B custom-skills/inv-value-return/scripts/forecast_returns.py --input custom-skills/inv-value-return/templates/example.json --output json
python3 -B custom-skills/inv-value-return/scripts/forecast_returns.py --input custom-skills/inv-value-return/templates/example.json --output text
python3 -B -m unittest discover -s custom-skills/inv-value-return/tests -v
```

## 字段

| 字段 | 约定 |
|---|---|
| `years` | 必填，正整数；每年一条现金流，不支持分数年 |
| `current_price` | 必填，有限数值且 > 0；每股买入报价，不含买费 |
| `currency` | 必填，非空字符串；所有价格、股息均已转换为该币种及同一股份/ADR单位 |
| `as_of` | 必填，有效 `YYYY-MM-DD`；输入假设日期，不表示程序已核行情 |
| `buy_fee_rate` | 可省略，显式默认 0；有限数值 [0,1]，初始成本=报价×(1+买费) |
| `exit_fee_rate` | 可省略，显式默认 0；有限数值 [0,1]，只从终值卖价扣除 |
| `dividend_tax_rate` | 可省略，显式默认 0；有限数值 [0,1]，逐年股息扣税 |
| `pessimistic_floor_rate` | 可省略或 null；若给出必须有限且 > -1。本次解析的悲观底线（可为 −5% 等任意数值，或已核同币种同期限税后无风险率），程序不核来源 |
| `pessimistic_floor_basis` | 可省略或 null；字符串，说明底线来源/作用域，例如“本次用户指示”“USER.md 回报目标”“某日某期限国债税后”。旧字段 `annual_rf_after_tax` 已移除，传入即报错 |
| `target_cagr_range` | 必填 `[低目标,高目标]`，有限、均 > -1，低≤高；小数比例，不读取用户配置或内置15–20% |
| `scenarios` | 必填，三或四项，每项对象 |
| `scenarios[].name` | 必填，`pessimistic`、`base`、`optimistic` 各一次；可选再加一次 `no_rerating`（不重估对照：终值按当前同口径倍数滚动，非第四种经济情景）。保留输入顺序 |
| `scenarios[].terminal_price` | 必填，有限且≥0，最后一年末每股退出报价，卖费前 |
| `scenarios[].dividends` | 必填，长度恰好为 years 的数组；各项有限且≥0，为每年末每股税前股息；允许全0 |
| `scenarios[].terminal_bridge` | 可选 JSON 对象；原样输出但不验证经济逻辑或来源；例如 `method`、`source`、`earnings`、`multiple`、`unit_conversion`。不强制PE，不自动执行盈利×倍数或汇率转换 |

布尔值不能充当数值；所有层级的 NaN/Infinity 均拒绝。非法结构、空情景、缺名字、负股息、长度不符等返回失败。额外元数据可保留在输入供人阅读，不作为计算参数；未知字段不会替代必填参数。

## 计算及输出

- `initial_cost = current_price × (1 + buy_fee_rate)`，t=0 一次支出。
- `annual_net_cash_flows[t] = dividends[t] × (1-dividend_tax_rate)`；末年再加 `terminal_price × (1-exit_fee_rate)`。
- `annual_irr` 通过求根满足 `initial_cost = Σ cash[t]/(1+r)^t`。每年末收股息，最后年末卖出；不是把所有现金统一移至期末，也不是按日历天数计算的 XIRR。允许负收益；完全无回款时明确为 -1（-100%边界）。
- `terminal_collected_cagr_non_irr = (Σ cash / initial_cost)^(1/years)-1`；假设股息不再投资、无利息地留存至期末。这是**期末归集 CAGR，不是 IRR**。
- `max_buy_prices_for_target` 顺序对应输入的低/高目标，逐个计算 `Σ cash[t]/(1+target)^t / (1+buy_fee_rate)`。它是给定情景达到目标的最高当前报价，不是估值认证或买入建议。
- `target_buffers` 顺序对应低/高目标，为 `annual_irr − 目标`（小数，text 显示为 pp），即目标回报余量，不是估值折让。
- `target_comparison` 为 `below_range` / `within_range` / `above_range`；边界含等号，求根舍入比较采用 `1e-12` 相对/绝对容差。
- `pessimistic_floor` 对 **pessimistic** 情景输出 `rate`/`basis`/`irr_buffer`/`max_buy_price`/`pass`：`max_buy_price` 以底线率按同一贴现公式计算，`pass` 为悲观 IRR≥底线（含容差，等价于报价≤上限）。缺底线时数值字段为 null，text 明确 `not certified`。这里仅认证算术比较，不认证外部研究或底线来源。
- `fees_and_tax` 输出实际使用的三个比例（包括默认0）。`notes` 始终标注**税费未核**，即使输入给出比例也不声称已核验。不额外计算资本利得税；需要时由外部准备一致的终值假设并说明，避免重复扣税。
- `terminal_bridge` 用于输出来源及盈利×倍数、币种、ADR比例等换算说明；金融、亏损、资产型公司可直接提供适当研究口径推导的终值，无须PE。FX后的终值与每年股息必须由外部先准备为同一输出币种。
- CLI 成功 exit 0，JSON 或 text 输出；非法输入/文件读取失败 exit 2，stderr 报错、stdout 空。程序使用 Python 浮点，极端超出浮点范围的输入运算可失败，不应把报错当成有效预测。

## 示例性质

`example.json` 是 **illustrative / 非市场数据** 的 TSM 纯敏感性示例，价格412.61、3年、终值370.588/625/916.667、股息3/4/5。假设日期也只是示例标签；不声称是该日实际行情或已核预测。15–20%只在示例输入中显式给出，不是程序默认或用户目标认证。示例不设悲观底线，`pessimistic_floor_rate` 保留 null，不认证保守通过；不得捏造数据来源。
