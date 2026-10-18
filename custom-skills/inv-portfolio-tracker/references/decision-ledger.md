# 决策台账协议

## 单写入边界

运行 `python3 -B {baseDir}/scripts/decision_ledger.py --help`。默认只用默认profile的 `~/.hermes/memories/investment-decisions/ledger.sqlite3`；测试必须显式 `--db` 临时路径。不得复制股数/现金。PORTFOLIO仍负责真实持仓和成交，报价刷新脚本原样保留。

- `init`：schema user_version=1；不支持版本拒绝，不能静默升级。
- `apply --json '{"key":"唯一操作key","records":[...]}'`：BEGIN IMMEDIATE单事务；完全相同key重试不改库，不同payload拒绝；记录只追加，版本连续且主键唯一。events记录完整批次和落盘时间。同批次按数组顺序校验并插入：后面的 issue/research 可以引用前面已插入但未提交的 evidence，不能引用尚未插入的后续记录；任何一条失败整批回滚。
- `audit`：mode=ro一致性快照，JSON研究队列/缺口/conditions/证据有效状态及integrity；不联网、不更新研究。**输出较大时不要`| python3 -c "..."`管道解析**——终端安全扫描把"pipe直接喂给interpreter"当高风险模式拦截审批，无人值守会挂起超时。改为先`> /tmp/xxx.json`落盘，再用`execute_code`/`read_file`读取解析。
- `render`：只读生成简洁 Markdown 到 stdout，展示结论、重要未知、关键变量、下一复核、未决 issue 与提醒/暂停冲突；不默认倾倒全部来源 JSON。`render --details` 追加每个研究标的全部实体的最新版本完整记录，不是全部历史版本导出。两者均不联网、不改数据库；调用方以临时文件+原子 replace 更新 CURRENT.md，不双写旧档案/观察表。

## schema v1

records(kind,id,version,symbol,payload JSON)，主键(kind,id,version)；events(key,payload,created)，key唯一。公共字段kind/id/symbol/version必须提供，version从1连续增加。实体kind：

- evidence：source、date（未知为null）、basis口径、status=historical/unknown/anomalous/upstream_failed/verified/invalidated。verified须实际日期；币种/单位写入basis，不得猜。
- assumption：text、source；版本保留，不倒填历史买入理由。
- research：status=unknown/partial/needs_review/decision_ready；evidence_ids引用同标的核验证据；reviewed_through仅在真实研究覆盖事件后填写。
- condition：purpose=reminder、metric、source、status、line；变更必须提供supersedes=上一版本，否则审计暂停。历史冲突须issue，不能机械选择新价线。588000暂停。
- decision：stage=suggestion/user_confirmed/executed；后两者必须confirmation_source；执行另需execution_source。记录来源引用，不同步持仓，不代替券商成交；真实成交无卡照样记账。
- issue：status=open/closed、impact、next_action；关闭须closure_evidence_ids，影响结论仍needs_review。
- event：event_type=financial_report/material_risk、source、date真实公告/事件日期；受影响旧证据 effective_status=invalidated；未知日期不录事件，不编下次财报日期。日期、类型、范围在同一 event ID 的后续版本中不可变。
- quote：独立source/date/status，不更新research。audit不自动比较价线，evaluation保守unknown，不能误报未触发。

## 新研究/决策卡 v3（物理 SQLite schema 仍为 v1）

新研究使用一张 `kind:research, protocol_version:3` 卡；不拆每段 evidence，不要求外部反方、双来源、来源类型数量或五分类 readiness。来源可以是原文链接，也可以是报告绝对路径及其来源列表定位；同一份原文足够支撑时不为填配额检索。一次输入：

```bash
python3 -B {baseDir}/scripts/decision_ledger.py --db <明确的台账路径> apply --file <卡片JSON绝对路径>
```

`--file` 与 `--json` 互斥，读取 UTF-8 批次。示例仅展示格式，所有事实、日期、单位、责任人与结论必须来自实际研究，不得原样认证生产标的：

```json
{"key":"example-review-1","records":[{"kind":"research","id":"EXAMPLE","symbol":"EXAMPLE","version":1,"protocol_version":3,"status":"partial","owner":"实际负责核验的人","card":{"sources":[{"source":"/absolute/report.md#来源列表","date":"2026-09-25","locator":"原文p.4或报告来源条目","excerpt":"实际原文摘录","units":"原文单位/币种，无数值时注明不适用","basis":"财报原文口径","status":"verified"}],"facts":"已核验事实及期间","assumptions":"决定价值的关键假设，与事实区分","opposition":"最强反对理由或检验结果，无需外部机构反方","valuation_basis":"估值口径、期间、单位与假设，不用价格位置代替","conclusion":"当前判断","review_conditions":"财报/经营变量/治理风险等复核条件","important_unknowns":["仍未解决的重要经济未知"]}}]}
```

`important_unknowns` 用列表明确披露；未解决的重要未知非空不能写 `decision_ready`。有未知先写 partial/needs_review，而非把每栏填满就称研究通过。申请就绪时需要上述实质内容、owner、非空来源及已核验日期/单位/原文位置/摘录，重要未知为实际核验后的空列表；不能靠占位词或更新日期认证。脚本只检查结构，不能识别被隐瞒的经济未知或证明真实性，人工承担责任。

旧 evidence 的异常、unknown、upstream_failed、invalidated、异常口径或事件失效，未关闭 issue、未版本复核的 closed issue、暂停/冲突 condition 仍阻止新卡就绪，不能切 v3 绕过。实际复核后追加合法新版本，保留旧记录。新 financial_report/material_risk 事件使研究 needs_review；重新就绪需受影响来源重新核验并 reviewed_through 覆盖事件，未受影响来源保留原核验依据。报价更新不是研究。

卡片 conclusion 是判断唯一写入源；JUDGMENTS 停止手写，历史保留不覆盖。`render` 可生成新的只读判断视图（CURRENT.md 或新文件），不回写历史 JUDGMENTS。卡片研究结论不是用户确认或成交；实际建议/确认/成交阶段继续用 decision 引用精确研究版本，真实成交只在 PORTFOLIO 记持仓/现金，台账仅记录来源，不执行或重复记账。

## 事件范围与增量复核

- event 可提供 `affected_evidence_ids`（证据实体 ID）和/或 `affected_propositions`（受影响命题 ID）；evidence 和卡片 `sources` 可提供 `proposition_ids`。这些字段一旦提供必须是非空、无重复、每项为非空字符串的列表；字符串、空列表、空白、非字符串及重复项均拒绝，失败整批回滚。不自动修正 ID。
- 同标的事件匹配证据 ID 或命题交集，两个范围取并集。完全未提供范围保守影响所有来源。提供命题范围而来源没有 `proposition_ids`，仍按受影响处理；提供证据 ID 范围而卡片来源没有明确 `evidence_id`，也保守待核，不能用来源自定义 `id` 冒充证据映射。来源 `evidence_id` 一旦提供必须为非空字符串；映射的经济真实性由人工核验。
- `date` 是原文发布日期，不能为了复核更新；`verified_on` 是实际重新核验日期，可写在 evidence 或卡片来源，必须为规范 ISO 日期且不早于原文 `date`。受影响来源以 `verified_on`（没有时回退 `date`）与事件日期比较：早于事件则失效，真实同日或更晚核验才可恢复。不得仅改日期认证。无需按90/120天机械重写历史事实。
- event 的 `date` / `event_type` / 两个范围字段在后续版本不可变（也不能把未知范围补成窄范围，或删除已有范围）；新发现的另一个事件用新 ID。`reviewed_through` 只表示研究实际覆盖到哪些事件，不能替代来源复核，也不能解除异常证据、未决 issue 或暂停条件。
- 未受影响证据保持原日期与状态；受影响证据追加新版本或卡片来源实际复核后追加 research 新版本。原始研究和事件保留。脚本只检查结构与日期关系，不证明命题范围完整或原文真实。

## 旧研究就绪协议 v2（仅兼容，不作为新卡配额）

旧式 `research.status=decision_ready` 使用显式 `protocol_version:2`。`evidence_ids` 为同标的已落库、最新版本有效的证据 ID；另提供 `readiness`，键恰为 `original`、`independent`、`contrarian`、`valuation`、`portfolio_comparison`，每项为非空证据 ID 数组，均须属于 `evidence_ids`。所引用证据需 verified、日期、原文 excerpt 与 locator、非异常口径，且分别提供 `evidence_type`（上述类别；independent 对应 supporting）与 `source_group`。独立支持证据至少有一个 `source_group` 不同于原文组；同机构/同底层共享来源不能标成独立。反方、估值与组合机会成本分别要有对应证据，不用价格区间冒充估值。分类与独立性仅作结构检查，人工仍须核验原始内容与经济判断。原有无 protocol_version 的记录照旧读取、版本续写，但旧 `decision_ready` 审计为 needs_review；不静默升级、也不自动将七个生产研究标的设为就绪。

新增或续写的 `issue.status=open`（包含未标 v2 的调用）须有 `owner`、ISO 日期 `due`、`next_event`（可观察的下一事件），审计 gaps 会列出三字段；既存 v1 issue 保持可读。无法合理承诺复核日期时不要编造，先维持既存 issue 并由人工确定跟进安排。新增 `decision` 的 suggestion/user_confirmed（含未标 v2 的调用）须引用当前同标的 `research_id` 与整数 `research_version`；更新研究后建议须重发以绑定新版本。executed 是实际成交记账，可在无研究记录时仅凭 confirmation_source 与 execution_source 写入；若显式附加研究引用也必须有效。`protocol_version` 接受 1/2/3，不改变 SQLite user_version=1、旧主键、事件和真实成交来源。

## 门禁与边界

缺证据、异常增长PEG、价格位置冒充估值、未解决问题/暂停条件不能认证decision_ready。新财报按上述范围失效受影响旧证据，缺范围保守处理；90/120天不再是fresh认证。程序验证字段结构和状态，不证明经济判断正确；保留原文核验、最强反对理由或检验结果及实际相关的组合约束，不用来源数量代替判断。独立突发风险能启动研究，USER.md是唯一约束。未知不补造。

当前最小闭环不接网络、不交易、不投递；事件发现和证据经济真实性需人工/研究流程输入。关闭影响评级的issue后维持needs_review，重新认证需明确处理旧问题影响；不能靠更新日期全绿。完整周度运行、消息去重投递尚待真实周期验证。

## 迁移与回滚

先备份每个个人文件及源码，manifest记原路径/备份路径/SHA256；读取真实PORTFOLIO代码集，历史材料标historical，不复制持仓量。迁移后比较当前持仓、现金和调仓章节字节，7/7覆盖只表示档案覆盖，不是研究通过。旧档案封存，JUDGMENTS历史保留并停止手写，新判断只写台账。

回滚先停止写入并另备份现状，按manifest逐个恢复本轮更改个人文件；保留JUDGMENTS历史，回滚说明另记归档日志而非改写历史判断。源码只逆转本轮diff，不git reset覆盖别人未提交修改；新数据库/生成文件另存归档，不删除证据。全量周度观察未发生不得称通过。
