# 归档技术细节与 Index.md 维护

## 归档技术细节

- **scan 不需要 pymupdf**，用系统 Python 即可：`python3 "$SK" scan --source ~/Downloads`
- **archive 也不需要 pymupdf**（重建索引除外，失败时会跳过索引继续 git push）
- macOS 沙盒下 `pathlib` 可能无法访问 `~/Downloads/`，脚本内部自动回退 AppleScript

### 已知限制：scan 对中文路径/目录名可能返回空

实测发现 `scan --source ~/.inv-report` 在中文目录名环境下可能返回 "来源目录中未找到 PDF 文件"，即使目录内存在大量 PDF。

**降级方案**：直接用 Python 遍历重建：

```python
from pathlib import Path
import re

base = Path.home() / ".inv-report"
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

base = Path.home() / ".inv-report"
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
