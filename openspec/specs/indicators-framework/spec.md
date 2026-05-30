## ADDED Requirements

### Requirement: 指标配置数据结构
系统 SHALL 定义 `IndicatorConfig` 数据结构，每个指标 MUST 包含以下字段：
- `key`: str — 指标唯一标识（kebab-case）
- `name`: str — 中文名称
- `direction`: str — 方向分类（cost/revenue/policy/consumption/growth/capital_flow/cost_reverse）
- `weight`: float — 权重（0-1，所有指标之和为 1.0）
- `unit`: str — 度量单位
- `data_method`: str — 数据获取方式，MUST 为 `"script"` 或 `"agent_search"`
- `handler`: str — 处理器类型（`"kline"` / `"macro"` / `"ranking"` / `"agent_search"`）
- `transmission_summary`: str — 1-2 句传导机制说明
- `scoring_guide`: str — LLM 评分指引（逗号分隔的量化区间）

可选字段：
- `tier`: int — 层级分组（1/2/3），用于渲染时分组显示
- `threshold`: dict — 看涨/看跌阈值（`{"bearish": N, "bullish": M}`）
- `search_hint`: str — Agent 搜索建议（仅 `agent_search` 指标需要）

#### Scenario: 完整指标配置
- **WHEN** 定义一个 K-line 类型指标（如纯碱价格）
- **THEN** 配置包含 `key="soda_ash"`, `handler="kline"`, `data_method="script"`，及所有必需字段

#### Scenario: Agent 搜索指标配置
- **WHEN** 定义一个需要 Agent 搜索的指标（如游戏版号）
- **THEN** 配置包含 `handler="agent_search"`, `data_method="agent_search"`, `search_hint="..."`

### Requirement: Fetcher 注册机制
系统 SHALL 提供 `register_fetchers(fetcher_map: dict[str, Callable])` 方法，将指标 key 映射到对应的 fetcher 函数。Fetcher 函数 MUST 返回 dict，包含 `data_quality` 字段（`"complete"` / `"partial"` / `"agent_required"` / `"missing"`）。

#### Scenario: 注册多个 fetcher
- **WHEN** 调用 `register_fetchers({"soda_ash": fetch_soda_ash, "auto_sales": fetch_auto_sales})`
- **THEN** 后续 `build_snapshot()` 调用这些 fetcher 获取数据

#### Scenario: Fetcher 返回 partial 数据
- **WHEN** fetcher 返回 `{"data_quality": "partial", "raw_text": "...", "latest_price": 1800}`
- **THEN** 快照中该指标 `data_quality` 为 `"partial"`，`raw_text` 被保留供 LLM 提取

#### Scenario: 缺少 fetcher 的指标
- **WHEN** 某个 `data_method="script"` 的指标未注册 fetcher
- **THEN** 该指标 `data_quality` 设为 `"missing"`，`error` 设为 `"no_fetcher_registered"`

### Requirement: 快照构建器
系统 SHALL 提供 `build_snapshot(config: dict, fetchers: dict, results: dict, errors: dict) -> dict` 函数，生成统一格式的快照 JSON。

快照顶层结构 MUST 为：
```json
{
  "snapshot_version": "3.0",
  "fetched_at": "ISO8601",
  "indicators": { "<key>": { ... } }
}
```

每个指标条目 MUST 包含：`name`, `direction`, `weight`, `unit`, `data_method`, `data_quality`, `transmission_summary`, `scoring_guide`。

#### Scenario: K-line handler 处理
- **WHEN** 指标的 `handler="kline"` 且 fetcher 返回 K-line 数据
- **THEN** 快照自动计算：当前价格（应用 divisor）、20/60 日趋势、120 日百分位、波动率警告

#### Scenario: Macro handler 处理
- **WHEN** 指标的 `handler="macro"` 且 fetcher 返回宏观数据
- **THEN** 快照直接透传 fetcher 返回的字段

#### Scenario: Agent search handler 处理
- **WHEN** 指标的 `handler="agent_search"`
- **THEN** 快照中 `data_quality` 为 `"agent_required"`，`search_hint` 从 config 复制

#### Scenario: Handler 不匹配
- **WHEN** 指标的 `handler` 值不在已知处理器列表中
- **THEN** 快照中该指标 `data_quality` 为 `"missing"`，`error` 为 `"unknown_handler: <handler>"`

### Requirement: 文本渲染器
系统 SHALL 提供 `render_text_snapshot(snapshot: dict) -> str` 函数，将快照渲染为人类可读的 Markdown 文本。

#### Scenario: 包含 tier 的渲染
- **WHEN** 指标配置包含 `tier` 字段
- **THEN** 渲染标题为 `## {name} (Tier{N}, {direction}, 权重{w}%)`

#### Scenario: 不含 tier 的渲染
- **WHEN** 指标配置不含 `tier` 字段
- **THEN** 渲染标题为 `## {name} ({direction}，权重{w}%)`

#### Scenario: partial 数据渲染
- **WHEN** 指标 `data_quality` 为 `"partial"` 且有 `raw_text`
- **THEN** 渲染包含已解析字段 + `- 原始文本（供LLM提取）：{raw_text前100字符}...`

### Requirement: 并发获取支持
`build_snapshot` 流程 SHALL 支持通过 `ThreadPoolExecutor` 并发调用已注册的 fetcher 函数。

#### Scenario: 并发获取多个指标
- **WHEN** 注册了 5 个 fetcher 且 `max_workers=3`
- **THEN** fetcher 并发执行，`results` 和 `errors` dict 由框架组装

#### Scenario: 单个 fetcher 失败不影响其他
- **WHEN** 5 个 fetcher 中 1 个抛出异常
- **THEN** 其余 4 个正常执行，失败指标 `data_quality` 为 `"missing"`，`error` 为异常信息

### Requirement: 模块位置与结构
框架代码 SHALL 位于 `custom-skills/_shared/indicators/` 目录下：
- `builder.py` — `build_snapshot()`, `render_text_snapshot()`
- `config.py` — `IndicatorConfig` dataclass, handler 注册表
- `handlers.py` — 各 handler 类型的处理逻辑（kline, macro, ranking, agent_search）

#### Scenario: 从 tencent 技能导入
- **WHEN** `inv-tencent-indicators/scripts/tencent_indicators.py` 需要框架
- **THEN** 通过 `from indicators.builder import build_snapshot, render_text_snapshot` 导入
