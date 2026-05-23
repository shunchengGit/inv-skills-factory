"""腾讯控股前置指标 — 指标配置。

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
    # ── Tier 1：收入端（游戏）──────────────────────────────────────────
    "retail_sales": {
        "key": "retail_sales",
        "name": "中国社会消费品零售总额",
        "direction": "revenue",
        "weight": 0.12,
        "unit": "亿元",
        "data_method": "script",
        "handler": "macro",
        "transmission_summary": "社零总额是消费大盘温度计，反映居民消费意愿。腾讯广告收入与消费景气度高度正相关。",
        "scoring_guide": "社零同比>6%=强势，3-6%=中性，<3%=弱势",
        "tier": 1,
        "threshold": {"bearish": 3, "bullish": 7},
    },
    "top_games_ranking": {
        "key": "top_games_ranking",
        "name": "腾讯手游畅销榜排名",
        "direction": "revenue",
        "weight": 0.15,
        "unit": "名",
        "data_method": "script",
        "handler": "ranking",
        "transmission_summary": "手游畅销榜排名是游戏收入的高频代理指标。多款游戏进入 Top 10 说明产品组合强势。",
        "scoring_guide": "3+款入Top10=强势，1-2款=中性，0款=弱势",
        "tier": 1,
        "threshold": {"bearish": 0, "bullish": 3},
    },
    "southbound_flow": {
        "key": "southbound_flow",
        "name": "南向资金净流入",
        "direction": "capital_flow",
        "weight": 0.10,
        "unit": "亿港元",
        "data_method": "script",
        "handler": "macro",
        "transmission_summary": "南向资金是港股定价权的重要力量。持续净流入腾讯说明内地资金看好，反之则承压。",
        "scoring_guide": "近5日净流入>50亿=强势，-20~50亿=中性，<-20亿=弱势",
        "tier": 1,
        "threshold": {"bearish": -20, "bullish": 50},
    },

    # ── Tier 2：收入端（广告/金融）───────────────────────────────────────
    "game_approval": {
        "key": "game_approval",
        "name": "游戏版号审批",
        "direction": "policy",
        "weight": 0.10,
        "unit": "",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "游戏版号是新产品上线的必要前提。版号发放节奏加快意味着未来新游供给增加，利好收入增长。",
        "scoring_guide": "腾讯近3月获版号≥2个=利好，1个=中性，0个=利空",
        "tier": 2,
        "search_hint": "搜索国家新闻出版署最新游戏版号审批公告，查看腾讯获批数量",
    },
    "wechat_video_usage": {
        "key": "wechat_video_usage",
        "name": "微信视频号使用数据",
        "direction": "revenue",
        "weight": 0.10,
        "unit": "",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "视频号是腾讯广告增长新引擎，使用时长和创作者数量是关键增长指标。视频号广告加载率仍在提升阶段。",
        "scoring_guide": "视频号使用时长同比>50%=强增长，20-50%=稳健，<20%=放缓",
        "tier": 2,
        "search_hint": "搜索微信视频号最新使用数据（使用时长、创作者数量、广告收入增速）",
    },

    # ── Tier 3：金融科技 ──────────────────────────────────────────────
    "wechat_payment": {
        "key": "wechat_payment",
        "name": "微信支付市场份额/交易额",
        "direction": "revenue",
        "weight": 0.08,
        "unit": "",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "微信支付是金融科技板块核心收入来源。支付笔数和 GMV 增速反映商业支付健康度。",
        "scoring_guide": "商业支付GMV同比>15%=强增长，5-15%=稳健，<5%=放缓",
        "tier": 3,
        "search_hint": "搜索微信支付最新交易数据或市场份额（商业支付GMV增速）",
    },

    # ── Tier 3：宏观/政策 ──────────────────────────────────────────────
    "internet_policy": {
        "key": "internet_policy",
        "name": "互联网监管政策动向",
        "direction": "policy",
        "weight": 0.08,
        "unit": "",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "互联网监管政策是影响腾讯估值的关键外部因素。政策放松提升估值空间，收紧则压缩估值。",
        "scoring_guide": "明确放松信号=强利好，维持现状=中性，收紧信号=利空",
        "tier": 3,
        "search_hint": "搜索中国互联网行业最新监管政策动向",
    },
    "cloud_market": {
        "key": "cloud_market",
        "name": "中国云计算市场规模/增速",
        "direction": "revenue",
        "weight": 0.07,
        "unit": "",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "腾讯云是第二增长曲线，市场规模和增速决定其收入天花板。腾讯云市占率变化反映竞争格局。",
        "scoring_guide": "云市场同比>30%=高景气，15-30%=稳健，<15%=放缓",
        "tier": 3,
        "search_hint": "搜索中国云计算市场最新规模和增速数据（IDC/信通院报告）",
    },
    "gaming_market": {
        "key": "gaming_market",
        "name": "全球游戏市场规模/增速",
        "direction": "revenue",
        "weight": 0.10,
        "unit": "",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "全球游戏市场增速是腾讯游戏业务的天花板指标。新兴市场（拉美、中东）是增量来源。",
        "scoring_guide": "全球游戏市场同比>5%=扩张，0-5%=平稳，<0%=收缩",
        "tier": 3,
        "search_hint": "搜索Newzoo或Sensor Tower最新全球游戏市场规模及增速预测",
    },
    "ai_progress": {
        "key": "ai_progress",
        "name": "腾讯AI进展（混元大模型）",
        "direction": "growth",
        "weight": 0.10,
        "unit": "",
        "data_method": "agent_search",
        "handler": "agent_search",
        "transmission_summary": "AI能力是腾讯未来竞争力的核心变量。混元大模型进展、AI应用落地速度决定长期估值溢价。",
        "scoring_guide": "重大突破/开源=强利好，持续迭代=中性，落后竞品=利空",
        "tier": 3,
        "search_hint": "搜索腾讯混元大模型最新进展（版本更新、能力评测、应用落地）",
    },
}
