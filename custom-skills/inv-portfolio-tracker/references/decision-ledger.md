# 决策台账协议

## 单写入边界

运行 `python3 -B {baseDir}/scripts/decision_ledger.py --help`。默认只用默认profile的 `~/.hermes/memories/investment-decisions/ledger.sqlite3`；测试必须显式 `--db` 临时路径。不得复制股数/现金。PORTFOLIO仍负责真实持仓和成交，报价刷新脚本原样保留。

- `init`：schema user_version=1；不支持版本拒绝，不能静默升级。
- `apply --json '{"key":"唯一操作key","records":[...]}'`：BEGIN IMMEDIATE单事务；完全相同key重试不改库，不同payload拒绝；记录只追加，版本连续且主键唯一。events记录完整批次和落盘时间。**同批次内不能互相引用**：issue的`closure_evidence_ids`、research的`evidence_ids`等门禁校验只查已落库的`records`，不含本批次内还未commit的记录。新建的证据要先单独`apply`落库，再在下一次`apply`里让issue/research引用它；一次性把evidence和引用它的issue塞进同一个records数组会得到`missing verified evidence`之类的门禁错误。
- `audit`：mode=ro一致性快照，JSON研究队列/缺口/conditions/证据有效状态及integrity；不联网、不更新研究。**输出较大时不要`| python3 -c "..."`管道解析**——终端安全扫描把"pipe直接喂给interpreter"当高风险模式拦截审批，无人值守会挂起超时。改为先`> /tmp/xxx.json`落盘，再用`execute_code`/`read_file`读取解析。
- `render`：只读生成Markdown到stdout，调用方以临时文件+原子replace更新CURRENT.md；不双写旧档案/观察表。

## schema v1

records(kind,id,version,symbol,payload JSON)，主键(kind,id,version)；events(key,payload,created)，key唯一。公共字段kind/id/symbol/version必须提供，version从1连续增加。实体kind：

- evidence：source、date（未知为null）、basis口径、status=historical/unknown/anomalous/upstream_failed/verified/invalidated。verified须实际日期；币种/单位写入basis，不得猜。
- assumption：text、source；版本保留，不倒填历史买入理由。
- research：status=unknown/partial/needs_review/decision_ready；evidence_ids引用同标的核验证据；reviewed_through仅在真实研究覆盖事件后填写。
- condition：purpose=reminder、metric、source、status、line；变更必须提供supersedes=上一版本，否则审计暂停。历史冲突须issue，不能机械选择新价线。588000暂停。
- decision：stage=suggestion/user_confirmed/executed；后两者必须confirmation_source；执行另需execution_source。记录来源引用，不同步持仓，不代替券商成交；真实成交无卡照样记账。
- issue：status=open/closed、impact、next_action；关闭须closure_evidence_ids，影响结论仍needs_review。
- event：event_type=financial_report、source、date真实公告日期；旧证据effective_status=invalidated；未知日期不录事件，不编下次财报日期。
- quote：独立source/date/status，不更新research。audit不自动比较价线，evaluation保守unknown，不能误报未触发。

## 研究就绪协议 v2（物理 SQLite schema 仍为 v1）

新写入的 `research.status=decision_ready` 必须显式 `protocol_version:2`。`evidence_ids` 为同标的已落库、最新版本有效的证据 ID；另提供 `readiness`，键恰为 `original`、`independent`、`contrarian`、`valuation`、`portfolio_comparison`，每项为非空证据 ID 数组，均须属于 `evidence_ids`。所引用证据需 verified、日期、原文 excerpt 与 locator、非异常口径，且分别提供 `evidence_type`（上述类别；independent 对应 supporting）与 `source_group`。独立支持证据至少有一个 `source_group` 不同于原文组；同机构/同底层共享来源不能标成独立。反方、估值与组合机会成本分别要有对应证据，不用价格区间冒充估值。分类与独立性仅作结构检查，人工仍须核验原始内容与经济判断。原有无 protocol_version 的记录照旧读取、版本续写，但旧 `decision_ready` 审计为 needs_review；不静默升级、也不自动将七个生产研究标的设为就绪。

新增或续写的 `issue.status=open`（包含未标 v2 的调用）须有 `owner`、ISO 日期 `due`、`next_event`（可观察的下一事件），审计 gaps 会列出三字段；既存 v1 issue 保持可读。无法合理承诺复核日期时不要编造，先维持既存 issue 并由人工确定跟进安排。新增 `decision` 的 suggestion/user_confirmed（含未标 v2 的调用）须引用当前同标的 `research_id` 与整数 `research_version`；更新研究后建议须重发以绑定新版本。executed 是实际成交记账，可在无研究记录时仅凭 confirmation_source 与 execution_source 写入；若显式附加研究引用也必须有效。`protocol_version` 只接受 1/2，不改变 SQLite user_version=1、旧主键、事件和真实成交来源。

## 门禁与边界

缺证据、异常增长PEG、价格位置冒充估值、未解决问题/暂停条件不能认证decision_ready。新财报覆盖旧证据；90/120天不再是fresh认证。程序验证字段结构和状态，不证明经济判断正确；完整QARP仍要求原文、反方、组合及机会成本。独立突发风险能启动研究，USER.md是唯一约束。未知不补造。

当前最小闭环不接网络、不交易、不投递；事件发现和证据经济真实性需人工/研究流程输入。关闭影响评级的issue后维持needs_review，重新认证需明确处理旧问题影响；不能靠更新日期全绿。完整周度运行、消息去重投递尚待真实周期验证。

## 迁移与回滚

先备份每个个人文件及源码，manifest记原路径/备份路径/SHA256；读取真实PORTFOLIO代码集，历史材料标historical，不复制持仓量。迁移后比较当前持仓、现金和调仓章节字节，7/7覆盖只表示档案覆盖，不是研究通过。旧档案封存，JUDGMENTS仅追加明确替代。

回滚先停止写入并另备份现状，按manifest逐个恢复本轮更改个人文件；保留JUDGMENTS更正日志，追加回滚说明而非删日志。源码只逆转本轮diff，不git reset覆盖别人未提交修改；新数据库/生成文件另存归档，不删除证据。全量周度观察未发生不得称通过。
