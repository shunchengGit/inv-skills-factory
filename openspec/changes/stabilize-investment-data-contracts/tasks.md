## 1. 契约模型与测试基线

- [ ] 1.1 在 `inv-stock-data/scripts/` 新增无网络依赖的 v1 envelope 构造与验证模块，定义 status、symbol、source、gap、window 和 component 结构
- [ ] 1.2 为 A 股、港股、美股、ETF 建立最小匿名 fixture，覆盖 ok、partial、failed 与 fallback 响应
- [ ] 1.3 新增数据层 contract tests，验证统一 envelope、结构化 gap、来源追踪和未知/非法状态拒绝

## 2. 数据层生产者迁移

- [ ] 2.1 将 snapshot 命令迁移到 v1 标准字段，修复 ETF NAV 字段映射并为四类市场补齐 data_as_of、sources 和 gaps
- [ ] 2.2 修复港股日线 DataFrame fallback 的布尔判断，并记录 Yahoo 失败与降级源成功状态
- [ ] 2.3 为 daily CLI/命令增加 `period` 与可选 `limit`，传递到抓取层并返回实际 observations、first_date、last_date
- [ ] 2.4 实现 52 周、250 日和 5 年指标的观测数及日期覆盖门槛，样本不足时返回 null 和结构化 gap
- [ ] 2.5 将 financial、financials 和其余公开命令迁移到统一 envelope，确保 failed 结果没有伪造事实值
- [ ] 2.6 将 `all` 固定为 snapshot、financial、financials 三组件，提供组件级状态并正确汇总外层 partial/failed
- [ ] 2.7 更新 JSON/text 渲染与 CLI 退出码，使 ok、partial、failed 可由调用者稳定判定
- [ ] 2.8 扩展数据层测试，覆盖五年请求不被截为 20 条、20 条输入不生成长期指标、all 部分成功及四市场 smoke fixture

## 3. 估值消费方与就绪门禁

- [ ] 3.1 为 `inv-valuation-engine` 新增薄 adapter，解析 v1 envelope 并拒绝不支持的 major schema，移除对旧 payload 的散落读取
- [ ] 3.2 修改 A 股与港美股 Snapshot 构建流程：按契约读取 `all` 三组件，并显式请求 daily、announcements、relations 等非聚合数据
- [ ] 3.3 让估值历史计算使用上游 window 和门槛，删除短窗口 `hist_5y` 静默退化路径
- [ ] 3.4 实现 `ok`、`partial`、`insufficient_for_valuation`、`upstream_failed` 状态机及最小评级条件
- [ ] 3.5 修改报告生成：不可评级时 conclusion/action 均为空，partial 时 action 为空，所有格式展示上游状态、时点、来源和 data gaps
- [ ] 3.6 新增估值离线测试矩阵，覆盖上游全失败、仅价格、部分财务、完整数据、20 条历史及完整五年历史

## 4. 五力消费方迁移

- [ ] 4.1 为 `inv-porter-five-forces` 新增 v1 adapter，映射标准公司、行业、价格和 fundamentals 字段并拒绝未知 major schema
- [ ] 4.2 删除港美股对旧 `quote`、`yahoo_fundamentals`、`stats_52w`、`earnings` 和 `news` 路径的依赖
- [ ] 4.3 将上游 status、data_as_of、sources、gaps 和 fallback 状态透传到五力结构化底稿
- [ ] 4.4 根据现有 Porter 框架确定每个力的最低证据条件，实现 evidence_count、confidence、gaps 和可空 score，证据不足时不生成默认总分
- [ ] 4.5 新增五力离线 contract tests，覆盖 A/H/US 映射、partial/fallback、未知版本和证据不足路径

## 5. 下游规则与文档同步

- [ ] 5.1 更新 `inv-qarp-strategy` 对估值状态的门禁：不可评级时要求补数/手工情景，partial 时显著降置信度且不转换为自动买入动作
- [ ] 5.2 更新 `inv-stock-data`、`inv-valuation-engine`、`inv-porter-five-forces` 和 `inv-qarp-strategy` 的 SKILL/references，记录 v1 schema、all 范围、历史窗口和失败语义
- [ ] 5.3 全仓搜索并移除旧字段路径、旧 `all` 组成假设及把短窗口称为 5 年数据的文档或代码

## 6. 验证与交付

- [ ] 6.1 运行全部新增离线测试、现有 knowledge-curator unittest 和技能 linter，修复所有由本变更引入的错误
- [ ] 6.2 在代理条件允许时分别执行 A 股、ETF、港股、美股的 snapshot/daily/all 可选 smoke test，核对 envelope 与实际窗口；网络失败只记录，不替代离线验收
- [ ] 6.3 验证估值与五力代表性 CLI 对 ok、partial、failed 输入均产生符合规格的状态、退出码和缺口输出
- [ ] 6.4 同步受影响 Skill 版本并检查 OpenSpec artifacts、实现 diff 和测试覆盖一致后，准备归档
