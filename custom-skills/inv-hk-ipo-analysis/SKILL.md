---
name: inv-hk-ipo-analysis
description: 分析港股IPO招股书PDF，提取财务数据、基石投资者、行业前景、风险因素，综合判断打新价值
version: 1.0.0
triggers:
  - "新股分析"
  - "IPO分析"
  - "打新"
  - "招股书分析"
  - "是否认购"
  - "新股招股"
  - "结合网络分析"
  - "结合网络信息"
  - "招股章程"
  - "赢面分析"
  - "新股排序"
  - "首日预期"
---

# 港股IPO招股书分析技能

## 核心目标

当用户提供港股IPO招股书PDF或询问新股认购建议时，系统性地提取关键信息，结合市场数据，给出有依据的判断。

## 执行流程

### 第一步：读取招股书PDF

#### 环境准备

IPO prospectus 提取复用 `inv-research-analyzer` 的 PyMuPDF venv 模式：

```bash
# 复用 research-analyzer 的 venv（若不存在则创建）
if [ ! -d /tmp/research-pdf-venv ]; then
    python3 -m venv --clear /tmp/research-pdf-venv
    /tmp/research-pdf-venv/bin/pip install -q pymupdf
fi
PY=/tmp/research-pdf-venv/bin/python
```

#### 1A. 建立关键词地图（推荐用于100页以上大文件）

对400页以上的招股书，先用关键词扫描全文档定位章节，再定向提取：

```bash
$PY -c "
import fitz  # pymupdf
doc = fitz.open('/path/to/prospectus.pdf')

# 第一遍：建立关键词→页码映射
keywords = {
    '基石': [], '財務資料': [], '行業概覽': [],
    '風險因素': [], '所得款項': [], '業務': [],
    '公司資料': [], '發售價': [], '市值': [],
    '虧損': [], '收入': [], '研發': [],
    '現金': [], '經營現金流': [],
}
for i in range(doc.page_count):
    text = doc[i].get_text()
    for kw in keywords:
        if kw in text:
            keywords[kw].append(i+1)

for kw, pages in keywords.items():
    if pages:
        print(f'{kw}: 第{pages[:5]}页... (共{len(pages)}页)')
doc.close()
"
```

#### 1B. 定向提取关键页面

根据关键词地图，提取对应页面内容：

```bash
$PY -c "
import fitz
doc = fitz.open('/path/to/prospectus.pdf')
pages_to_extract = [2, 8, 16, 17, 22, 23, 157]  # 根据关键词地图调整
for p in pages_to_extract:
    text = doc[p-1].get_text()
    print(f'=== 第{p}页 ===')
    print(text[:3000])
doc.close()
"
```

#### 1C. 全文搜索模式（用于查找分散信息）

当关键词分布在多个不连续页面时（如基石投资者名单可能分散在几十页），使用全文搜索：

```bash
$PY -c "
import fitz
doc = fitz.open('/path/to/prospectus.pdf')
target_kw = '基石投資'  # 或 'Cornerstone' / '所得款項用途'
for i in range(1, doc.page_count + 1):
    text = doc[i-1].get_text()
    if target_kw in text:
        print(f'=== 第{i}页 ({target_kw}) ===')
        print(text[:2000])
        print()
doc.close()
"
```

### 第二步：提取关键信息

#### 必须提取的维度

| 维度 | 关键字段 | 说明 |
|------|---------|------|
| **基本资料** | 招股价、每手股数、入场费、招股期、上市日 | 打新成本 |
| **财务数据** | 收入、亏损、研发开支、现金、经营现金流 | 判断烧钱速度 |
| **基石投资者** | 名单、认购占比、禁售期 | 基石占比高→流通盘小 |
| **无基石投资者** | 需特别标注，视为利空信号 | 机构不背书，流通盘全抛压 |
| **核心产品/业务** | 产品阶段、市场规模、竞争格局 | 判断成长性 |
| **风险因素** | 核心风险提示 | 排雷 |
| **所得款项用途** | 资金分配比例 | 判断资金使用效率 |

#### 关键财务指标计算

```python
# 现金消耗率
burn_rate = abs(经营现金流)  # 年化
runway_months = 现金 / (burn_rate / 12)  # 无IPO能撑多久

# IPO后 runway
runway_months_post_ipo = (现金 + 集资净额) / (burn_rate / 12)

# PS倍数
ps_ratio = 市值 / 年化收入
```

### 第三步：搜索市场数据

```bash
# 查询孖展认购热度
web_search("股票代码 孖展 认购倍数")

# 查询近期同类新股首日表现
web_search("2026年 港股 18A 新股 首日 表现")

# 查询公司新闻和评价
web_search("公司名 IPO 评价")
```

### 第四步：综合分析框架

#### 打新决策矩阵

| 维度 | 利好信号 | 利空信号 |
|------|---------|---------|
| **大市环境** | 近期新股胜率>70%，首日涨幅中位数>10% | 近期多只破发，市场情绪转冷 |
| **自身热度** | 孖展超购>10倍 | 孖展<5倍 |
| **基石占比** | >40%（流通盘小，易炒作） | <20%（抛压大） |
| **无基石投资者** | — | 机构不背书，流通盘全抛压，利空 |
| **基石质量** | 主权基金/知名机构/产业资本 | 无名机构/关联方 |
| **集资归属** | 公司收钱（扩产/研发/还债） | **全部旧股转让/公司净额=HK$0**（纯老股东套现，公司本身不受益，强利空） |
| **孖展未足额** | — | **孖展<招股集资总额=未足额**，市场用脚投票最强信号，几乎必破发或开盘即跌（实例：6228 Merdeka孖展HK$5,900万 vs 集资HK$23.85亿 = 0.025倍超购） |
| **基本面** | 收入高增长、毛利率提升、现金充裕 | 持续亏损、烧钱快、二次递表 |
| **估值** | PS合理、对比同行有折价 | PS极高、对比同行无优势 |
| **入场费** | <5000港币（散户易参与） | >1万港币 |

#### 判断逻辑

1. **大市环境**优先于个股质地——大市热时烂票也能涨，大市冷时好票也破发
2. **孖展热度**是市场用脚投票的结果，比主观判断更可靠
3. **基石占比高+孖展冷** = 矛盾信号，通常意味着机构锁仓但散户不跟，首日可能小涨小跌
| 基石质量 | 主权基金/知名机构/产业资本 | 无名机构/关联方 |
| **A+H股溢价** | H股较A股有折價 | H股較A股溢價 |
| **二次递表** | 红旗信号，说明第一次递表失效，需深入调查原因 | — |
| **A股上市失败史** | 若公司曾申请A股上市未果（尤其被否），需重点评估监管风险及转港股动机 | — |

### 第五步：输出结论

#### 打新结论模板

```
## 打新分析：[公司名]（[代码]）

### 关键数据
- 招股价：XX 港元 | 入场费：XX 港元
- 市值：XX 亿港元
- 基石占比：XX%
- 孖展超购：XX 倍
- 上市日：XXXX年XX月XX日

### 综合判断
- 首日上涨概率：XX%
- 首日破发概率：XX%
- 预期涨幅区间：-X% ~ +X%

### 建议
- [建议申购 / 现金1手 / 不建议]
- 理由：XX
- 操作策略：XX
```

## 常见陷阱

详见 `references/common-pitfalls.md`（21 条踩坑记录，含数据源降级、DR/HDR特殊框架、A+H孖展误判等）。

## 参考文件

| 文件 | 用途 |
|------|------|
| `references/hk-ipo-glossary.md` | 港股IPO常用术语（孖展、超购、基石、回拨机制等） |
| `references/hk-ipo-prospectus-extraction-patterns.md` | 招股书PDF提取实战模式（关键词地图、章节跳跃、财务表格处理） |
| `references/hk-ipo-data-sources.md` | 港股IPO抓取数据源清单：一/二/三级源、已知403/Cloudflare拦截清单、降级路径、多源交叉验证规则 |
| `references/hk-ipo-batch-comparison.md` | 多只新股横向对比工作流：每只标的5步标准化、上市日错位、7维度评分卡、迭代追加时的重排规则 |
| `references/hk-dr-second-listing-analysis.md` | DR/HDR第二上市专用框架：母股折让计算、旧股转让陷阱、流动性结构、MSCI重分类风险 |
| `references/hk-a-plus-h-listing-analysis.md` | A+H双重上市专用框架：AH折价计算公式、孖展冷淡反向解读、A股股东摊薄、短打+长持策略分层 |
