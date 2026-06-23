# Index.md 维护工作流

`~/.inv-knowledge/res/Index.md` 是研报库的主索引，但 `archive` 命令**不会自动更新它**。归档/删除/手动改动后必须手动 lint，否则元数据头、目录表、文件清单会逐渐和实际文件对不上。

## 关键陷阱：用 patch 编辑 Index.md 的锚点选择

⚠️ **不要用单纯的 "### XXX" 作为 patch 的 old_string**。

实战翻车案例（2026-06-20）：插入「中际旭创」章节时，用 `"### 中通快递"` 做锚点试图在前面插入新章节。由于 fuzzy 匹配引擎认为 "### 中通快递" 在文件里看似唯一，但 patch 引擎会把整段插入识别成"重命名 + 删除前段"——结果删除了相邻的「工业富联」章节、把「微软」标题改成了「中通快递」。

**正确的锚点选择规则**：

1. **用前一章节最后一个 PDF 行 + 空行 + 下一章节标题** 三行组合作为 old_string，新内容在中间插入：

   ```
   old_string:
   | 2026-04-30 | [....pdf](三星电子/....pdf) |
   <空行>
   ### 中通快递

   new_string:
   | 2026-04-30 | [....pdf](三星电子/....pdf) |
   <空行>
   ### 中际旭创
   ...完整章节...
   <空行>
   ### 中通快递
   ```

   PDF 行包含独一无二的文件名+ID，绝对唯一，避免 fuzzy 匹配错位。

2. **删除章节**：用 "上一章节最后一行 + 整段被删章节 + 下一章节标题" 做 old_string，replace 成 "上一行 + 下一章节标题"。

3. **大改建议**：超过 3 处改动直接重建 Index.md（用下面的 Python 模板），别逐处 patch。

## lint 检查清单（每次归档/删除/手动改动后必须执行）

1. **元数据头** (`count:`)：是否与所有子文件夹 PDF 总数一致？
2. **总览表**：个股/行业/策略 各类型目录数 + 文件数；合计行
3. **目录表**：每行的"X 份"是否与对应子文件夹实际 PDF 数一致？时间范围匹配最早/最晚？总计行？
4. **个股速览 / 行业速览 / 策略速览**：手动维护章节是否存在且未过时？
5. **文件清单章节**：是否每个子文件夹都有对应 `### XXX` 章节？章节内 PDF 行数 == 实际数？

## lint 验证脚本（直接复用）

```python
from pathlib import Path
import re

base = Path.home() / ".inv-knowledge" / "res"
subdirs = sorted([d for d in base.iterdir() if d.is_dir() and not d.name.startswith('.')])

folder_counts = {}
total_pdfs = 0
for subdir in subdirs:
    pdfs = [f for f in subdir.iterdir() if f.suffix.lower() == '.pdf']
    folder_counts[subdir.name] = len(pdfs)
    total_pdfs += len(pdfs)

idx_text = (base / "Index.md").read_text()

# 1. 元数据 count
m = re.search(r'^count:\s*(\d+)', idx_text, re.M)
print(f"元数据 count: {m.group(1)} {'✓' if int(m.group(1))==total_pdfs else '✗'}")

# 2. 总览合计
m = re.search(r'\*\*合计\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+)\*\*', idx_text)
if m:
    print(f"总览合计: 目录 {m.group(1)} {'✓' if int(m.group(1))==len(subdirs) else '✗'}, 文件 {m.group(2)} {'✓' if int(m.group(2))==total_pdfs else '✗'}")

# 3. 目录表总计
m = re.search(r'\*\*总计\*\*.*?\*\*(\d+)\*\*', idx_text)
if m:
    print(f"目录表总计: {m.group(1)} {'✓' if int(m.group(1))==total_pdfs else '✗'}")

# 4. 文件清单章节份数
for name, expected in folder_counts.items():
    m = re.search(rf'###\s+{re.escape(name)}\s*\n\n[^\n]+·\s+(\d+)\s+份', idx_text)
    if not m:
        print(f"  ✗ {name}: 在文件清单中找不到 ### 章节")
    elif int(m.group(1)) != expected:
        print(f"  ✗ {name}: 实际 {expected}, Index.md {m.group(1)}")

# 5. 章节标题唯一性（防 patch 误操作）
for name in folder_counts:
    cnt = idx_text.count(f"### {name}")
    if cnt != 1:
        print(f"  ✗ ### {name} 出现 {cnt} 次（应为 1）")

print("lint 完成")
```

## 删除与重建流程

当需要批量删除低质量研报或彻底移除某个标的时：

1. **读取 Index.md** 确定范围
2. **统计页数/文件**：用 Python 遍历，提取每份 PDF 页数，筛选待删除列表
3. **执行删除**：`rm` 删除文件；若删除后子文件夹为空，用 `rmdir` 移除空目录
4. **重建 Index.md**：用下面的 Python 模板重新生成总览表和目录表（手动维护的"行业速览"等保留原状）
5. **lint 验证**
6. **git commit & push**

## 重建 Index.md 的 Python 骨架

```python
from pathlib import Path
import re
from datetime import datetime

base = Path.home() / ".inv-knowledge" / "res"
subdirs = sorted([d for d in base.iterdir() if d.is_dir() and not d.name.startswith('.')])

# 提取每个 PDF 的日期前缀
def pdf_date(p):
    m = re.match(r'(\d{4}-\d{2}-\d{2})', p.name) or re.match(r'(\d{8})', p.name)
    if not m: return None
    s = m.group(1)
    if len(s) == 8: s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
    try: return datetime.strptime(s, "%Y-%m-%d").date()
    except: return None

# 收集每个子文件夹的元信息
rows = []
for sub in subdirs:
    pdfs = [f for f in sub.iterdir() if f.suffix.lower() == '.pdf']
    dates = sorted([d for d in (pdf_date(p) for p in pdfs) if d])
    rows.append({
        "folder": sub.name,
        "count": len(pdfs),
        "min": dates[0] if dates else None,
        "max": dates[-1] if dates else None,
        "pdfs": sorted(pdfs, key=lambda p: pdf_date(p) or datetime.min.date()),
    })

# 输出元数据头
total = sum(r["count"] for r in rows)
all_dates = [d for r in rows for d in [r["min"], r["max"]] if d]
print("---")
print(f"updated: {datetime.now():%Y-%m-%d}")
print(f"count: {total}")
print(f"range: {min(all_dates)} ~ {max(all_dates)}")
print("---")
# ...后续生成总览表、目录表、个股速览、文件清单章节
```

## 章节排序规范

- **目录表**：按拼音首字母 + 第二字。常见顺序：ASML / Meta / SK海力士 / 万 / 三 / 中际 / 中通 / 台 / 地 / 宁 / 工 / 微 / 恒 / 拼 / 日 / 毛 / 汇 / 泡 / 澜 / 福 / 老 / 腾 / 英 / 谷 / 贵 / 阿 / 隆 / 行业研究-... / 策略研究
- **个股速览**：按"最新研报日期"倒序
- **文件清单章节**：与目录表顺序一致

## URL 编码规则（文件清单链接）

PDF 链接路径需要 URL 编码：
- 空格 → `%20`
- 中文括号 `（）` 直接保留
- ASCII 括号 `()` 直接保留即可（部分 markdown 渲染器接受）
- 引号 `"` → `%22`

参考既有条目格式即可，无需手算。

## 过期清理规则

- 个股研报：6 个月
- 行业/策略研究：12 个月

清理时一并 lint Index.md。
