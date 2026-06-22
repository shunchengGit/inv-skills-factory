---
name: inv-research-analyzer
description: 本地券商研报PDF分析：LLM查找Index.md → extract提取 → 结构化综合观点。用于分析券商研报、提取研报核心观点时
version: 2.0.2
trigger:
  - 研报分析
  - 券商研报
  - 研报提取
  - research_pdf
commands:
  - /research_pdf extract - 抽取正文到 stdout（edges / first-n / all / --folder）
  - /research_pdf list - 列出匹配 PDF（调试用）
  - /research_pdf scan - 扫描来源目录，输出待归档清单 JSON
  - /research_pdf archive - 接收归档方案 JSON，执行移动、建索引、push
---

# 股票研报 PDF 分析（inv-research-analyzer）

路径中 **`{baseDir}`** 表示本技能目录。

## 核心目标

基于本地券商 PDF，输出结构化综合观点（共识、分歧、盈利预测区间、隐含假设）。**不做**买卖建议、五档估值或目标价结论（交由 `inv-valuation-engine` + `inv-stock-data`）。

## 环境准备（必须）

每次 extract 前必须先确保 pymupdf 可用。**不要用 `&&` 链式创建 venv**——venv 已存在时 `python3 -m venv` 会失败，导致 pymupdf 未安装。

```bash
# 正确做法：先检查再按需创建
if [ ! -d /tmp/research-pdf-venv ]; then python3 -m venv /tmp/research-pdf-venv; fi
/tmp/research-pdf-venv/bin/pip install -q -r "{baseDir}/requirements.txt"
PY=/tmp/research-pdf-venv/bin/python
```

或者更简单——用 `python3 -m venv --clear` 强制重建（每次重建约 2s，但最稳定）：

```bash
python3 -m venv --clear /tmp/research-pdf-venv && /tmp/research-pdf-venv/bin/pip install -q -r "{baseDir}/requirements.txt"
PY=/tmp/research-pdf-venv/bin/python
```

**scan 子命令不需要 pymupdf**，可以直接用系统 Python 执行。

## 查找研报（硬规则）

**第一步永远是读 `~/.inv-report/Index.md`**，任何情况下不得跳过。

禁止操作：
- ❌ 直接用 `list --code` 查找（对非 A 股不可靠）
- ❌ 直接用 `extract --contains` 提取（绕过了 Index.md 子文件夹确认）
- ❌ 凭记忆猜测子文件夹名

**正确流程**：

1. **读取 `~/.inv-report/Index.md`**（必做，不可跳过）
2. 在目录表中按**代码列**匹配标的（支持 `0700.HK` / `MSFT` / `PDD` / `2330.TW` 等任意格式）
3. 确定目标**子文件夹名**（如「微软」「腾讯控股」）和报告份数
4. `extract --folder <子文件夹名>` 提取文本
5. 若 Index.md 无匹配 → 走 Web 降级（`references/web-fallback-for-non-a-share.md`）

## 归档研报（organize）

将 Downloads 等目录的散落研报 PDF 归档到研报库：

1. `scan --source ~/Downloads` → 获取待归档清单 JSON
2. 读 `~/.inv-report/Index.md`，判断每个文件应归档到哪个子文件夹
3. 构造归档方案 JSON，调用 `archive --plan '<JSON>'` 执行移动、建索引、git push

这是完整闭环——不要只提取不归档。新下载的研报应先 scan → archive 入库，再从库中 extract。

## 快速命令

```bash
# 安装依赖（--clear 强制重建，最稳定；scan 不需要此步）
python3 -m venv --clear /tmp/research-pdf-venv && /tmp/research-pdf-venv/bin/pip install -q -r "{baseDir}/requirements.txt"
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

1. **读 `~/.inv-report/Index.md`**：确定子文件夹名和报告份数。
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

- 抽取工具：`pymupdf`；表格可能错位，**财务数字以 PDF 原文为准**。加密/损坏 PDF 自动跳过。
- `--max-pages`（默认 30）防卡死。Python：用 venv + `requirements.txt`。

## 输出结构

**多篇同一标的时必须有「综合观点」**，禁止只堆单篇摘要。分析维度：元信息、评级与目标价、核心逻辑、盈利预测、风险、商业模式与护城河、资本配置、盈利质量、增长假设。

结构化输出模板详见 `references/output-templates.md`。

## 被调用模式

输入 ticker + 可选窗口/页数，输出结构化模板。调用：读 Index.md → `extract --folder` → 按模板整理。时效性：默认 fresh（≤90天），aging 标注，stale 不引用。典型调用方：`inv-valuation-engine`、`inv-porter-five-forces`。

## 执行流程

1. 确认标的、日期窗口（默认半年）→ 2. 读 `~/.inv-report/Index.md` 匹配代码 → 3. `extract --folder` 提取 → 4. 按输出结构写作。Index.md 无匹配走 Web 降级；用户提供 PDF 路径则 PyMuPDF 直接提取。若用户问估值/买卖：引导 `inv-stock-data` + `inv-valuation-engine`。

## 归档技术细节与 Index.md 维护

详见 `references/archive-and-index-guide.md`，包含 scan 中文路径降级、归档 JSON 格式、Index.md lint 检查清单、删除与重建流程。

## 与其他技能配合

- **`inv-stock-data`**：事实数据（现价、财务指标）；冲突时以行情与披露为准。
- **`inv-valuation-engine`**：估值与假设；研报仅作**预期输入**。
- **`inv-porter-five-forces`**：竞争格局；研报作证据补充。
- **边界**：不把卖方评级或目标价当独立最终结论。

## 参考文件

| 文件 | 用途 |
|------|------|
| `references/web-fallback-for-non-a-share.md` | 非 A 股无本地 PDF 时的降级策略 |
| `references/adhoc-pdf-and-expert-calls.md` | 临时 PDF 与专家电话纪要处理 |
| `references/extended-cycle-analysis-workflow.md` | 周期股深度分析扩展 |
| `references/foreign-stock-research-workflow.md` | 外资研报分析工作流 |
| `references/research-integration-notes.md` | 研报整合实战笔记 |
| `references/index-maintenance-workflow.md` | Index.md 维护、lint 检查与删除重建工作流 |

## 使用原则

1. 先提取文本再写综述。
2. **不构成投资建议**。
3. 查找研报先读 Index.md，不要用 `list --code` 做主要查找。
4. 异常排版 PDF：加大 `--max-chars`、换 `first-n`/`all`，或 OCR。
5. 加密/损坏 PDF：自动跳过。
6. pymupdf 依赖缺失：用 venv 安装（见快速命令）。