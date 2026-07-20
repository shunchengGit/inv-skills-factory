## ADDED Requirements

### Requirement: market 模块职责与导出
`market.py` SHALL 导出 `parse_symbol(raw) → (code, market)`、`prefixed_sina(code, market) → str`、`to_yahoo_symbol(code, market) → str` 三个函数和 `_A_SHARE_PREFIXES`、`_BSE_PREFIXES` 两个常量。模块 SHALL 不依赖任何同目录其他模块（仅依赖 `re`）。

#### Scenario: parse_symbol 解析 A 股代码
- **WHEN** 传入 `"600519"`
- **THEN** 返回 `("600519", "a")`

#### Scenario: parse_symbol 解析港股代码
- **WHEN** 传入 `"00700"`
- **THEN** 返回 `("0700", "hk")`

#### Scenario: to_yahoo_symbol 港股转换
- **WHEN** 传入 `("0700", "hk")`
- **THEN** 返回 `"0700.HK"`

### Requirement: utils 模块职责与导出
`utils.py` SHALL 导出 `safe_call(fn, *args, default=None, **kwargs)`、`ret_n(df, n) → list[dict]`、`_fmt_pct(val) → str`、`_fmt_num(val, decimals) → str` 四个函数。模块 SHALL 不依赖同目录其他模块（仅依赖 `pandas`）。

#### Scenario: safe_call 处理异常
- **WHEN** 被调用函数抛出异常
- **THEN** 返回 `default` 值，不抛出异常

#### Scenario: ret_n 截取 DataFrame
- **WHEN** 传入 DataFrame 有 100 行，`n=5`
- **THEN** 返回前 5 行的 list[dict]

### Requirement: fetch_ashare 模块职责与导出
`fetch_ashare.py` SHALL 导出所有 A 股数据抓取函数和 A 股特有功能（公告、调研）。依赖 `utils.safe_call`、`utils.ret_n`、`market.prefixed_sina` 和 `akshare`。

#### Scenario: 导入 fetch_ashare 函数
- **WHEN** `commands.py` 需要 `fetch_ashare_snapshot` 和 `fetch_announcements`
- **THEN** 通过 `from fetch_ashare import fetch_ashare_snapshot, fetch_announcements` 导入

#### Scenario: fetch_announcements 属于 fetch_ashare
- **WHEN** 查找 `fetch_announcements` 函数位置
- **THEN** 在 `fetch_ashare.py` 中而非独立模块

### Requirement: fetch_etf 模块职责与导出
`fetch_etf.py` SHALL 导出 `fetch_etf_snapshot`、`fetch_etf_daily`、`fetch_etf_nav`、`_float_or_none`。依赖 `utils.safe_call`、`market.prefixed_sina` 和 `akshare`。

#### Scenario: 导入 ETF 函数
- **WHEN** `commands.py` 需要 ETF 快照数据
- **THEN** 通过 `from fetch_etf import fetch_etf_snapshot` 导入

### Requirement: fetch_yahoo 模块职责与导出
`fetch_yahoo.py` SHALL 导出所有港美股数据抓取函数（yfinance 主路径 + akshare/Sina 降级路径）。依赖 `utils.safe_call`、`akshare`、`yfinance`。

#### Scenario: 导入港美股函数
- **WHEN** `commands.py` 需要 Yahoo 快照数据
- **THEN** 通过 `from fetch_yahoo import fetch_yahoo_snapshot, fetch_yahoo_daily` 导入

### Requirement: render 模块职责与导出
`render.py` SHALL 导出 `RENDER_TABLE` dispatch 字典和 `print_text(payload) → str` 函数。所有 11 个 `_render_*` 函数作为内部实现，不强制导出但可通过 `RENDER_TABLE` 访问。依赖 `utils._fmt_pct`、`utils._fmt_num`。

#### Scenario: 渲染 A 股快照
- **WHEN** 调用 `print_text({"command": "snapshot_a", ...})`
- **THEN** 通过 `RENDER_TABLE["snapshot_a"]` 分发到 `_render_snapshot_a`

#### Scenario: 渲染独立于抓取
- **WHEN** render.py 被单独导入
- **THEN** 不依赖任何 fetch_* 或 commands 模块

## MODIFIED Requirements

### Requirement: commands 模块职责与导出
`commands.py` SHALL 导出所有公开 `cmd_*` 子命令函数和所需降级函数，并通过契约模块构造 `investment-data-contracts` v1 envelope。模块 SHALL 依赖 `fetch_*`、`market`、`utils` 和 `_shared.proxy`，但 SHALL NOT 将供应商原始 payload 直接暴露给消费者。`cmd_daily` SHALL 接受显式历史窗口参数，`cmd_all` SHALL 仅聚合 snapshot、financial 和 financials 并保留各组件状态。

#### Scenario: cmd_snapshot 跨模块调用
- **WHEN** `cmd_snapshot("600519", "a")` 执行
- **THEN** 调用 A 股抓取模块并返回 schema v1 标准 snapshot envelope，而不是供应商原始键集合

#### Scenario: 降级回退路径
- **WHEN** Yahoo Finance 返回空数据且港股降级源成功
- **THEN** `cmd_snapshot_yahoo` 使用降级数据生成 partial envelope，记录主来源失败和 fallback 成功，不得因 DataFrame 布尔判断崩溃

#### Scenario: 日线窗口透传
- **WHEN** `cmd_daily` 收到 `period="5y"` 且未指定 limit
- **THEN** 抓取层接收长期窗口请求，响应保留完整可用序列和实际 window 元数据，不得固定截取 20 条

#### Scenario: all 组件范围
- **WHEN** `cmd_all` 执行
- **THEN** 仅聚合 snapshot、financial、financials 三个有独立状态的组件，不隐式承诺 daily、announcements 或 relations

### Requirement: 入口文件职责
`cs_stock_info.py` SHALL 仅包含 CLI 参数、市场级代理管理、命令 dispatch、统一退出码和渲染入口，不包含数据抓取或领域计算。CLI SHALL 支持 daily 的历史窗口参数，并按 envelope 状态返回可判定退出结果：`ok` 为成功，`partial` 保留可消费输出并显式标识降级，`failed` 返回非零退出码。

#### Scenario: 入口文件导入所有模块
- **WHEN** `cs_stock_info.py` 被执行
- **THEN** 从 commands、render、market 和契约模块导入公开接口，且入口本身不实现抓取逻辑

#### Scenario: 入口文件处理代理
- **WHEN** 市场为港股或美股
- **THEN** 按共享代理策略配置请求环境，并把代理不可用记录为结构化来源或 gap

#### Scenario: 命令行输出采用新契约
- **WHEN** 运行 `python cs_stock_info.py snapshot 600519 --output json`
- **THEN** 输出 `investment-data-contracts` v1 envelope；旧 JSON shape 不再作为公共兼容承诺

#### Scenario: failed 返回非零
- **WHEN** 命令返回 `status: "failed"`
- **THEN** CLI 输出结构化失败 envelope 并以非零退出码结束
