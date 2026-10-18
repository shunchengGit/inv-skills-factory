# 主估值与诊断指标协议

## 唯一机器策略

`scripts/scoring_rules.json` 的policy规定：metric_voting=false、automatic_action=false、safety_margin=scenario_review，固定周期折扣及强制峰值乘数为空。其余指标区间仅供诊断与兼容，不构成整体评级或动作。

## 一主一辅

选择一个符合企业经济结构的主估值，另一个辅助方法只查矛盾，不投票、不平均。PEG、价格/历史估值分位、卖方目标价只作背景，不能充当主估值或辅助价值认证。

没有核验主估值与情景输入时，脚本输出diagnostic，conclusion与action_reference为空。数据齐全不是研究已完成；verified字段是调用方核验声明，程序只验证结构，不证明经济真实性。

## 可选标签与程序边界

五档 conclusion 可缺省/null，不是就绪必需输入；有标签时只作展示。confidence 不再由诊断评级计数，程序不认证研究置信度。辅助 assessment 可有分歧，非 consistent 必须填写 explanation（分歧根源、采用理由及风险）；不要求人为凑一致。

终值折让输出名为 terminal_value_discount_pct，旧 margin_of_safety_pct 仅兼容读取，不等于当前内在价值安全边际。动作空值表示估值与QARP资本配置分离，不等于估值门禁失败。

默认只请求核心 all；日线、公告、调研显式按需。缺口 scope=background 只作背景披露，未标记则保守作为 core。核心快照 upstream_status=failed 阻止主估值；其他上游 partial、fallback 或未标背景的缺口使已核验主估值仅为 partial，不会自动删除主估值。价格/币种或主估值结构缺失仍不能放行。比较按输入顺序列核验主估值三情景、来源/日期/币种/期限；不同经济结构和风险不能机械排名。

## 三情景

保守、基准、乐观使用同一币种、估值日和期限；说明正常化盈利/现金流、资本需求、股数稀释、终值倍数与实际可收分配。每个参数有来源或明确自建假设，不能为满足目标回报反向挑参数。

区分今天内在价值与未来退出价值：未来退出价值不能直接当当前安全边际。程序总回报=((value_per_share+cash_distributions)/current_price-1)*100；年化=(((value_per_share+cash_distributions)/current_price)^(1/years)-1)*100。cash_distributions 是全期限累计每股分配，按期末归集，无再投资或现金流时点折现，不等于IRR。税费、汇率和稀释不自动处理，须在输入口径与 assumptions 中注明；需精确回报时另做带日期现金流核算。terminal_value_discount_pct=(1-current_price/value_per_share)*100，仅比较现价与未来终值。

安全边际通过保守情景、价值区间宽度和不利情景生存能力解释，不叠加统一行业折扣或分歧惩罚。五档标签只能是人工核验主估值的展示，不映射买卖。

## 公司类型

- 稳态非金融：正常化盈利或可持续现金流为主，辅助方法核查再投资与资产。
- 银行：普通股权益、可持续ROE与资本约束，不套制造业FCF门槛。
- 周期制造：正常化盈利及资产负债表，不把峰值低PE当便宜。
- 分部差异显著：必要时SOTP，防现金、投资和新业务重复计价。

## 兼容保留

本轮不删除 scoring_rules.py 加载器及 scoring_rules.json 旧 ranges/pe_ranges_by_type/阈值导出：报告仍导入 EARNINGS_GROWTH_HIGH/LOW，其他公开常量的外部消费者未穷尽验证。旧区间不再进入 build_metric_views 的评级、整体结论、排序或交易动作。confidence、MetricView.rating、action_reference 字段及 sort_rows 接口保留结构兼容，分别输出未评定、null、null及原输入顺序；旧 margin_of_safety_pct 只在主估值渲染兼容读取。

## 数据门禁

upstream_failed/insufficient_for_valuation不可评级；partial显式受限。核验来源、日期、单位、币种及利润口径，缺项不得补造。动作始终交由QARP资本配置协议结合组合与机会成本判断，不由估值脚本自动输出。
