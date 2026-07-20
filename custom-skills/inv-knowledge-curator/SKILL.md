---
name: inv-knowledge-curator
description: AI投资知识库：3进3出1底座，OKF v0.2。脚本管确定性IO，检索/关联/综合交LLM。用于知识管理、资源分析时
version: 3.2.1
trigger: [知识管理, 收藏文章, 笔记整理, 研报分析, 券商研报, 研报提取, 财报分析, 资源入库, km_init, km_import, km_search, km_lint, km_graph]
commands:
  - /km_init - 初始化知识库（LLM 流程：bash git clone + 建目录）
  - /km_import - 导入：丢链接(LLM用firecrawl抓取→总结→入库) / 丢资源文件(归档→提取→总结→入库) / 记笔记
  - /km_search - 搜（LLM 流程：读 index.md + grep entries + 跟随链接）
  - /km_lint - 健康度检查与修复（脚本）
  - /km_graph - 知识图谱（脚本）
---

# inv-knowledge-curator v3.2

> **3 进 3 出 1 底座。** 扁平存储，frontmatter + 全文检索，不依赖目录层级。
> **脚本/LLM 分工**：脚本只做确定性 IO（git/PDF提取/索引重建/图谱生成/合规校验）；检索、统计、关联发现、综合分析全交 LLM（读 `entries/index.md` + `grep entries/*.md` + 跟随 markdown 链接）。
> **边界**：下游技能默认只读知识库；真正的 `/km_import store|res` 写入、Synthesis 落库、版本递增与刷新由本技能主流程负责。原始 PDF 只读入口统一为 `km_import read --file <res/...pdf> --pages ...`。

## 仓库结构

```
~/.inv-knowledge/
├── entries/                       ← 知识条目（扁平）
│   ├── index.md                   ← 按 type 分组
│   ├── by-tag/                    ← 按标签索引（{tag}.md）
│   └── {slug}.md                  ← OKF v0.2
├── res/                           ← 资源文件（研报/财报/其他，按标的）
│   ├── index.md                   ← 资源索引
│   └── {ticker}/
├── knowledge-graph.html           ← 知识图谱
└── log.md                         ← 变更日志
```

---

# 一、OKF v0.2 知识条目格式

LLM 生成条目时按此模版填充，**描述用中文，摘要≥3句，关键要点≥3条，关联≥2个**：

```markdown
---
type: Analysis
title: 福耀玻璃2026年Q1毛利率回升至38%的核心原因
description: 福耀玻璃2026Q1毛利率38%（+3pp YoY），受益纯碱降价+产品结构升级（天幕/HUD玻璃占比25%），ASP同比+11%超长期指引。
timestamp: 2026-06-22T00:00:00+08:00
resource: res/福耀玻璃/2026-04-21-UBS-Fuyao-Glass-Q126.pdf
source_type: pdf
tags: [fuyao-glass, profit-trend, competitive-advantage, 2026-Q1]
---

# 福耀玻璃2026年Q1毛利率回升至38%的核心原因

## 摘要
福耀玻璃2026年Q1实现营收104.13亿元（+5.1% YoY），毛利率38%（+3pp YoY），超出市场预期。核心驱动力：1）纯碱价格同比下降约15%；2）高附加值产品（天幕玻璃、HUD前挡玻璃、镀膜玻璃）占比提升至25%，带动ASP同比+11%。剔除汇兑损益后净利润+10% YoY，显示主营业务韧性。5家外资券商（UBS/BNP/BofA/JPM/MS）一致看好，目标价CNY80/HKD80。

## 关键要点
- 毛利率38%：纯碱降价贡献约1.5pp，产品结构升级贡献约1.5pp
- ASP同比+11%（vs长期指引6-7% CAGR），受益国内高端车型销量增长
- 汇兑损益逆转是Q1利润下滑的核心干扰项（2025Q1收益2.4亿→2026Q1亏损4.4亿）
- 美国工厂产能利用率85%，关税影响可控（美国市占率30%+，替代供应商有限）
- 一致预期2026年归母净利润约93亿，当前PE约15x，处于近5年估值低位

## 关联
- [福耀玻璃竞争壁垒与护城河分析](entries/福耀玻璃竞争壁垒分析.md) — 补充四大竞争壁垒（国运红利/柔性生产/垂直一体化/降本文化）
- [曹德旺2025年度股东大会关税表态](entries/曹德旺股东大会表态-美国关税.md) — 管理层对关税风险的最新判断

## 引用
- [UBS - Fuyao Glass Q126 Earnings](res/福耀玻璃/2026-04-21-UBS-Fuyao-Glass-Q126.pdf)
```

### type 取值

| type | 适用场景 |
|------|---------|
| `Article` | 外部文章/新闻/数据快照 |
| `Analysis` | 自己的分析、研判、深度研究 |
| `Reference` | 基准数据锚点、年报核心数据 |
| `Synthesis` | 多源综合报告 |
| `Note` | 随手记、片段、想法 |

### tags 三层标签体系

| 层级 | 含义 | 示例 |
|------|------|------|
| **标的** | 公司/行业 | `fuyao-glass` `tsmc` `tencent` |
| **分析维度** | 角度 | `valuation` `risk-factor` `competitive-advantage` |
| **时效** | 时间锚点 | `2026-Q1` `2024` `2026-06` |

维度标签词库：估值(`valuation` `profit-trend`)、风险(`risk-factor` `fx-risk` `geopolitical-risk`)、竞争(`competitive-advantage` `moat` `porter-five-forces`)、商业模式(`business-model` `technology-moat`)、数据(`baseline-data` `official-source`)、市场(`sentiment` `capital-flow` `margin-trading`)

### 内容质量标准

详见 [二、3 进（导入）](#二3-进导入) 中的**入库前必检清单**（8 项逐条检查表 + 正反例 + 格式规范 + type 选型指南）。

---

# 二、3 进（导入）

## ⚠ 入库前必检清单（每条 entry 生成后逐项自检，不通过不调 store）

入库前最少确认 8 项：`description`、摘要、关键要点、tags、关联、type、title、resource。

其中有三条必须特别注意：
- **description 必须含具体数字和结论**，否则搜索召回会明显变差
- **关键要点必须是可解析的列表格式**，不要在 `## 关键要点` 下直接写段落
- **关联链接必须使用真实文件名**，写入前先 `ls entries/` 或读 `entries/index.md` 核对

完整检查表、正反例、关键要点格式规范、type 选型和共享导入规则，详见 `references/import-checklist.md`。

## /km_init — 初始化（LLM 流程，无脚本）

1. 检查 `~/.inv-knowledge` 是否存在
2. bash：`git clone <INV_KNOWLEDGE_REPO_URL> ~/.inv-knowledge`（已存在则 `git pull`）
3. `mkdir -p ~/.inv-knowledge/entries ~/.inv-knowledge/res`

✅ 完成：`~/.inv-knowledge/entries` 和 `res/` 目录存在，可运行 `km_lint`

## /km_import <url> — 丢链接

1. LLM 用 `firecrawl_scrape` MCP 抓取 URL
2. 读内容写摘要+要点+tags
3. 搜索已有条目建 ≥2 关联
4. `km_import.py store`

✅ 完成：`store` 返回 `success:true`，条目已入库 + git push 完成

## /km_import res — 丢资源文件

1. LLM 看文件名判断归属（腾讯控股、福耀玻璃、行业研究-互联网...）
2. `km_import.py res --file {路径} --target {归属}` 归档到 res/ + 提取原文（pymupdf）
3. LLM 读原文，用中文写摘要+要点+tags
4. `km_import.py store` 存入 entries/

✅ 完成：`store` `success:true`；PDF 已归档到 `res/{target}/`，`res/index.md` 已更新，条目已入库

> `res/` 不限于研报，可存放财报、公告等任何资源文件。pymupdf venv 首次自动安装。

## /km_import note — 记笔记（折叠进 /km_import）

1. 用户口述，LLM 格式化+打标签
2. 搜索已有条目建 ≥2 关联
3. `km_import.py store --resource manual --source_type note`

✅ 完成：`store` `success:true`，笔记已入库

---

# 三、3 出（检索与分析）

## /km_search <query> — 搜（LLM 流程，无脚本）

1. 读 `entries/index.md`（按 type 分组的全量条目清单，含 title/description）→ 一句话定位候选
2. `grep -rl "<关键词>" entries/*.md` 按命中文件精筛；按 frontmatter 的 `type`/`source_type`/`tags`/`timestamp` 过滤
3. `grep` 也覆盖 `res/`（`res/index.md` 列出所有资源文件）
4. 跟随命中条目正文 `## 关联` 段链接，扩展相关条目

✅ 完成：返回匹配条目列表（含 path + 相关原因），或按 4.5 格式输出知识缺口

**LLM 搜索策略**（让 LLM 总能找到相关内容）：

1. **多角度搜索**：同一个标的用不同关键词搜 — 中文名"腾讯"、代码"0700"、英文"tencent"、行业"互联网"
2. **过滤链**：全搜 → 读命中条目 frontmatter → 按 type/source_type/tags/timestamp 精准过滤
3. **跟随交叉引用**：命中条目后，读其正文 `## 关联` 段的 markdown 链接，跳到关联条目（"串"的快捷方式）
4. **标签导航**：无结果时读 `entries/by-tag/{tag}.md` 浏览该标签下所有条目
5. **放宽搜索**：零结果时缩短关键词（"福耀玻璃利润趋势"→"福耀"）
6. **双向追踪**：想知道"谁引用了我关注的条目"，用 `grep -rl "条目slug.md" entries/*.md` 反查

| 出口 | 方式 | 说明 |
|------|------|------|
| **搜** | LLM 读 index + grep | 多角度 + 过滤 + 跟随链接 + 标签导航 |
| **串** | LLM inline | 读条目→提取实体→grep 搜索扩展→读关联链→输出关联图（无独立命令） |
| **合** | LLM inline | 搜索→读匹配条目→聚合共识/分歧/时间线/缺口→可选 `store` 为新 Synthesis（无独立命令） |

---

# 四、深度挖掘协议（下游技能必读）

> 三个深度等级（L1 快速检索 / L2 深度探索 / L3 全库挖掘）供下游技能（估值引擎/QARP策略/主题研究）选择。**估值和决策类分析默认最低 L2**。完整协议见 `references/deep-mining-protocol.md`。

- **L1 快速检索**（30秒）：读 `entries/index.md` 定位 top 3-5 候选，不跟随引用
- **L2 深度探索**（3-5分钟，估值/决策默认）：多角度 grep ≥3 角度 → frontmatter 过滤 → 跟随 `## 关联` 链 ≥1 层 → 标签导航 → 按类型分层读取
- **L3 全库挖掘**（5-10分钟，主题研究默认）：L2 + 系统遍历关联 + 聚合分析 + 双向回链 + 知识缺口评估

L2/L3 结束按检查清单自查，覆盖不足时按 4.5 知识缺口格式输出（详见 reference）。

---
# 五、1 底座 + 健康度

## /km_graph — 知识图谱（脚本）

1. 运行 `km_visualize.py`（或 `km_lint --fix` 后自动重建）
2. 生成 `knowledge-graph.html`（Cytoscape 力导向图，自包含）

✅ 完成：`knowledge-graph.html` 已生成，含节点/边；孤立节点比例过高时头部黄标提醒

> 不要在每条 store 后生成——太频繁。导入 5-10 条后随 `km_lint --fix` 一起重建即可。

## /km_lint — 健康度检查与修复（脚本）

1. 运行 `km_lint.py [--fix] [--skip-url-check] [--check-duplicates]`
2. 看 `summary` 找问题最多的项（`empty_summary:3` / `no_cross_refs:12` 等），LLM 优先修数量最多的项
3. （`--fix`）自动重建 index/by-tag/图谱 + git push，再次 lint 验证

✅ 完成：仅检查 → 返回 `summary` + 各项 issue 列表；`--fix` → 安全清理正文死链、重建 index/by-tag/图谱并 git push；以 `severity.errors` 判断阻断性问题

### lint 修复工作流（LLM 驱动）

当 `km_lint --fix` 后仍有孤立条目（`no_cross_refs > 0`）时，LLM 负责补关联、清死链、再次验证；`--fix` 只做确定性修复，不自动写交叉关联。

常见 lint 问题速查、修复步骤与 `--fix` 覆盖范围，详见 `references/error-handling.md`。

---

# 六、时效规则

| 时效 | 距今 | 规则 |
|------|------|------|
| **fresh** | ≤90天 | 默认引用 |
| **aging** | 91-183天 | 须标注 |
| **stale** | >183天 | 默认不引用 |

---

# 七、批量导入（Subagent 工作流）

当有多份 PDF（如批量研报）需要一次性入库时，使用 `delegate_task` 派发 subagent 并行处理。完整工作流（派发模板、写库方式选择、subagent 格式硬规则、垃圾条目清理）见 `references/batch-import.md`。

核心要点：
- **推荐写法**：subagent 内 `write_file()` 直写含完整 OKF frontmatter 的条目 → 主会话 `km_lint.py --fix --skip-url-check` 统一重建索引/标签/图谱/git push
- **批量导入避免** `--content-file`（完整 OKF 文件会形成双重 frontmatter）；单条正文可用 stdin。优先 write_file 避免 shell `$` 转义
- **subagent 硬规则**：每条 25-50 行 MAX，禁止倾倒 PDF 原文
- 批量后立即跑垃圾清理 grep（PDF 免责声明标题 / >200 行 / 无 frontmatter 幽灵条目）

---

# 八、脚本

> 原则：只保留确定性 IO 脚本。检索/统计/初始化/关联发现/综合分析交 LLM。

| 脚本 | 用途 |
|------|------|
| `knowledge.py` | 共享 OKF 引擎：frontmatter 解析、索引/标签重建、合规校验（被其他脚本 import，不直接调用） |
| `km_import.py store/res/read` | 条目存储（git push + index/log 更新）+ 资源导入（pymupdf PDF 提取 + MD5 归档）+ 只读 PDF 提取（`read`，无副作用，下游技能读原始研报用） |
| `km_lint.py` | 健康度检查与修复（确定性检查 + index/by-tag/图谱重建 + git push） |
| `km_visualize.py` | 知识图谱（Cytoscape HTML，确定性数据构建） |

**已交 LLM 的能力**（无脚本）：
- 初始化 `/km_init` → LLM bash `git clone` + `mkdir`
- 搜索 `/km_search` → LLM 读 `entries/index.md` + `grep entries/*.md`
- 关联发现 → LLM 导入时手动建（不再用确定性词袋规则自动补）
- 综合 `/合` → LLM inline 聚合
- 统计概览 → 不再单独设命令；用户问起时 LLM 读 `entries/index.md` 口算，或跑 `/km_lint`（其 summary 含条目数/type分布/stale 等统计）

---

# 九、异常处理

常见导入/抓取/lint 异常、`km_lint --fix` 自动修复范围、以及 git push 触发时机，详见 `references/error-handling.md`。

主规则只保留两条：
- `km_lint --fix` 只做确定性修复（索引、标签、图谱、死链、部分 resource 补全），**不自动写交叉关联**
- 写入失败不应让知识库边界下沉到下游技能；需要写库、刷新或版本递增时，一律回到 `inv-knowledge-curator` 主流程处理

## 依赖

- `_shared/git.py` `_shared/dotenv.py` `_shared/proxy.py`
- `pymupdf`（通过 `/tmp/research-pdf-venv`）
- `PyYAML`（OKF frontmatter 安全解析）
- `assets/cytoscape.min.js`（固定版本内嵌，图谱离线可用）
- 远程仓库：`git@github.com:shunchengGit/inv-knowledge.git`
