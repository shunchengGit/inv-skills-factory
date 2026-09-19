# 可复现候选发现与机构覆盖证据

## 能力边界（2026-09-06源码核对）
inv-stock-data/scripts/cs_stock_info.py 只有按证券查询的 snapshot/profile/daily/financial/financials/all/description/announcements/relations 及 index-daily。fetch_ashare.py 内部读取A股名称列表后只返回指定代码，不是公开全市场筛选入口；index-daily 是指数行情，不是成分股列表。当前没有已验证的全市场扫描器、跨市场筛选CLI或机构研究覆盖计数器。不得将内部函数、Yahoo分析师人数/共识字段说成已实现的覆盖门禁。

复用已有公共CLI核实选定证券身份、行业、财务/估值和公告；A股 relations 只作调研线索，参与机构名单不能自动算研究覆盖。行情/财务严格走inv-stock-data及其规定降级，不在本技能增AkShare/yfinance/行情接口或批量跨市场抓取器。候选名册和公开研究文献可用web工具采集，二者不是新增行情接口。

## 分层入口与轮换
1. **基底名册**：优先指数公司/交易所官网公布的沪深300、中证500、恒生综合大中型、S&P 500、Russell 1000等成分名单（例子不是要求全部下载）。可用追踪指数的基金官网持仓文件补充，但注明跟踪误差、日期及不完整性。每周至少复核名册版本；名册只是发现入口，指数身份、高市值、高流动性均不证明机构研究充分。若用流动性过滤，必须有数据层可得的实际指标、日期和阈值，否则不能声称已筛选。
2. **机构覆盖入口**：公司IR analyst coverage名录、券商官网公开公司报告/业绩点评、可合法访问的研究摘要或评级行动原文。跨机构行业专题中的公司只有存在实质公司分析才可纳入。IR名单无研究日期只能提供待查机构，不能直接通过。公开摘要足够核验时不要求购买付费全文。
3. **事件补充**：最新财报/公告、非热门行业公开研究、本地知识库线索；新发现公司仍需同一道覆盖门禁。新闻热度、熟悉度和知识库库存不决定入池资格。陌生不等于差，但用户不研究小众标的，不为发现数量降低门槛。

每轮至少尝试两个不同类型入口，不是同一榜单两面镜像；主列表按市场、行业、代码稳定排序，使用持久游标接续，不能只挑AI搜索想到的名字。每周先选上周最少覆盖市场/行业；并列按A/H/美及行业名称排序。主行业不得连续两天相同；无法满足如实记录，不编造配额。来源打不开可换同类官方入口，再用已存名册（明示陈旧程度）；仍不足则仅研究已核验池，标注降级，不宣称扫描全市场。

## 机构覆盖前门槛
- 截至当轮上海日期，滚动近12个月（按日历周年，闰日取2月28日）至少 **3家独立机构集团**有可核实的、具日期的实质公司研究。
- 最新财报公布后尽量核实至少 **2家独立机构集团**更新；记录实际数量。满足12个月3家但财报后不足2家，仅在财报内容已用官方来源核对且缺口/原因明确时可继续初筛，不能写成“财报后已充分覆盖”。最新财报日期未知则coverage=unknown，先补证，不进入daily QARP研究。
- 实质覆盖：公司财务预测、盈利变化、估值假设、竞争地位或风险论证之一有可读具体内容。只有目标价/评级数字、搜索片段、机构持股/13F、调研出席、新闻转引、券商销售转发、未注明日期的分析师名单均不够。公开具名具日摘要/评级行动说明若含上述论证可算，不要求全文付费访问。
- 按最终机构集团统一group_id；同集团子公司/不同分析师只算一家，同篇报告被多家媒体转载只算原机构一家。无法确认集团独立性或日期/内容时不计数并记缺口。原文与镜像不构成两个来源。
- 每条计数证据保存机构名、group_id、发布日期、报告标题、原始URL（有转引另存转载URL）、实质论点摘录/页码、核实日期。计数必须能从这些证据重算，不靠LLM声称或分析师人数推定。
- coverage状态：verified（达到硬阈值且最新财报日期已核实）、insufficient（可核实机构不足3家）、unknown（证据无法核实）。后两者留发现池待补证，不自动记screen_reject/hard_reject，不等于公司质量差。30天后或新研究/财报事件再检查，防止占满daily额度；证据过期或新财报出现即重算。

## 先池后筛与文件契约
无需改SQLite结构或重写历史结论。ledger.py已原样保存附加JSON字段；发现池是**未研究线索**，不等于台账stage=candidate（后者仅初筛通过）。

每周刷新、daily开始续读 ROOT/universe/YYYY-MM-DD.json（同日续写，保留旧版），字段：
- schema_version="1.0"，as_of（上海日期），universe_scope（实际名册/市场范围，不写“全市场”），limitations数组。
- sources数组：source_id、channel（roster/research/event/library）、url或绝对本地路径、published_at或null、retrieved_at、snapshot_path、查询词或抓取步骤、列表范围/页码、raw_count、实际读取count、是否完整。原文件存 ROOT/universe/sources/；不能将抓取日期冒充名册日期。
- selection：本轮市场/行业、排序键、各source_id的cursor_before/cursor_after、每渠道预先声明处理上限（默认20个名字）、过滤规则/参数、跳过公司及理由。下一轮从游标接续；源版本更换时记录旧新版本映射/游标重置理由。
- companies数组：company_id、name、aliases、market、industry、discovery_source_ids、first_seen、last_coverage_checked、next_coverage_check、coverage对象、selection_status（pending/coverage_hold/eligible/cooldown/holding/selected）、reason。先统一A/H/ADR公司身份再计数量。

coverage对象：as_of、status、latest_earnings_at、latest_earnings_source、evidence数组（上述逐条字段）、independent_groups_12m数组、independent_groups_post_earnings数组、gaps数组、post_earnings_exception（不足2家时的官方核对及理由，否则null）。数组是可追溯计数结果，不是代理自填的替代证据。

每日顺序：续读/补齐名册 → 公司去重及持仓/冷却check → 按固定顺序补机构证据 → 保存候选池及计数 → 只从coverage=verified且check允许的公司选择目标5–8家 → 调数据层QARP轻筛。额度不足就少做或零家，不跨过门槛凑5家。一次snapshot、一次覆盖核查和一次完整初筛要分别计数。

每份新研究记录附加discovery={universe_path, source_ids, selection_reason}及coverage对象；写record前再次核实覆盖有效、check允许。旧记录无这些字段仍可读，视为legacy未认证；以后实际再研究时补新记录，不批量覆盖旧payload或改变历史结论。weekly旧candidate/partial也先过当前覆盖门槛，再决定是否投入深研。

## 验收
- 从保存名册、查询/日期、游标、规则可复现本轮考察顺序；run中记名册读取数/去重后数/覆盖核查数/verified数/完成初筛数，不能混用。
- 逐家公司重新按证据日期过滤和group_id去重，核对12个月及财报后计数；URL、发布日期、实质论据缺一不计数。机构归属和内容真实性仍需人工/代理查原文，不声称脚本已自动认证。
- 实际下载不足或只取前20条就写该范围；本次仅修技能并不等于候选池已建立或市场已扫描。
- 机构覆盖充分只是用户研究范围门槛，不是安全性、便宜或可买认证；QARP、反方证据、独立估值及与持仓/现金比较不变。
