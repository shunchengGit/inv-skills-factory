---
name: inv-research-analyzer
description: 本地券商研报PDF分析：LLM查找Index.md → extract提取 → 结构化综合观点
version: 2.0.2
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

**第一步永远是读 `~/股票研报/Index.md`**，任何情况下不得跳过。

禁止操作：
- ❌ 直接用 `list --code` 查找（对非 A 股不可靠）
- ❌ 直接用 `extract --contains` 提取（绕过了 Index.md 子文件夹确认）
- ❌ 凭记忆猜测子文件夹名

**正确流程**：

1. **读取 `~/股票研报/Index.md`**（必做，不可跳过）
2. 在目录表中按**代码列**匹配标的（支持 `0700.HK` / `MSFT` / `PDD` / `2330.TW` 等任意格式）
3. 确定目标**子文件夹名**（如「微软」「腾讯控股」）和报告份数
4. `extract --folder <子文件夹名>` 提取文本
5. 若 Index.md 无匹配 → 走 Web 降级（`references/web-fallback-for-non-a-share.md`）

## 归档研报（organize）

将 Downloads 等目录的散落研报 PDF 归档到研报库：

1. `scan --source ~/Downloads` → 获取待归档清单 JSON
2. 读 `~/股票研报/Index.md`，判断每个文件应归档到哪个子文件夹
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
| **典型调用方** | `inv-valuation-engine`（估值）、`inv-porter-five-forces`（五力） |

## 执行流程

1. 确认标的、日期窗口（默认半年）。
2. 读取 `~/股票研报/Index.md`，在目录表匹配代码，确定子文件夹名。
3. `extract --folder <子文件夹名>` 提取文本。
4. 按「输出结构」写作；注明研报文件名日期窗口和时效性。
5. **若 Index.md 无匹配**：走 Web 降级（`references/web-fallback-for-non-a-share.md`）。
6. **若用户直接提供 PDF 路径**：用 PyMuPDF 直接提取（勿用 read_file 读二进制 PDF）。批量提取到 `/tmp/` 后分批读取。
7. 若用户问「是否低估/值得买」：引导 `inv-stock-data` + `inv-valuation-engine`。

## 归档技术细节

- **scan 不需要 pymupdf**，用系统 Python 即可：`python3 "$SK" scan --source ~/Downloads`
- **archive 也不需要 pymupdf**（重建索引除外，失败时会跳过索引继续 git push）
- macOS 沙盒下 `pathlib` 可能无法访问 `~/Downloads/`，脚本内部自动回退 AppleScript

### 已知限制：scan 对中文路径/目录名可能返回空

实测发现 `scan --source ~/股票研报` 在中文目录名环境下可能返回 "来源目录中未找到 PDF 文件"，即使目录内存在大量 PDF。

**降级方案**：直接用 Python 遍历重建：

```python
from pathlib import Path
import re

base = Path.home() / "股票研报"
for subdir in sorted(base.iterdir()):
    if not subdir.is_dir() or subdir.name.startswith('.'):
        continue
    pdfs = [f for f in subdir.iterdir() if f.suffix.lower() == '.pdf']
    if pdfs:
        print(f"{subdir.name}: {len(pdfs)} 份")
```

归档方案 JSON 格式：

```json
{
  "actions": [
    {"source_path": "~/Downloads/研报文件.pdf", "target_folder": "目标子文件夹名"}
  ]
}
```

过期清理规则：个股研报 6 个月，行业/策略 12 个月。

## Index.md 维护与清理工作流

archive 命令不会自动更新 Index.md 元数据和目录条目，归档后必须手动 lint 检查。详见 `references/index-maintenance-workflow.md`。

### lint 检查清单（每次归档/删除/手动改动后必须执行）

1. **元数据头**：总研报数是否与文件夹内实际 PDF 总数一致？
2. **总览表**：日期范围是否与最早/最晚文件匹配？
3. **目录表**：每行的 `X 份` 是否与对应子文件夹实际 PDF 数一致？
4. **行业速览/策略速览**：手动维护章节是否存在且未过时？
5. **文件清单章节**：是否存在子文件夹未在清单中体现？

### 删除与重建流程

当需要批量删除低质量研报（如页数过少、内容过短）或彻底移除某个标的时：

1. **读取 Index.md 确定范围**
2. **用 Python 遍历统计页数/文件**：提取每份 PDF 页数，筛选待删除列表
3. **执行删除**：`rm` 删除文件；若删除后子文件夹为空，用 `rmdir` 移除空目录
4. **重建 Index.md**：用 Python 遍历重新生成总览表和目录表
5. **git commit & push**

**重建 Index.md 的 Python 模板**：

```python
from pathlib import Path
import re

base = Path.home() / "股票研报"
subdirs = sorted([d for d in base.iterdir() if d.is_dir() and not d.name.startswith('.')])

# 统计
folder_counts = {}
all_pdfs = []
for subdir in subdirs:
    pdfs = [f for f in subdir.iterdir() if f.suffix.lower() == '.pdf']
    folder_counts[subdir.name] = len(pdfs)
    all_pdfs.extend(pdfs)

# 生成总览表（示例）
print(f"**总研报数**：{len(all_pdfs)} 份（{len(subdirs)} 个标的）")
```

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