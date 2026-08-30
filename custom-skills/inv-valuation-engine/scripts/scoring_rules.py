"""估值评分的唯一代码来源（脚本实际执行的阈值）。

与 `references/scoring-rules.md` 保持一致：md 是给人读的权威细则文档，
本模块是脚本机器执行的阈值常量。改动任何阈值必须**同步两处**，避免漂移。

区间格式统一为 `[(lower, upper, rating), ...]`，`lower`/`upper` 为 `None` 表示
无界；判断规则为 `lower <= value < upper`（右开区间），见
`valuation_report.metric_rating_by_ranges`。
"""

from __future__ import annotations

# 五档区间类型：[(lower, upper, rating), ...]
Ranges = list[tuple[float | None, float | None, str]]

# PEG（对应 scoring-rules.md「通用定量指标标准」PEG 行）
PEG_RANGES: Ranges = [
    (None, 0.6, "低估"),
    (0.6, 0.8, "合理偏低"),
    (0.8, 1.2, "合理"),
    (1.2, 1.5, "合理偏高"),
    (1.5, None, "高估"),
]

# 历史 PE/PB 分位（对应 scoring-rules.md「历史PE/PB分位」行）
PERCENTILE_RANGES: Ranges = [
    (None, 20, "低估"),
    (20, 30, "合理偏低"),
    (30, 70, "合理"),
    (70, 90, "合理偏高"),
    (90, None, "高估"),
]

# PS（成长股）（对应 scoring-rules.md「PS（成长股）」行）
PS_RANGES: Ranges = [
    (None, 2, "低估"),
    (2, 4, "合理偏低"),
    (4, 8, "合理"),
    (8, 15, "合理偏高"),
    (15, None, "高估"),
]

# 盈利收益率 = 1/PE，用于和债券/股息收益率对照（对应「隐含年化收益率」的收益侧）
EARNINGS_YIELD_RANGES: Ranges = [
    (8, None, "低估"),
    (6, 8, "合理偏低"),
    (4, 6, "合理"),
    (2.5, 4, "合理偏高"),
    (None, 2.5, "高估"),
]

# 分析师目标价上行空间
ANALYST_UPSIDE_RANGES: Ranges = [
    (20, None, "低估"),
    (10, 20, "合理偏低"),
    (0, 10, "合理"),
    (-10, 0, "合理偏高"),
    (None, -10, "高估"),
]

# 各行业 PE 锚五档区间；key 对应 infer_company_type 的映射值。
# 对应 scoring-rules.md「行业参数参考」PE 合理区间，并扩展为五档。
PE_RANGES_BY_TYPE: dict[str, Ranges] = {
    "消费/医疗": [
        (None, 16, "低估"),
        (16, 20, "合理偏低"),
        (20, 30, "合理"),
        (30, 35, "合理偏高"),
        (35, None, "高估"),
    ],
    "互联网/软件": [
        (None, 12, "低估"),
        (12, 15, "合理偏低"),
        (15, 40, "合理"),
        (40, 50, "合理偏高"),
        (50, None, "高估"),
    ],
    "半导体/科技制造": [
        (None, 10, "低估"),
        (10, 15, "合理偏低"),
        (15, 35, "合理"),
        (35, 45, "合理偏高"),
        (45, None, "高估"),
    ],
    "周期行业": [
        (None, 5, "低估"),
        (5, 8, "合理偏低"),
        (8, 15, "合理"),
        (15, 20, "合理偏高"),
        (20, None, "高估"),
    ],
    "default": [
        (None, 8, "低估"),
        (8, 10, "合理偏低"),
        (10, 20, "合理"),
        (20, 30, "合理偏高"),
        (30, None, "高估"),
    ],
}

# 股息率分级（成熟型公司：消费/医疗、金融/地产）
DIVIDEND_YIELD_HIGH = 4.0    # >= 4% → 合理偏低
DIVIDEND_YIELD_MEDIUM = 2.0  # >= 2% → 合理；否则 合理偏高

# PB-ROE 代理阈值：pb / roe * 100 < 阈值 → 合理，否则 合理偏高
PB_ROE_THRESHOLD = 15.0

# Forward PE 隐含增速校验：超过该百分比则判定疑似失真，降级用 trailing PE
FORWARD_PE_IMPLIED_GROWTH_LIMIT = 30.0

# 利润增速异常阈值（百分比）：超出范围疑似 GAAP 单季度扭曲
EARNINGS_GROWTH_HIGH = 40.0
EARNINGS_GROWTH_LOW = -30.0
