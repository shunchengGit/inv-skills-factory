## Context

cs-stock/scripts/cs_stock_info.py 是 1383 行单文件，包含市场识别、数据抓取（A 股/ETF/港美股）、命令编排、渲染输出和 CLI 入口。其他技能（value-investing-valuation、porter-five-forces-analysis、quality-growth-qarp）通过 `python cs_stock_info.py <command> --output json` CLI 子进程调用，不受内部拆分影响。

### 当前函数清单与行范围

| 函数 | 行范围 | 行数 | 目标模块 |
|------|--------|------|----------|
| `parse_symbol()` | 29-55 | 27 | market.py |
| `prefixed_sina()` | 58-71 | 14 | market.py |
| `to_yahoo_symbol()` | 74-91 | 18 | market.py |
| `safe_call()` | 94-114 | 21 | utils.py |
| `ret_n()` | 117-131 | 15 | utils.py |
| `_fmt_pct()` | 134-139 | 6 | utils.py |
| `_fmt_num()` | 142-147 | 6 | utils.py |
| `_safe_float()` | 150-154 | 5 | utils.py |
| `fetch_ashare_snapshot()` | 157-228 | 72 | fetch_ashare.py |
| `fetch_ashare_daily()` | 231-254 | 24 | fetch_ashare.py |
| `fetch_announcements()` | 257-269 | 13 | fetch_ashare.py |
| `fetch_research()` | 272-283 | 12 | fetch_ashare.py |
| `fetch_etf_snapshot()` | 286-368 | 83 | fetch_etf.py |
| `fetch_etf_daily()` | 371-385 | 15 | fetch_etf.py |
| `fetch_yahoo_snapshot()` | 388-465 | 78 | fetch_yahoo.py |
| `fetch_yahoo_daily()` | 468-496 | 29 | fetch_yahoo.py |
| `cmd_snapshot()` | 499-641 | 143 | commands.py |
| `cmd_daily()` | 644-705 | 62 | commands.py |
| `cmd_profile()` | 708-749 | 42 | commands.py |
| `cmd_financial()` | 752-832 | 81 | commands.py |
| `cmd_description()` | 835-870 | 36 | commands.py |
| `cmd_announcements()` | 873-890 | 18 | commands.py |
| `cmd_relations()` | 893-961 | 69 | commands.py |
| `cmd_index_daily()` | 964-993 | 30 | commands.py |
| `_fallback_ashare_*` (3个) | 996-1099 | 104 | commands.py |
| `render_*` (11个) + `RENDER_TABLE` | 1102-1419 | 318 | render.py |
| `main()` + argparse | 1420-1383 | ~87 | cs_stock_info.py |

## Goals / Non-Goals

**Goals:**
- 每个 .py 文件单一职责，行数控制在 500 行以内
- 模块间依赖方向清晰：cli → commands → fetch_* → market/utils，render 独立
- 所有模块通过 `sys.path.insert(0, 同级目录)` 导入，与现有 scripts/ 风格一致
- CLI 接口、JSON 输出结构不变

**Non-Goals:**
- 不改变任何命令行参数或输出格式
- 不添加新的子命令或功能
- 不修改 SKILL.md
- 不引入 pyproject.toml 包结构或 pip installable 模式
- 不合并 fetch_misc.py 为独立文件（26 行太少，并入 fetch_ashare.py）

## Decisions

### D1: 模块间导入使用 `sys.path.insert` + 相对文件名

**决策**: 所有模块在文件顶部 `sys.path.insert(0, str(Path(__file__).resolve().parent))`，然后 `from market import parse_symbol, prefixed_sina` 等。

**理由**: 与现有 scripts/ 目录中其他技能的导入方式一致（如 `_shared` 的引入方式），无需修改 PYTHONPATH 或 pyproject.toml。

### D2: 公告/调研并入 fetch_ashare.py

**决策**: `fetch_announcements()` 和 `fetch_research()`（共 25 行）放入 `fetch_ashare.py`，不单独建 `fetch_misc.py`。

**理由**: 26 行的独立模块增加文件数但无实际可维护性收益。公告和调研是 A 股特有功能，逻辑上属于 A 股数据层。

### D3: 3 个降级函数留在 commands.py

**决策**: `_fallback_ashare_snapshot()`、`_fallback_ashare_daily()`、`_fallback_ashare_financial()`（共 104 行）留在 `commands.py` 中，不单独提取。

**理由**: 降级函数是命令编排的一部分（"主路径失败 → 尝试降级路径"），与 cmd_* 函数强耦合。提取为独立模块增加间接层但无清晰职责边界。

### D4: render.py 包含 RENDER_TABLE dispatch 字典

**决策**: `RENDER_TABLE` 字典和 11 个 `render_*` 函数全部在 `render.py` 中。

**理由**: 渲染是纯输出逻辑，不依赖任何 fetch/command 函数。`RENDER_TABLE` 是 render 函数的分发表，与 render 函数强内聚。

### D5: 入口文件仅保留 CLI 解析 + 代理策略 + dispatch

**决策**: `cs_stock_info.py` 缩减为约 87 行，包含：
- `sys.path.insert` 导入路径
- 代理管理（setup/clear/restore）
- argparse 定义
- `main()` 调用 `commands.cmd_*` 和 `render.RENDER_TABLE`

**理由**: 入口文件只做"接线"——解析参数、设置环境、分发到对应命令和渲染器。不包含任何业务逻辑。

### D6: 拆分顺序按依赖方向自底向上

**决策**: 拆分顺序：market.py → utils.py → render.py → fetch_ashare.py → fetch_etf.py → fetch_yahoo.py → commands.py → cs_stock_info.py 入口。

**理由**: 自底向上拆分保证每步可独立验证。market/utils 无依赖，先拆最安全；render 只依赖 utils，第二步；fetch_* 依赖 market + utils，第三步；commands 依赖所有 fetch_* + market + utils，最后。

## Module Dependency Graph

```
cs_stock_info.py (入口，~87行)
  ├─→ commands.py (~466行)
  │     ├─→ fetch_ashare.py (~104行)
  │     ├─→ fetch_etf.py (~98行)
  │     ├─→ fetch_yahoo.py (~108行)
  │     ├─→ market.py (~60行)
  │     └─→ utils.py (~55行)
  ├─→ render.py (~318行)
  │     └─→ utils.py
  └─→ _shared/proxy.py
```

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 模块间 import 需要所有文件在同一目录 | 已满足：cs-stock/scripts/ 是扁平目录 |
| 循环导入风险 | 依赖图是 DAG（无环），market/utils 不依赖上层模块 |
| 拆分后 debug 跳转文件多 | IDE 支持多文件跳转，比 1383 行单文件定位更快 |
| 测试覆盖不变 | 拆分不改变行为，现有测试仍通过；未来可对单个模块添加单元测试 |

## Migration Plan

1. 自底向上拆分，每步一个 commit，保证可回退
2. 每步验证：`python cs_stock_info.py --help` 和一个 smoke test 命令
3. 拆分完成后删除原文件中的冗余代码
4. 最后更新 `_meta.json` 的 scripts 字段