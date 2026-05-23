## Why

custom-skills/ 经过多次迭代已积累 7 个技能、16 个 Python 脚本，但存在三类系统性问题：(1) 代码重复——代理检测、前置指标快照构建等逻辑散落各处，改一处漏一处；(2) 仓库污染——.venv 已被 git track（56MB）；(3) 扩展性差——新增前置指标技能需复制整套代码骨架。现在优化可以避免技术债持续膨胀。

## What Changes

- 清理 `stock-research-report-analysis/.venv/` 出 Git 仓库（已 track 需 `git rm --cached`）
- 抽取代理管理公共模块（`custom-skills/_shared/proxy.py`），统一 cs-stock、eastmoney_fetch、global_auto_fetch 三处的 Clash 端口检测逻辑
- 抽取前置指标框架公共模块（`custom-skills/_shared/indicators/`），将 tencent/fuyao 两套独立实现统一为配置驱动框架
- 修正 `_meta.json` 中 dependencies 声明与实际调用不一致的问题（fuyao、tencent、stock-research-report-analysis）
- **BREAKING**: tencent-leading-indicators 和 fuyao-leading-indicators 的脚本入口从各自独立实现改为调用共享框架，命令行参数接口可能微调

## Capabilities

### New Capabilities
- `shared-proxy`: 统一代理检测与管理模块，供所有需要代理的脚本调用
- `indicators-framework`: 前置指标配置驱动框架——指标定义、快照构建、评分渲染的共享基础设施，新增公司指标只需添加配置文件

### Modified Capabilities
- `tencent-leading-indicators`: 脚本改为调用 indicators-framework，移除重复的快照构建代码
- `fuyao-leading-indicators`: 脚本改为调用 indicators-framework，移除重复的快照构建代码

## Impact

- **代码**: `cs-stock/scripts/cs_stock_info.py`、`fuyao-leading-indicators/scripts/`（4 文件）、`tencent-leading-indicators/scripts/`（4 文件）需要重构
- **依赖**: fuyao、tencent 的 `_meta.json` 需新增对 `_shared` 的依赖声明；stock-research-report-analysis 的 dependencies 需补充 cs-stock
- **Git**: 需从索引中移除 `.venv/`，仓库体积减小约 56MB
- **SKILL.md**: fuyao 和 tencent 的 SKILL.md 需更新脚本调用方式说明
