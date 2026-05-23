## MODIFIED Requirements

### Requirement: 福耀前置指标数据获取改为调用共享框架
fuyao-leading-indicators 的 `fuyao_indicators.py` SHALL 改为调用 `_shared/indicators/` 框架的 `build_snapshot()` 和 `render_text_snapshot()`，而非内联实现。

#### Scenario: build_snapshot 使用共享框架
- **WHEN** 运行 `fuyao_indicators.py`
- **THEN** 调用 `_shared/indicators/builder.py` 的 `build_snapshot()`，传入 `indicators_config.py` 中的 INDICATORS 配置和已注册的 fetcher 函数

#### Scenario: render_text_snapshot 使用共享框架
- **WHEN** 输出格式为 `text`
- **THEN** 调用 `_shared/indicators/builder.py` 的 `render_text_snapshot()`，传入快照 dict

#### Scenario: 命令行接口保持不变
- **WHEN** 运行 `python fuyao_indicators.py --output json`
- **THEN** 输出格式与重构前兼容（相同的顶层 JSON 结构和字段名）

#### Scenario: 保留技能专属 CLI 参数
- **WHEN** 运行 `python fuyao_indicators.py --skip-auto --raw-cpca`
- **THEN** `--skip-auto` 和 `--raw-cpca` 参数仍可使用，由技能自己的 CLI 层处理

### Requirement: indicators_config 符合 IndicatorConfig schema
`indicators_config.py` 中的 INDICATORS dict SHALL 符合 `_shared/indicators/config.py` 定义的 IndicatorConfig 数据结构要求：每个指标 MUST 声明 `data_method` 和 `handler` 字段。

#### Scenario: 统一 data_method 声明
- **WHEN** 原配置中 script 类型指标在 build_snapshot 中注入 `data_method`
- **THEN** 改为在 config 中显式声明 `data_method: "script"`

#### Scenario: 新增 handler 字段
- **WHEN** 原配置中所有指标缺少 `handler` 字段
- **THEN** 为每个指标添加 `handler` 字段：`soda_ash`/`natural_gas`/`usdcny`/`ccfi` → `"kline"`, `auto_sales`/`nev_penetration` → `"macro"`, `us_auto_sales` → `"macro"`, `eu_auto_sales` → `"agent_search"`

### Requirement: 代理检测改为调用共享模块
`eastmoney_fetch.py` 中的 `_detect_proxy()` 和模块级代理设置 SHALL 改为调用 `_shared/proxy.py` 的 `detect_proxy()` 和 `apply_proxy_to_session()`。

#### Scenario: 替换内联代理检测
- **WHEN** `eastmoney_fetch.py` 初始化 requests.Session
- **THEN** 调用 `apply_proxy_to_session(session)` 替代内联的 `_detect_proxy()` + `session.proxies.update()`

#### Scenario: 代理行为不变
- **WHEN** Clash 运行在 7890 端口
- **THEN** session 的 proxies 被正确设置，与重构前行为一致

### Requirement: _meta.json 依赖声明修正
`fuyao-leading-indicators/_meta.json` 的 `dependencies` SHALL 反映实际依赖关系。

#### Scenario: 补充 _shared 依赖
- **WHEN** 重构后 fuyao 脚本依赖 `_shared/proxy.py` 和 `_shared/indicators/`
- **THEN** `_meta.json` 的 `dependencies` 从 `[]` 更新为 `["_shared"]`
