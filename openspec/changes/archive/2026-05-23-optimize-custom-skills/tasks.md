## 1. 创建 _shared 目录结构

- [x] 1.1 创建 `custom-skills/_shared/` 目录和 `custom-skills/_shared/indicators/` 子目录
- [x] 1.2 在 `_shared/indicators/` 下创建空文件：`builder.py`、`config.py`、`handlers.py`

## 2. 实现共享代理模块

- [x] 2.1 编写 `custom-skills/_shared/proxy.py`：实现 `detect_proxy()` 函数（env var 优先 → Clash 端口扫描 7890/7891/7897）
- [x] 2.2 编写 `setup_proxy_env(override=None)` 函数：通过 `os.environ.setdefault` 设置 HTTPS_PROXY/HTTP_PROXY，无代理时输出 stderr 警告
- [x] 2.3 编写 `apply_proxy_to_session(session, proxy=None)` 函数：设置 `session.proxies["http"]` 和 `session.proxies["https"]`
- [x] 2.4 编写 `clear_proxy_env()` / `restore_proxy_env()` 函数：保存/恢复 HTTP_PROXY/HTTPS_PROXY/http_proxy/https_proxy 环境变量
- [x] 2.5 验证：从 `cs-stock/scripts/` 和 `fuyao-leading-indicators/scripts/` 分别测试 `sys.path.insert` + `from proxy import ...` 可正常导入

## 3. 实现前置指标框架核心

- [x] 3.1 编写 `custom-skills/_shared/indicators/config.py`：定义 `IndicatorConfig` dataclass（key, name, direction, weight, unit, data_method, handler, transmission_summary, scoring_guide + 可选 tier, threshold, search_hint）
- [x] 3.2 编写 `custom-skills/_shared/indicators/handlers.py`：实现 kline handler（divisor + compute_kline_stats + 20/60日趋势 + 120日百分位 + 波动率警告）、macro handler（透传 fetcher 字段）、ranking handler（透传）、agent_search handler（标记 agent_required + 复制 search_hint）
- [x] 3.3 编写 `custom-skills/_shared/indicators/builder.py`：实现 `build_snapshot(config, fetchers, results, errors)` 函数——遍历 config 指标，按 handler 类型分发到对应处理逻辑，组装四态 data_quality 快照
- [x] 3.4 编写 `builder.py` 中的 `render_text_snapshot(snapshot)` 函数——按 tier/非tier 渲染标题，按 data_quality 渲染数据行，partial 数据包含 raw_text 截断
- [x] 3.5 编写 `builder.py` 中的并发获取支持：`fetch_all_concurrent(fetchers, max_workers=3)` 用 ThreadPoolExecutor 调用已注册的 fetcher，异常指标记入 errors dict

## 4. 重构 cs-stock 代理逻辑

- [x] 4.1 在 `cs-stock/scripts/cs_stock_info.py` 顶部添加 `sys.path.insert` 引入 `_shared`
- [x] 4.2 替换内联 `_detect_proxy()` 为 `from proxy import detect_proxy`
- [x] 4.3 替换 `setup_proxy_for_yahoo()` 为 `from proxy import setup_proxy_env`，删除原函数
- [x] 4.4 替换 `clear_proxy_for_akshare()` / `restore_proxy()` 为 `from proxy import clear_proxy_env, restore_proxy_env`
- [x] 4.5 删除 cs-stock 中 `_DEFAULT_PROXY` 常量和 `_saved_proxy_env` 全局变量
- [x] 4.6 验证：运行 `python cs_stock_info.py --symbol 0700.HK snapshot --output json` 确认代理行为不变

## 5. 重构 fuyao 代理逻辑和指标框架

- [x] 5.1 在 `fuyao-leading-indicators/scripts/eastmoney_fetch.py` 顶部添加 `sys.path.insert` 引入 `_shared`
- [x] 5.2 替换内联 `_detect_proxy()` 和模块级代理设置为 `from proxy import apply_proxy_to_session` + `apply_proxy_to_session(SESSION)`
- [x] 5.3 更新 `fuyao-leading-indicators/scripts/indicators_config.py`：为每个指标添加 `handler` 字段和 `data_method` 字段
- [x] 5.4 重写 `fuyao-leading-indicators/scripts/fuyao_indicators.py`：用 `from indicators.builder import build_snapshot, render_text_snapshot, fetch_all_concurrent` 替代内联的 `build_snapshot()` 和 `render_text_snapshot()`；保留 `--skip-auto` 和 `--raw-cpca` 技能专属参数
- [x] 5.5 验证：运行 `python fuyao_indicators.py --output json` 确认输出结构与重构前兼容

## 6. 重构 tencent 指标框架

- [x] 6.1 更新 `tencent-leading-indicators/scripts/indicators_config.py`：为每个指标添加 `handler` 字段
- [x] 6.2 重写 `tencent-leading-indicators/scripts/tencent_indicators.py`：用 `from indicators.builder import build_snapshot, render_text_snapshot, fetch_all_concurrent` 替代内联实现；保留 fetcher 注册逻辑
- [x] 6.3 验证：运行 `python tencent_indicators.py --output json` 确认输出结构与重构前兼容

## 7. 收尾：元数据、文档、Git 清理

- [x] 7.1 更新 `fuyao-leading-indicators/_meta.json`：dependencies 从 `[]` 改为 `["_shared"]`；version bump
- [x] 7.2 更新 `tencent-leading-indicators/_meta.json`：dependencies 从 `[]` 改为 `["_shared"]`；version bump
- [x] 7.3 更新 `stock-research-report-analysis/_meta.json`：dependencies 从 `[]` 改为 `["cs-stock"]`（反映实际调用关系）
- [x] 7.4 运行 `git rm -r --cached custom-skills/stock-research-report-analysis/.venv/` 清理 56MB 已跟踪的 .venv（实际未被 track，无需操作）
- [x] 7.5 验证 `.gitignore` 已包含 `.venv/` 规则（已存在，确认OK）
- [x] 7.6 更新 `fuyao-leading-indicators/SKILL.md`：补充脚本调用共享框架的说明
- [x] 7.7 更新 `tencent-leading-indicators/SKILL.md`：补充脚本调用共享框架的说明