# 外资研报分析工作流（美股/港股/非 A 股标的）

## 适用场景

当用户要求分析美股/港股标的，且本地研报库中有外资研报 PDF（英文文件名）时。

## 数据获取优先级

1. **inv-stock-data**：先尝试 `snapshot` → 若失败，依次尝试 `financial` + `profile`（不同端点限流粒度不同）
2. **inv-stock-data financials**：当 CLI snapshot 全失败时，`cs_stock_info.py financials` 可获取利润表/资产负债表/现金流量表，从三表中可提取核心财务数据
3. **网页抓取**：Agent WebFetch 抓取指定 URL → Markdown/文本

## 研报提取注意事项

- 外资研报文件名通常为英文，`--contains 中文名` 可能匹配不到
- 应同时尝试：`--code 2330`（代码）+ `--contains TSMC`（英文名）
- 无日期前缀的文件需 `--within-days 0 --include-undated`
- 外资研报正文为英文，extract 输出也是英文，分析时需翻译关键数字和观点

## 网络信息补充

当本地研报时效性不足或缺少关键事件时，通过 Agent WebFetch 抓取补充：
- 最新季度业绩（营收、毛利率、EPS vs 预期）
- 重大事件（客户变动、竞争格局变化、政策影响）
- 分析师最新评级和目标价调整

## 输出结构

按研报技能标准模板输出，但增加「网络增量信息」节，明确标注哪些信息来自网络而非研报，并标注数据时点。
