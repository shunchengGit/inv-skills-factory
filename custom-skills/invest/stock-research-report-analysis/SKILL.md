---
name: stock-research-report-analysis
description: 当需要分析本地券商研报PDF时使用，支持提取结构化观点和综合判断
version: 2.0.0
commands:
  - /research_pdf extract - 抽取正文到 stdout（edges / first-n / all / folder）
  - /research_pdf list - 列出匹配 PDF（调试用）
  - /research_pdf scan - 扫描来源目录，输出待归档清单 JSON
  - /research_pdf archive - 接收归档方案 JSON，执行移动、建索引、push
---

# 股票研报 PDF 分析（stock-research-report-analysis）

路径中 **`{baseDir}`** 表示本技能目录。

## 核心目标

基于本地券商 PDF，输出结构化综合观点（共识、分歧、盈利预测区间、隐含假设）。**不做**买卖建议、五档估值或目标价结论（交由 `value-investing-valuation` + `cs-stock`）。

## 查找研报（硬规则）

**不要用 `list --code` 查找研报**——脚本对非 A 股代码的字符串匹配不可靠。

**正确流程**：

1. **读取 `~/股票研报/Index.md`**（Read 工具）
2. 在目录表中按**代码列**匹配标的（支持 `0700.HK` / `MSFT` / `PDD` / `2330.TW` 等任意格式）
3. 确定目标**子文件夹名**（如「微软」「腾讯控股」）和报告份数
4. `extract --folder <子文件夹名>` 提取文本
5. 若 Index.md 无匹配 → 走 Web 降级（`references/web-fallback-for-non-a-share.md`）

## 快速命令

```bash
# 安装依赖
python3 -m venv /tmp/research-pdf-venv && /tmp/research-pdf-venv/bin/pip install -r "{baseDir}/requirements.txt"
PY=/tmp/research-pdf-venv/bin/python
SK="{baseDir}/scripts/research_pdf.py"

# ── 推荐：--folder 直接提取子文件夹 ──
$PY "$SK" extract --folder 微软
$PY "$SK" extract --folder 腾讯控股 --within-days 90
$PY "$SK" extract --folder 福耀玻璃 --pages first-n --first-n 3

# ── 传统：--code / --contains（A 股可靠，非 A 股建议用 --folder）──
$PY "$SK" list --code 000858 --json
$PY "$SK" extract --code 000858 --sort date-asc
$PY "$SK" extract --contains 五粮液

# 全历史
$PY "$SK" extract --folder 五粮液 --within-days 0
```

## 脚本使用优先级

1. **读 `~/股票研报/Index.md`**：确定子文件夹名和报告份数。
2. **`extract --folder`**：直接提取（推荐，最精确）。
3. **`extract --contains`**：按文件名子串匹配（不确定子文件夹名时）。
4. **`list`**：仅调试用。
5. `extract` 至少指定 `--folder`、`--code` 或 `--contains` 之一。

## 时间范围与时效性（硬规则）

- 默认 **`--within-days 183`**（约半年），区间 `[--as-of - 天数, --as-of]`。
- **`--within-days 0`**：全历史。
- **`--as-of YYYY-MM-DD`**：固定基准日。
- **`--include-undated`**：纳入无日期前缀的文件（默认排除）。

| 时效性 | 距今 | 引用规则 |
|--------|------|----------|
| **fresh** | ≤ 90 天 | 默认引用 |
| **aging** | 91-183 天 | 须标注 |
| **stale** | > 183 天 | 默认不引用 |

## 数据源与约束

- 抽取工具：`pymupdf`；表格在纯文本中可能错位，**财务数字以 PDF 原文为准**。
- 加密/损坏 PDF：自动跳过，stderr 记录。
- `--max-pages`（默认 30）防止大研报卡死。
- Python：用 venv + `requirements.txt`，勿全局 `pip`。

## 输出结构

**多篇同一标的时必须有「综合观点」**，禁止只堆单篇摘要。

### 分析维度

| 模块 | 要点 |
|------|------|
| 元信息 | 券商、日期、页数、时效性 |
| 评级与目标价 | 原文；无则未披露 |
| 核心逻辑 | 1～3 条主线 |
| 盈利预测 | 仅摘录研报表内数字 |
| 风险 | 研报列示 |
| 商业模式与护城河 | 须可归因原文 |
| 资本配置与股东回报 | CAPEX、分红回购等 |
| 盈利质量线索 | ROE、毛利率等 |
| 增长假设与边界 | 关键变量、失效情景 |

### 结构化输出模板（被下游技能调用时）

```markdown
## 研报结构化摘要：{TICKER}

### 元信息
- 标的：{代码} {名称}
- 覆盖研报数：N 篇（{最早} ~ {最晚}）
- 时效性：fresh / aging / stale

### 共识观点（2-3 条）
1. …

### 分歧观点（1-2 条）
1. …

### 评级与目标价区间
| 券商 | 日期 | 评级 | 目标价 |
|------|------|------|--------|

### 盈利预测区间
| 指标 | 年份 | 区间 | 来源 |
|------|------|------|------|

### 核心风险
1. …

### 隐含假设与失效条件
1. …

### 与五力/估值的交叉验证点
- 供下游技能引用的具体验证点
```

### Markdown 输出模板（用户直接使用时）

```markdown
# 【标的】研报梳理（本地 PDF）
## 一、覆盖文件清单
## 二、分报告摘要（逐篇，宜短）
## 三、综合观点（共识 / 分歧 / 预测区间 / 隐含假设）
## 四、局限说明
## 五、待核实项
```

## 被调用模式

| 项目 | 说明 |
|------|------|
| **输入** | ticker + 可选 `--within-days`、`--pages` |
| **输出** | 结构化输出模板 |
| **调用方式** | 1) 读 `~/股票研报/Index.md` 匹配代码 → 2) `extract --folder <子文件夹>` → 按模板整理 |
| **时效性约束** | 默认仅引用 fresh；aging 需标注；stale 不引用 |
| **典型调用方** | `value-investing-valuation`（估值）、`porter-five-forces-analysis`（五力） |

## 执行流程

1. 确认标的、日期窗口（默认半年）。
2. 读取 `~/股票研报/Index.md`，在目录表匹配代码，确定子文件夹名。
3. `extract --folder <子文件夹名>` 提取文本。
4. 按「输出结构」写作；注明研报文件名日期窗口和时效性。
5. **若 Index.md 无匹配**：走 Web 降级（`references/web-fallback-for-non-a-share.md`）。
6. **若用户直接提供 PDF 路径**：用 PyMuPDF 直接提取（勿用 read_file 读二进制 PDF）。批量提取到 `/tmp/` 后分批读取。
7. 若用户问「是否低估/值得买」：引导 `cs-stock` + `value-investing-valuation`。

## 研报管理（organize）

将 Downloads 等目录中散落的研报 PDF **归档到研报库子文件夹 → 清理过期 → git 提交推送**。

标的识别由 LLM 完成：读 `Index.md` 目录表，理解代码→文件夹名映射，判断归档目标。

### 研报库结构

```
~/股票研报/
├── 腾讯控股/          # 个股研报
├── 行业研究-互联网/   # 行业研报
├── 策略研究/          # 策略/宏观研报
├── Index.md           # 索引
└── .git/
```

### scan 子命令（输出待归档清单）

```bash
$PY "$SK" scan --source ~/Downloads
```

输出 JSON：每份 PDF 的文件名、提取的代码、日期、券商猜测，以及研报库已有子文件夹列表。LLM 据此 + Index.md 判断每个文件应归档到哪个子文件夹。

### archive 子命令（执行归档方案）

LLM 判断完毕后，构造归档方案 JSON 并调用：

```bash
$PY "$SK" archive --plan '<JSON>'
# 或从 stdin 传入：
echo '<JSON>' | $PY "$SK" archive
```

归档方案 JSON 格式：

```json
{
  "actions": [
    {"source_path": "/Users/chengshun/Downloads/2026-05-20-2057.HK-JPMorgan-中通快递.pdf", "target_folder": "中通快递"},
    {"source_path": "/Users/chengshun/Downloads/行业-半导体深度.pdf", "target_folder": "行业研究-半导体"}
  ]
}
```

**执行流程**：
1. 读取归档方案，逐个移动文件到目标子文件夹
2. 同名文件：MD5 相同则删除源文件，不同则加后缀 `_2`
3. 输出研报库全部文件清单（JSON），供 Agent 判断过期
4. Agent 删除过期文件（个股 6 个月，行业/策略 12 个月）
5. 重建索引 + `git add -A && git commit && git push`

### macOS Downloads 访问

macOS 沙盒下 `pathlib` 可能无法访问 `~/Downloads/`，脚本内部自动回退 AppleScript。

## 与其他技能配合

- **`cs-stock`**：事实数据（现价、财务指标）；冲突时以行情与披露为准。
- **`value-investing-valuation`**：估值与假设；研报仅作**预期输入**。
- **`porter-five-forces-analysis`**：竞争格局；研报作证据补充。
- **边界**：不把卖方评级或目标价当独立最终结论。

## 参考文件

| 文件 | 用途 |
|------|------|
| `references/web-fallback-for-non-a-share.md` | 非 A 股无本地 PDF 时的降级策略 |
| `references/adhoc-pdf-and-expert-calls.md` | 临时 PDF 与专家电话纪要处理 |
| `references/extended-cycle-analysis-workflow.md` | 周期股深度分析扩展 |
| `references/foreign-stock-research-workflow.md` | 外资研报分析工作流 |
| `references/research-integration-notes.md` | 研报整合实战笔记 |

## 使用原则

1. 先提取文本再写综述。
2. **不构成投资建议**。
3. 查找研报先读 Index.md，不要用 `list --code` 做主要查找。
4. 异常排版 PDF：加大 `--max-chars`、换 `first-n`/`all`，或 OCR。
5. 加密/损坏 PDF：自动跳过。
6. pymupdf 依赖缺失：用 venv 安装（见快速命令）。