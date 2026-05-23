## 1. 提取 market.py

- [x] 1.1 创建 `cs-stock/scripts/market.py`，从 cs_stock_info.py 提取 `parse_symbol()`、`prefixed_sina()`、`to_yahoo_symbol()` 和相关常量
- [x] 1.2 在 cs_stock_info.py 中将原函数替换为 `from market import parse_symbol, prefixed_sina, to_yahoo_symbol`
- [x] 1.3 验证：`python cs_stock_info.py snapshot 600519 --output json` 仍正常运行

## 2. 提取 utils.py

- [x] 2.1 创建 `cs-stock/scripts/utils.py`，提取 `safe_call()`、`ret_n()`、`_fmt_pct()`、`_fmt_num()`、`_float_or_none()`
- [x] 2.2 在 cs_stock_info.py 中替换为 `from utils import safe_call, ret_n, _fmt_pct, _fmt_num, _float_or_none`
- [x] 2.3 验证：`python cs_stock_info.py snapshot 600519 --output json`

## 3. 提取 render.py

- [x] 3.1 创建 `cs-stock/scripts/render.py`，提取所有 11 个 `_render_*` 函数、`RENDER_TABLE` 字典、`print_text()` 函数
- [x] 3.2 render.py 顶部添加 `from utils import _fmt_pct, _fmt_num`
- [x] 3.3 在 cs_stock_info.py 中替换为 `from render import RENDER_TABLE, print_text`
- [x] 3.4 验证：`python cs_stock_info.py snapshot 600519 --output text`

## 4. 提取 fetch_ashare.py

- [x] 4.1 创建 `cs-stock/scripts/fetch_ashare.py`，提取 A 股抓取函数 + 公告/关联
- [x] 4.2 fetch_ashare.py 顶部添加 `from utils import safe_call, ret_n`、`from market import prefixed_sina`
- [x] 4.3 在 cs_stock_info.py 中替换为 `from fetch_ashare import ...`
- [x] 4.4 验证：`python cs_stock_info.py snapshot 600519 --output json`

## 5. 提取 fetch_etf.py

- [x] 5.1 创建 `cs-stock/scripts/fetch_etf.py`，提取 ETF 抓取函数 + `_float_or_none()` + `fetch_etf_name()`
- [x] 5.2 fetch_etf.py 顶部添加 `from utils import safe_call, ret_n, _name_code_cache, _etf_category_cache`、`from market import prefixed_sina`
- [x] 5.3 在 cs_stock_info.py 中替换为 `from fetch_etf import fetch_etf_snapshot, fetch_etf_daily, fetch_etf_nav, fetch_etf_name`
- [x] 5.4 验证：`python cs_stock_info.py snapshot 510300 --output json`（ETF 测试）

## 6. 提取 fetch_yahoo.py

- [x] 6.1 创建 `cs-stock/scripts/fetch_yahoo.py`，提取港美股抓取函数 + 降级函数
- [x] 6.2 fetch_yahoo.py 顶部添加 `from utils import safe_call` + `sys.path.insert` 引入 `_shared`
- [x] 6.3 在 cs_stock_info.py 中替换为 `from fetch_yahoo import ...`
- [x] 6.4 验证：`python cs_stock_info.py snapshot 0700.HK --output json`（港股测试）

## 7. 提取 commands.py

- [x] 7.1 创建 `cs-stock/scripts/commands.py`，提取所有 8 个 `cmd_*` 函数和 3 个 `_fallback_*` 降级函数
- [x] 7.2 commands.py 顶部添加 `from fetch_ashare import ...`、`from fetch_etf import ...`、`from fetch_yahoo import ...`、`from market import ...`、`from utils import ...`
- [x] 7.3 在 cs_stock_info.py 中替换为 `from commands import cmd_snapshot_a, cmd_daily, ...`
- [x] 7.4 验证：`python cs_stock_info.py snapshot 600519 --output json`

## 8. 清理入口文件 + 更新元数据

- [x] 8.1 删除 cs_stock_info.py 中所有已提取的函数定义，仅保留 import + argparse + main
- [x] 8.2 确认 cs_stock_info.py 约 130 行，只含 CLI 入口逻辑
- [x] 8.3 更新 `cs-stock/_meta.json` 的 scripts 字段，列出所有新增模块
- [x] 8.4 全面回归验证：A 股 / ETF / 港股 / 美股 的 snapshot + daily 命令