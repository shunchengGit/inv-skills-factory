## Context

custom-skills/ 包含 7 个投资分析技能，其中两个前置指标技能（tencent/fuyao）和 cs-stock 存在代码重复和结构一致性问题。代理检测逻辑在 `cs_stock_info.py` 和 `eastmoney_fetch.py` 中各有一份几乎相同的实现。前置指标技能虽结构高度相似，但各自独立实现，新增公司指标需复制整套代码。

### 当前代码重复情况

**代理检测**：`_detect_proxy()` 在两个文件中字节级相同（env var 优先 + Clash 端口扫描），但应用方式不同——cs-stock 通过 `os.environ` 设给 yfinance，eastmoney_fetch 通过 `session.proxies` 设给 requests。

**前置指标**：两套实现共享相同三阶段架构（fetch_all → build_snapshot → render_text），但细节差异较大：
- Tencent 用 config 声明 data_method，Fuyao 在 build_snapshot 中注入
- Fuyao 有 K-line 共享处理块（divisor_map + compute_kline_stats），Tencent 无 K-line 指标
- Fuyao 用 ThreadPoolExecutor 并发，Tencent 顺序执行
- Fuyao 有 partial/raw_only 中间数据质量状态，Tencent 只有 complete/missing/agent_required
- 快照版本不一致（1.0 vs 2.0）

## Goals / Non-Goals

**Goals:**
- 消除代理检测代码重复，所有脚本调用统一模块
- 建立前置指标共享框架，新增公司指标只需添加配置文件 + fetcher 脚本
- 清理 Git 仓库中的 .venv 污染
- 修正 _meta.json 依赖声明

**Non-Goals:**
- 不重写 cs-stock 的 1443 行单文件拆分（独立优化，范围过大）
- 不脚本化 QARP 选股闸门（独立优化）
- 不统一所有技能的错误处理规范（渐进改进）
- 不改变各技能的 SKILL.md 指令逻辑和 Claude 交互方式

## Decisions

### D1: 共享代码放在 `custom-skills/_shared/`

**决策**: 新建 `custom-skills/_shared/` 目录，放置 `proxy.py` 和 `indicators/` 包。

**替代方案**:
- A) 每个技能内 `sys.path.append` 到 cs-stock —— 耦合 cs-stock，且 cs-stock 不是公共库
- B) 发布为 pip 包 —— 过度工程，技能脚本是 CLI 工具非库
- C) 放在仓库根目录 `shared/` —— 与 custom-skills/ 平级，语义不如 `_shared` 明确

**理由**: `_shared` 前缀下划线表明它是基础设施而非独立技能，与现有 skill 目录命名约定兼容。各脚本通过 `sys.path.insert(0, Path(__file__).resolve().parents[2] / "_shared")` 引入，无需 pip install。

### D2: 代理模块提供两种应用方式

**决策**: `_shared/proxy.py` 导出：
- `detect_proxy()` — 核心检测（env var → 端口扫描）
- `setup_proxy_env(override=None)` — 设 `os.environ`（给 yfinance/curl_cffi 用）
- `apply_proxy_to_session(session, proxy=None)` — 设 `session.proxies`（给 requests 用）
- `clear_proxy_env()` / `restore_proxy_env()` — 临时清除/恢复（给 akshare 用）

**理由**: 两种应用方式面向不同的 HTTP 库，无法统一为一种。cs-stock 用 env var 是因为 yfinance/curl_cffi 从环境变量读取代理；eastmoney_fetch 用 session.proxies 是因为 requests 优先读 session 配置。

### D3: 前置指标框架采用配置驱动 + fetcher 注册模式

**决策**: 框架核心为 `IndicatorSnapshotBuilder`，工作流：

```
indicators_config.py          *_fetch.py            _shared/indicators/
─────────────────           ───────────           ────────────────────
INDICATORS = {               def fetch_xxx():      builder.py
  "soda_ash": {                return {...}          - build_snapshot()
    name, direction, weight,                       - render_text()
    fetcher="soda_ash",       def fetch_yyy():      config.py
    handler="kline",            return {...}          - IndicatorConfig dataclass
    ...                                            - handler 注册表
}                             register_fetchers()
                              → {key: callable}
```

**关键设计**:
- 每个指标的 config 中声明 `handler` 类型（`"kline"` | `"macro"` | `"ranking"` | `"agent_search"`）
- handler 类型决定 build_snapshot 中的数据处理逻辑（K-line 共享 divisor_map + 趋势统计，macro 直接取值等）
- fetcher 函数在各自的 `*_fetch.py` 中定义，通过 `register_fetchers()` 注册到 builder
- 新增公司指标：写 config + fetcher 脚本 + `register_fetchers`，零框架代码修改

**替代方案**:
- A) 纯配置驱动（YAML 定义数据源 URL + 解析规则）—— 太理想化，数据源多样（Playwright、RSS、FRED CSV），无法纯配置化
- B) 继承体系（BaseIndicator → KlineIndicator, MacroIndicator）—— Python 不需要这种重 OO，函数 + handler 注册更 Pythonic

### D4: 统一 data_method 声明位置为 config 级别

**决策**: 所有指标在 config 中必须声明 `data_method: "script" | "agent_search"`，不再在 build_snapshot 中注入。

**理由**: Tencent 已采用此模式，更清晰。Fuyao 的"运行时注入"模式使得 config 不完整，无法仅看 config 就知道指标的数据来源。

### D5: 统一 data_quality 为四态模型

**决策**: 采用 Fuyao 的更丰富模型：`"complete"` | `"partial"` | `"agent_required"` | `"missing"`。

**理由**: partial 状态（脚本获取了数据但未完全解析，附 raw_text 供 LLM 提取）是有价值的中间态，Tencent 未来也可能需要。

### D6: .venv 清理使用 `git rm -r --cached`

**决策**: `git rm -r --cached custom-skills/stock-research-report-analysis/.venv/`，然后 commit。.gitignore 已有 `.venv/` 规则，后续不会再被 track。

**理由**: `--cached` 只从 Git 索引移除，不删除本地文件。用户本地 .venv 保持不变，但 clone 仓库时不再下载 56MB。

### D7: 保留各技能独立的 fetcher 脚本文件

**决策**: 框架只抽取 `build_snapshot`、`render_text`、config schema 和 handler 注册。各公司的 fetcher 脚本（eastmoney_fetch.py、game_ranking_fetch.py 等）仍留在各自技能目录下。

**理由**: fetcher 是领域特定的（不同 API、不同解析逻辑），强行统一反而增加复杂度。框架负责"组装"而非"获取"。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| `_shared` 引入 `sys.path` hack，不够优雅 | 各脚本顶部一行 `sys.path.insert`，比代码重复好；未来可考虑 pyproject.toml 的 path dependency |
| handler 类型需预定义，未来新数据形态可能不 fit | handler 注册表是开放式的，新类型只需写一个处理函数并注册，不改框架核心 |
| Tencent/Fuyao 重构后命令行参数接口微变 | 保持 `--output json\|text` 不变；Fuyao 的 `--skip-auto`、`--raw-cpca` 保留为技能专属参数 |
| `global_auto_fetch.py` 中 `trust_env=False` 绕过代理的逻辑与共享代理模块冲突 | 不冲突——FRED（美国数据源）不需要代理，在 fetcher 层控制 session 配置，代理模块只管检测和设置 |

## Migration Plan

1. **Phase 1（无破坏性）**: 创建 `_shared/`，写 `proxy.py` 和 `indicators/` 框架代码。现有脚本不改动。
2. **Phase 2（渐进替换）**: cs-stock 和 eastmoney_fetch 改为 import _shared.proxy；tencent/fuyao 的 `*_indicators.py` 改为调用框架。每个技能独立改、独立测。
3. **Phase 3（收尾）**: 清理 .venv、修正 _meta.json、更新 SKILL.md。
4. **回滚**: 每个阶段都是独立 commit，可逐个 revert。框架代码是增量添加，删除 `_shared/` 即可回退 Phase 1。

## Open Questions

- 是否需要为 `_shared` 写 `__init__.py` 使其成为正式 Python 包？还是保持为 loose scripts 目录？当前倾向后者（与现有 scripts/ 风格一致）。
