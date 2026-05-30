## MODIFIED Requirements

### Requirement: 腾讯前置指标数据获取改为调用共享框架
inv-tencent-indicators 的 `tencent_indicators.py` SHALL 改为调用 `_shared/indicators/` 框架的 `build_snapshot()` 和 `render_text_snapshot()`，而非内联实现。

#### Scenario: build_snapshot 使用共享框架
- **WHEN** 运行 `tencent_indicators.py`
- **THEN** 调用 `_shared/indicators/builder.py` 的 `build_snapshot()`，传入 `indicators_config.py` 中的 INDICATORS 配置和已注册的 fetcher 函数

#### Scenario: render_text_snapshot 使用共享框架
- **WHEN** 输出格式为 `text`
- **THEN** 调用 `_shared/indicators/builder.py` 的 `render_text_snapshot()`，传入快照 dict

#### Scenario: 命令行接口保持不变
- **WHEN** 运行 `python tencent_indicators.py --output json`
- **THEN** 输出格式与重构前兼容（相同的顶层 JSON 结构和字段名）

### Requirement: indicators_config 符合 IndicatorConfig schema
`indicators_config.py` 中的 INDICATORS dict SHALL 符合 `_shared/indicators/config.py` 定义的 IndicatorConfig 数据结构要求：每个指标 MUST 声明 `data_method` 和 `handler` 字段。

#### Scenario: 补充 data_method 字段
- **WHEN** 原配置中 script 类型指标缺少 `data_method` 字段
- **THEN** 补充 `data_method: "script"`；`agent_search` 指标已有 `data_method` 字段保持不变

#### Scenario: 新增 handler 字段
- **WHEN** 原配置中所有指标缺少 `handler` 字段
- **THEN** 为每个指标添加 `handler` 字段：`retail_sales` → `"macro"`, `top_games_ranking` → `"ranking"`, `southbound_flow` → `"macro"`, `game_approval`/`wechat_video_usage`/`wechat_payment` → `"agent_search"`

### Requirement: 代理检测改为调用共享模块
`southbound_flow_fetch.py` 中如需代理 SHALL 改为调用 `_shared/proxy.py` 的 `apply_proxy_to_session()`（当前该脚本使用 akshare 直连，不使用代理，此为预防性要求）。

#### Scenario: 当前无代理需求
- **WHEN** `southbound_flow_fetch.py` 使用 akshare 获取港股通数据
- **THEN** 不使用代理，与当前行为一致

### Requirement: _meta.json 依赖声明修正
`inv-tencent-indicators/_meta.json` 的 `dependencies` SHALL 反映实际依赖关系。

#### Scenario: 补充 _shared 依赖
- **WHEN** 重构后 tencent 脚本依赖 `_shared/proxy.py` 和 `_shared/indicators/`
- **THEN** `_meta.json` 的 `dependencies` 从 `[]` 更新为 `["_shared"]`
