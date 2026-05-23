## Why

cs-stock 的 `cs_stock_info.py` 是 1383 行单文件，包含 8 个子命令、6 组数据抓取函数、11 个渲染函数和 CLI 入口。任何修改（新增子命令、修复抓取 bug、调整输出格式）都需在这单一文件中定位和修改，维护成本高且容易引入交叉影响。

## What Changes

- 将 `cs_stock_info.py` 拆分为 7 个模块文件 + 1 个入口文件：
  - `market.py` — 市场识别与符号解析（parse_symbol, prefixed_sina, to_yahoo_symbol）
  - `utils.py` — 通用工具（safe_call, ret_n, _fmt_pct, _fmt_num）
  - `fetch_ashare.py` — A 股数据抓取 + 公告/调研（合并原 fetch_misc 26 行）
  - `fetch_etf.py` — ETF 数据抓取
  - `fetch_yahoo.py` — 港美股数据抓取（yfinance + akshare/Sina 降级）
  - `commands.py` — 8 个子命令编排 + 3 个降级回退
  - `render.py` — 11 个渲染函数 + dispatch 表
  - `cs_stock_info.py` — 仅保留 CLI 入口（argparse + 代理策略 + dispatch，约 87 行）
- 所有模块通过 `sys.path.insert(0, 同级目录)` 相互导入，与现有 scripts/ 风格一致
- **非 BREAKING**：命令行参数接口、JSON 输出结构、SKILL.md 呇令列表均不变

## Capabilities

### New Capabilities
- `cs-stock-modular`: cs-stock 脚本模块化拆分——定义模块边界、导入方式、每个模块的职责和导出函数

### Modified Capabilities
- `shared-proxy`: cs-stock 入口文件的代理调用从内联 import 改为从 `_shared` 和 `market/utils` 组合导入（仅实现细节变化，spec 行为不变）

## Impact

- **代码**: `cs-stock/scripts/` 新增 7 个 .py 文件，原 `cs_stock_info.py` 从 1383 行缩减为约 87 行入口
- **依赖**: 其他技能（value-investing-valuation、porter-five-forces-analysis、quality-growth-qarp）通过 CLI 子进程调用 `cs_stock_info.py`，入口文件路径不变，不受影响
- **_meta.json**: scripts 字段需更新为列出新增模块文件
- **SKILL.md**: 无需修改（命令列表和用法不变）