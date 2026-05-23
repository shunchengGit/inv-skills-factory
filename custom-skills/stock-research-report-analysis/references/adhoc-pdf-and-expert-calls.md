# 临时 PDF 与专家电话纪要分析

## 适用场景

1. 用户直接提供 PDF 路径（常见于 `~/Downloads/`），文件不在 `RESEARCH_PDF_ROOT` 研报库中
2. PDF 是专家电话会议纪要（expert call transcript）、路演纪要、邀请函，而非标准卖方研报
3. 一次提供多份 PDF（5-10份），需要批量提取、去重、综合

## 直接 PyMuPDF 提取（绕过 research_pdf.py）

当文件不在研报库时，直接用 PyMuPDF 提取，无需先 index：

```python
import fitz
doc = fitz.open('/path/to/file.pdf')
print(f'总页数: {doc.page_count}')
for i, page in enumerate(doc):
    text = page.get_text()
    if text.strip():
        print(f'--- 第{i+1}页 ---')
        print(text[:6000])  # 每页截断防过长
```

**实际工作流：批量提取到 /tmp/ 文件**（适合用户一次提供 2+ 份 PDF）：
```python
import fitz, os, glob

def extract_pdf(pdf_path, out_path):
    doc = fitz.open(pdf_path)
    lines = [f'文件: {os.path.basename(pdf_path)}', f'总页数: {doc.page_count}', '']
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            lines.append(f'--- Page {i+1} ---')
            lines.append(text)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'已提取: {out_path}')

# 用 glob 解决文件名含 Unicode 特殊字符（如引号、省略号）
files = glob.glob('/Users/xxx/Downloads/2026-04-*Tencent*.pdf')
for f in sorted(files):
    out = '/tmp/' + os.path.basename(f).replace('.pdf', '.txt')
    extract_pdf(f, out)
```

**文件名 Unicode 字符问题**：
下载的 PDF 文件名常含 Unicode 特殊字符（右单引号 `’`、省略号 `…`、破折号 `—`），直接传给 `fitz.open()` 会 `FileNotFoundError`。解决方案：
1. 用 `glob.glob(pattern)` 匹配而不是硬编码路径
2. 或在 Python 内用 Unicode 转义：`fitz.open('/path/file_with_\u2019_char.pdf')`

**环境准备**（若未安装 pymupdf）：
```bash
python3 -m venv /tmp/pdf_env
/tmp/pdf_env/bin/pip install pymupdf
```

**注意事项**：
- 每页截断 6000 字符通常足够覆盖正文，disclosure 页可跳过
- 多模/扫描件 PDF `get_text()` 返回空，需走 OCR 技能
- 文件名含空格时 Python 路径需正确转义

**读取提取后的大文本文件**：
当批量提取到 `/tmp/` 后（如 6000+ 行的合并文件），**不要用代码执行工具的 `read_file` 读取**——它返回 `content_returned` (bool) 而非实际内容字符串，无法获取文本。**正确方式**：用命令行执行 `sed`/`grep`/`head`/`tail` 读取：

```bash
# 查看文件总行数
wc -l /tmp/tencent_reports_extracted.txt

# 读取第 100-200 行
sed -n '100,200p' /tmp/tencent_reports_extracted.txt

# 搜索关键词并显示上下文
grep -n -A 5 "目标价" /tmp/tencent_reports_extracted.txt

# 读取特定券商部分（按分隔符定位）
grep -n "HSBC\|JPMorgan\|Deutsche\|UBS" /tmp/tencent_reports_extracted.txt
```

**多份研报交叉分析工作流**（实测有效）：
1. 批量提取所有 PDF 到单个 `/tmp/` 文件（用 Python `fitz.open` + 逐页 `get_text()`）
2. 用 `grep -n` 定位各券商报告的起始行号
3. 用 `sed -n 'X,Yp'` 读取特定券商的完整内容
4. 逐券商提取：评级、目标价、核心逻辑、盈利预测、风险
5. 输出综合观点（共识/分歧/预测区间/隐含假设）

## 邀请函去重

同一专家电话会议通常有 2-3 份文件：
1. **邀请函**（invitation）：标题含 "Invitation" / "TODAY:"，内容只有嘉宾介绍+拨入信息，无实质分析
2. **纪要**（transcript / takeaway / note）：含专家观点、问答、数据

**去重规则**：
- 同一日期+同一嘉宾+同一主题 → 只保留纪要，邀请函标注"与纪要重复，无新增内容"
- 若只有邀请函无纪要 → 说明"仅有邀请函，核心内容有限"

## 专家电话纪要结构化

专家电话纪要与标准研报结构不同，按以下模板提取：

```markdown
## 专家电话纪要：{主题}
- 日期：{YYYY-MM-DD}
- 券商/主办方：{BofA / JPM / MS / ...}
- 嘉宾：{姓名}，{职位}，{公司}
- 分析师：{姓名}

### 核心判断（3-5条）
1. ...

### 关键数据/预测
| 指标 | 数值 | 来源 |
|------|------|------|

### 各客户/细分差异（若适用）
| 客户/细分 | 特征 |
|-----------|------|

### 技术路线判断（若适用）
| 技术 | 时间表 | 判断依据 |
|------|--------|----------|

### 供应链/组件状况（若适用）
- ...

### 与其他纪要的交叉验证
- ...
```

**专家纪要特有要点**：
- 嘉宾观点 ≠ 券商观点，必须标注"专家观点，非券商观点"
- Q&A 部分常含最有价值的一手信息，不要只看开场陈述
- 专家可能有利益关联（如 Source Photonics CTO 谈光模块竞争），需注明

## 多报告交叉信号综合

当一次处理 5+ 份 PDF 时，按以下流程：

### Step 1: 批量提取
- 逐份提取全文，记录：券商、日期、类型（研报/纪要/邀请函）、标的/行业

### Step 2: 去重与分类
- 邀请函 vs 纪要：去重
- 同一事件多份覆盖：合并（如 BofA 两份光模块专家纪要，嘉宾不同则都保留）

### Step 3: 单篇结构化
- 标准研报 → 按研报技能分析维度
- 专家纪要 → 按上方专家纪要模板
- 路演纪要 → 按主题分段（广告/招聘/数据中心等）

### Step 4: 交叉信号综合（最重要）
在所有单篇摘要之后，输出「交叉信号」节：

```markdown
## 交叉信号

1. **{信号主题}**：{哪些报告支持此信号，具体证据}
2. **{信号主题}**：...
```

**交叉信号识别方法**：
- 同一数据点被多份报告引用 → 强信号
- 不同报告对同一问题有不同判断 → 分歧信号（标注各方观点）
- 一份报告的数据验证/推翻另一份的假设 → 验证/推翻信号
- 时间线上的增量（新报告 vs 旧报告的变化）→ 趋势信号

## 行业调研纪要批量浏览工作流

适用场景：用户给出一个**目录路径**（如 `/Users/xxx/Desktop/股票研报/行业研究-互联网`），问"这说的是啥"，而非指定具体标的代码。目录下通常是**行业调研纪要**（industry tour takeaways），覆盖多家公司、多位专家，不是单一公司深度研报。

### 与标准研报的核心差异

| 维度 | 公司深度研报 | 行业调研纪要 |
|------|-------------|-------------|
| 覆盖标的 | 1家 | 3-10家 |
| 页数 | 通常10-30页 | 可能20-50页（如HSBC 23页） |
| 结构 | 盈利模型、估值、评级 | 多位专家访谈+分板块速记 |
| 免责声明 | 末页1-2页 | 第2页起大量 disclaimers |
| 对特定标的信息量 | 深度 | 可能仅1-2页提及，无展开 |

### 批量浏览四步法

**Step 1: 目录扫描与页数判断**
```python
import glob, fitz, os
files = sorted(glob.glob('/path/to/dir/*.pdf'))
for f in files:
    doc = fitz.open(f)
    print(f'{os.path.basename(f)}: {len(doc)} pages')
    doc.close()
```

**Step 2: 提取核心页（首页+关键页）**
- 投行研报PDF结构规律：**第1页 = 核心内容**（标题、分析师、关键观点/数据）
- **第2页起 = 免责声明**（BofA/HSBC/MS等均遵循此模式）
- 对长纪要（>10页），提取**首页 + 各板块首段**即可快速判断内容
- 对短文件（<5页），可全量提取

**Step 3: 结构化摘要（按文件）**
每份纪要输出：
```markdown
### {券商} — {日期} — {标题}
- **页数**: N页
- **类型**: 行业调研纪要 / 专家电话 / 路演
- **覆盖标的**: A, B, C...
- **核心主题**: AI变现 / 广告税 / 游戏出海 / ...
- **访谈专家**: 姓名+职位（如有）
- **关键判断（3-5条）**:
  1. ...
```

**Step 4: 整合同目录多份纪要**
若目录下有2+份文件，输出"目录综述"：
```markdown
## 目录综述：{目录名}

**文件清单**: N份（{最早日期} ~ {最晚日期}）

**覆盖主题**: ...

**提及标的汇总**: ...

**对特定标的的深度**: 说明哪些标的有展开分析、哪些仅被点名提及
```

### 实例（2026-04 中国互联网行业调研）

目录 `~/股票研报/行业研究-互联网` 含2份PDF：

| 文件 | 页数 | 类型 | 核心内容 |
|------|------|------|----------|
| BofA 4/15 | 3页 | Day 1纪要 | 招聘市场、广告、GEO、数据中心专家 |
| HSBC 4/27 | 23页 | 3天 tour | 游戏、本地生活、广告、AI、QuestMobile |

**对PDD的提及情况**：HSBC仅首页和评级表提及"PDD是投资者询问最多的标的之一"，目标价USD 159（+62%），但**文件中无PDD专家访谈或展开分析**。BofA全文未提PDD。这说明行业纪要对特定标的的信息量可能非常有限，不能替代公司深度研报。

## 长篇纪要中的关键词搜索定位

当处理20+页的行业纪要且用户关心特定标的时，**不要逐页人工阅读**，用正则搜索快速定位：

```python
import fitz, re

def search_ticker_in_pdf(pdf_path, patterns):
    """
    patterns: list of regex strings, e.g. ['PDD', 'Pinduoduo', '拼多多']
    Returns: list of (page_index, matched_text_snippet)
    """
    doc = fitz.open(pdf_path)
    results = []
    combined = re.compile('|'.join(patterns), re.IGNORECASE)
    for i in range(len(doc)):
        text = doc[i].get_text()
        if combined.search(text):
            results.append((i, text[:3000]))
    doc.close()
    return results

# 使用示例
matches = search_ticker_in_pdf('/path/to/hsbc.pdf', ['PDD', 'Pinduoduo', '拼多多'])
print(f"提及页数: {len(matches)} / {len(doc)} 总页")
```

**搜索策略**：
- 美股：代码（`PDD`）+ 英文名称（`Pinduoduo`）+ 中文名（`拼多多`）
- A股：代码（`600519`）+ 简称（`茅台` / `贵州茅台`）
- 港股：代码（`0700` / `00700`）+ 简称（`腾讯`）
- 注意：外资研报可能用英文名而非中文名

**搜索结果解读**：
- 命中页数 < 3页 → 该标的可能只是被"点名提及"，无深度分析
- 命中页数 5-10页 → 可能有专门板块或专家访谈
- 命中页数 > 10页 → 可能是该标的公司深度报告，应切换到公司研报分析模板

**实际案例**：HSBC 23页纪要中，PDD仅命中2页（首页概览+评级表），证实为"点名提及"级别。

## 跨目录文件去重（MD5 哈希）

当研报目录经过多年积累后，同一文件可能因手动复制、脚本误操作或下载重复出现在多个子目录中（如行业纪要同时出现在 `腾讯控股/` 和 `行业研究-互联网/`）。

**检测脚本**：
```python
import os, hashlib, glob
from collections import defaultdict

def find_duplicate_pdfs(root_dir):
    all_files = []
    for root, _, files in os.walk(root_dir):
        for f in files:
            if f.lower().endswith('.pdf') or f.lower().endswith('.undefined.pdf'):
                all_files.append(os.path.join(root, f))
    
    hash_map = defaultdict(list)
    for path in all_files:
        try:
            with open(path, 'rb') as f:
                md5 = hashlib.md5(f.read()).hexdigest()
            hash_map[md5].append(path)
        except Exception as e:
            print(f"Error reading {path}: {e}")
    
    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    return duplicates

# 使用示例
dups = find_duplicate_pdfs(os.path.expanduser('~/股票研报'))
for h, paths in dups.items():
    print(f"\n重复组（hash {h[:8]}...）: {len(paths)} 份")
    for p in paths:
        print(f"  {p}")
```

**去重策略**：
- 保留在**最具体**目录中的副本（如公司目录 > 行业目录）
- 若两份都在行业目录，保留日期更新或路径更规范的
- 跨目录重复（如同时在公司目录和行业目录）：优先保留在公司目录，删除行业目录中的副本（行业目录应保留纯行业报告，不含公司深度报告）

## 文件归类与移动（Downloads → 研报库）

用户常从邮件/终端下载研报到 `~/Downloads/`，需要批量移入 `~/研报/` 的对应子目录。

### ⚠️ macOS Full Disk Access 限制（关键坑）

macOS Terminal 默认**没有** Full Disk Access 权限，`find`/`ls`/`glob.glob()` 访问 `~/Downloads/`、`~/Desktop/`、`~/Documents/` 会返回 `Operation not permitted`。**Python `glob`/`shutil`/`os.listdir` 全部失败**。

**解决方案：用 `osascript` 通过 Finder 操作**（Finder 有权限）：

```bash
# 列出 Downloads 中所有文件名
osascript -e 'tell application "Finder" to get name of every file of folder "Downloads" of home'

# 移动单个文件到目标目录
osascript -e 'tell application "Finder" to move file "filename.pdf" of folder "Downloads" of home to folder "0700.HK-腾讯控股" of folder "研报" of home'

# 列出研报子目录中的文件
osascript -e 'tell application "Finder" to get name of every file of folder "0700.HK-腾讯控股" of folder "研报" of home'

# 检查 Downloads 中剩余文件数
osascript -e 'tell application "Finder" to get count of files of folder "Downloads" of home'
```

**注意事项**：
- `osascript` 的 Finder 语法中，文件夹名用 `folder "名称" of folder "父级"` 链式引用
- 文件名中的特殊字符（省略号 `…`、引号等）在 AppleScript 中一般能正确处理
- 批量移动时，逐文件调用 `osascript`（每条 `move` 命令单独执行），避免 heredoc/多行脚本被终端误解析为后台进程
- `osascript` 返回空字符串通常表示执行失败，检查 stderr

### 归类流程

1. **列出 Downloads 中的 PDF**：用 `osascript` 通过 Finder 获取文件名列表
2. **按文件名提取标的代码**：正则匹配 `9660.HK`、`601012.SS`、`0700.HK` 等代码模式
3. **创建目标子目录**：`mkdir -p ~/研报/{代码}-{公司简称}`（`mkdir` 不受 FDA 限制）
4. **逐文件移动**：用 `osascript` 的 Finder `move` 命令
5. **验证**：用 `osascript` 检查目标目录文件数 + Downloads 剩余文件数

### 目录命名规范

`{股票代码}-{公司简称}`，例如：
- `0700.HK-腾讯控股`
- `601012.SS-隆基绿能`
- `9660.HK-地平线机器人`
- `300124.SZ-汇川技术`

### 关键注意点

- 必须同时匹配 `*.pdf` 和 `*.undefined.pdf`（某些平台下载的文件名为 `...-121860640.undefined.pdf`）
- 移动前检查目标是否已存在同名文件，避免覆盖
- 移动后可执行 `find_duplicate_pdfs` 去重（该函数在研报库目录内运行，不受 FDA 限制）
- **不要尝试用 Python `glob.glob("~/Downloads/*.pdf")`**——macOS 会静默返回空列表而非报错

## 本会话实例（2026-04 光模块+中国互联网+DeepSeek）

本会话处理了 8 份 PDF，产出以下交叉信号作为参考：

1. **AI算力需求持续强劲**：BofA光模块专家（800G/1.6T到2030）+ JPM（AI capex从叙事转向变现验证）+ MS（DeepSeek V4参数跃升→算力需求只增不减）
2. **中国AI竞争力实质性提升**：DeepSeek V4匹配Opus-4.6 Agent能力 → JPM认为腾讯混元3.0是"国内AI可信度首次真正测试"
3. **供应链紧张是2026-27主旋律**：光模块EML/DSP短缺3Q26缓解 → 拥有供应链优势的龙头定价权持续增强
4. **AI投入从被奖励到被惩罚**：JPM明确市场不再为AI叙事买单 → 重投入但变现路径不清晰的公司承压，变现已在进行的公司受益
5. **可插拔模块多年内主导**：Frank Chang（Source Photonics CTO）明确CPO验证体系缺失 → XPO是可插拔的"未来武器"
6. **Google是1.6T最大增量客户**：2026-27年光模块需求可能3x-4x增长 → Google供应链公司重要利好
