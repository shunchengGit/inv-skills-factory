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

### Requirement: commands 模块职责与导出
`commands.py` SHALL 导出所有 `cmd_*` 子命令函数（8 个）和 3 个 `_fallback_*` 降级函数。依赖所有 `fetch_*` 模块、`market`、`utils`、`_shared.proxy`。

#### Scenario: cmd_snapshot 跨模块调用
- **WHEN** `cmd_snapshot("600519", "a")` 执行
- **THEN** 调用 `fetch_ashare.fetch_ashare_snapshot`、`fetch_ashare.fetch_announcements` 等

#### Scenario: 降级回退路径
- **WHEN** Yahoo Finance 返回空数据
- **THEN** `cmd_snapshot_yahoo` 调用 `_fallback_hk_sina` 或 `_fallback_hk_akshare`

### Requirement: render 模块职责与导出
`render.py` SHALL 导出 `RENDER_TABLE` dispatch 字典和 `print_text(payload) → str` 函数。所有 11 个 `_render_*` 函数作为内部实现，不强制导出但可通过 `RENDER_TABLE` 访问。依赖 `utils._fmt_pct`、`utils._fmt_num`。

#### Scenario: 渲染 A 股快照
- **WHEN** 调用 `print_text({"command": "snapshot_a", ...})`
- **THEN** 通过 `RENDER_TABLE["snapshot_a"]` 分发到 `_render_snapshot_a`

#### Scenario: 渲染独立于抓取
- **WHEN** render.py 被单独导入
- **THEN** 不依赖任何 fetch_* 或 commands 模块

### Requirement: 入口文件职责
`cs_stock_info.py` SHALL 仅包含 CLI 入口逻辑（argparse 定义 + 代理管理 + main dispatch），约 87 行。不包含任何业务逻辑（数据抓取、命令编排、渲染）。

#### Scenario: 入口文件导入所有模块
- **WHEN** `cs_stock_info.py` 被执行
- **THEN** 通过 `from commands import cmd_*`、`from render import RENDER_TABLE`、`from market import parse_symbol` 导入

#### Scenario: 入口文件处理代理
- **WHEN** 市场为港股或美股
- **THEN** 调用 `_shared.proxy.setup_proxy_env()`，然后 `clear_proxy_env()` 为 akshare 清除

#### Scenario: 命令行接口不变
- **WHEN** 运行 `python cs_stock_info.py snapshot 600519 --output json`
- **THEN** 输出与重构前完全一致的 JSON 结构