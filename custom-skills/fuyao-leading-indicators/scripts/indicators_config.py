"""福耀玻璃前置指标 — 指标配置。

每个指标包含：
- key: 指标唯一标识
- name: 中文名称
- direction: 传导方向分类
- weight: 权重（所有指标之和 = 1.0）
- unit: 度量单位
- data_method: 数据获取方式（"script" | "agent_search"）
- handler: 处理器类型（"kline" | "macro" | "ranking" | "agent_search"）
- transmission_summary: 1-2 句传导机制说明
- scoring_guide: LLM 评分指引
- tier: 层级分组
- threshold: 看涨/看跌阈值（可选）
- search_hint: Agent 搜索建议（仅 agent_search 指标）
"""

INDICATORS: dict[str, dict] = {
    # ── Tier 1：成本端 ──────────────────────────────────────────────
    "soda_ash": {
        "key": "soda_ash",
        "name": "纯碱（重碱）价格",
        "direction": "cost",
        "weight": 0.10,
        "unit": "元/吨",
        "data_method": "script",
        "handler": "kline",
        "transmission_summary": "纯碱是浮法玻璃核心原料，占生产成本约 20%。纯碱涨价直接推高玻璃成本，压缩毛利率。",
        "scoring_guide": "纯碱价格每变动100元/吨，约影响玻璃成本2-3元/重箱",
        "tier": 1,
        "threshold": {"bearish": 2800, "bullish": 2000},
    },
    "natural_gas": {
        "key": "natural_gas",
        "name": "天然气价格（LNG）",
        "direction": "cost",
        "weight": 0.10,
        "unit": "元/吨",
        "data_method": "script",
        "handler": "kline",
        "transmission_summary": "天然气是玻璃熔窑主要燃料，燃料成本占生产成本约 30%。LNG 涨价显著影响盈利。",
        "scoring_guide": "LNG价格每变动500元/吨，约影响玻璃成本3-5元/重箱",
        "tier": 1,
        "threshold": {"bearish": 5500, "bullish": 3500},
    },

    # ── Tier 1：收入端 ──────────────────────────────────────────────
    "auto_sales": {
        "key": "auto_sales",
        "name": "中国汽车销量",
        "direction": "revenue",
        "weight": 0.12,
        "unit": "万辆",
        "data_method": "script",
        "handler": "macro",
        "transmission_summary": "汽车玻璃占福耀收入约 75%，汽车销量是最直接的收入驱动指标。乘用车销量下滑直接压缩福耀订单量。",
        "scoring_guide": "乘用车月销量>220万辆=强势，180-220=中性，<180=弱势",
        "tier": 1,
        "threshold": {"bearish": 180, "bullish": 240},
    },
    "nev_penetration": {
        "key": "nev_penetration",
        "name": "新能源车渗透率",
        "direction": "revenue",
        "weight": 0.08,
        "unit": "%",
        "data_method": "script",
        "handler": "macro",
        "transmission_summary": "新能源车单车玻璃用量更高（天幕玻璃+隔音玻璃），渗透率提升是 ASP 增长核心驱动。",
        "scoring_guide": "渗透率>40%=强利好，30-40%=中性，<30%=弱",
        "tier": 1,
        "threshold": {"bearish": 25, "bullish": 45},
    },

    # ── Tier 2：成本端（国际）─────────────────────────────────────────
    "usdcny": {
        "key": "usdcny",
        "name": "美元兑人民币汇率",
        "direction": "cost_reverse",
        "weight": 0.08,
        "unit": "",
        "data_method": "script",
        "handler": "kline",
        "transmission_summary": "福耀海外收入占比约 45%，人民币贬值提升海外收入换汇后的人民币金额。汇率波动直接影响合并报表利润。",
        "scoring_guide": "USDCNY>7.3=利好出口，6.8-7.3=中性，<6.8=利空出口",
        "tier": 2,
        "threshold": {"bearish": 6.8, "bullish": 7.4},
    },

    # ── Tier 2：宏观/物流 ─────────────────────────────────────────────
    "ccfi": {
        "key": "ccfi",
        "name": "CCFI 出口集装箱运价指数",
        "direction": "cost",
        "weight": 0.06,
        "unit": "",
        "data_method": "script",
        "handler": "kline",
        "transmission_summary": "运价上涨增加福耀海外出口运输成本，尤其是对美国和欧洲市场。但运价高也反映全球贸易活跃。",
        "scoring_guide": "CCFI>1500=运输成本高，800-1500=中性，<800=运输成本低",
        "tier": 2,
        "threshold": {"bearish": 1600, "bullish": 800},
    },

    # ── Tier 2：海外汽车市场 ──────────────────────────────────────────
    "us_auto_sales": {
        "key": "us_auto_sales",
        "name": "美国汽车销量",
        "direction": "revenue",
        "weight": 0.10,
        "unit": "万辆",
        "data_method": "script",
        "handler": "macro",
        "transmission_summary": "美国是福耀最大海外市场（占海外收入约 40%），美国汽车销量直接影响福耀美国工厂产能利用率。",
        "scoring_guide": "美国月销量>130万辆=强势，110-130=中性，<110=弱势",
        "tier": 2,
        "threshold": {"bearish": 110, "bullish": 140},
    },
    "eu_auto_sales": {
        "key": "eu_auto_sales",
        "name": "欧洲汽车销量",
        "direction": "revenue",
        "weight": 0.06,
        "unit": "万辆",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "欧洲是福耀第二大海外市场，欧洲汽车销量影响福耀欧洲工厂订单量。ACEA 月度数据为准。",
        "scoring_guide": "欧洲月销量>100万辆=强势，80-100=中性，<80=弱势",
        "tier": 2,
        "search_hint": "搜索 ACEA 最新月度欧洲汽车注册量数据",
        "threshold": {"bearish": 80, "bullish": 110},
    },

    # ── Tier 3：政策/消费 ──────────────────────────────────────────────
    "cpca_retail": {
        "key": "cpca_retail",
        "name": "乘联会零售销量预估",
        "direction": "revenue",
        "weight": 0.08,
        "unit": "万辆",
        "data_method": "script",
        "handler": "macro",
        "transmission_summary": "乘联会零售数据是汽车终端消费的高频指标，比中汽协批发数据更贴近真实需求。福耀 ASP 与终端零售关联度高。",
        "scoring_guide": "乘联会月零售>180万辆=强势，150-180=中性，<150=弱势",
        "tier": 3,
        "threshold": {"bearish": 150, "bullish": 190},
    },
    "glass_inventory": {
        "key": "glass_inventory",
        "name": "浮法玻璃企业库存",
        "direction": "cost_reverse",
        "weight": 0.08,
        "unit": "万重箱",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "玻璃企业库存是行业供需最直观指标。库存高=需求弱=价格承压；库存低=需求强=涨价可期。福耀作为汽车玻璃厂商，受浮法玻璃价格影响。",
        "scoring_guide": "库存>6000万重箱=严重供过于求，4000-6000=中性，<4000=供不应求",
        "tier": 3,
        "search_hint": "搜索卓创资讯或隆众资讯最新浮法玻璃企业库存数据（万重箱）",
        "threshold": {"bearish": 6000, "bullish": 3500},
    },
    "glass_price": {
        "key": "glass_price",
        "name": "浮法玻璃现货价格",
        "direction": "revenue",
        "weight": 0.08,
        "unit": "元/吨",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "浮法玻璃现货价反映行业定价能力。福耀采购原片玻璃，价格变动影响成本，但福耀对下游有强议价权可传导。",
        "scoring_guide": "价格>2000元/吨=行业景气，1500-2000=中性，<1500=行业低迷",
        "tier": 3,
        "search_hint": "搜索最新浮法玻璃（5mm白玻）全国均价（元/吨）",
        "threshold": {"bearish": 1500, "bullish": 2100},
    },
    "auto_policy": {
        "key": "auto_policy",
        "name": "汽车消费政策动向",
        "direction": "policy",
        "weight": 0.06,
        "unit": "",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "汽车下乡补贴、以旧换新政策、购置税减免等政策直接影响购车意愿，是短中期需求波动的关键变量。",
        "scoring_guide": "重大刺激政策=强利好，延续现有政策=中性，政策收紧=利空",
        "tier": 3,
        "search_hint": "搜索中国最新汽车消费刺激政策（以旧换新补贴、购置税等）",
    },
}
