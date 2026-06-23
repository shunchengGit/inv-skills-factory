---
name: inv-research-analyzer
description: ⚠ DEPRECATED — 已合并到 inv-knowledge-curator v3.0。请使用 km_import.py --pdf --target 命令。
version: 2.0.2
trigger: []
commands: []
---

# ⚠ 已废弃 (DEPRECATED)

**inv-research-analyzer 已完全合并到 [inv-knowledge-curator](../inv-knowledge-curator/SKILL.md) v3.0。**

所有功能统一在 `km_import.py`：

| 旧命令 | 新命令 |
|--------|--------|
| `research_pdf.py scan` | 已删除，LLM 直接从文件名判断归属 |
| `research_pdf.py archive` | `km_import.py --pdf --target`（一步完成归档+提取） |
| `research_pdf.py extract` | `km_import.py --pdf --target` |
| `research_pdf.py list` | 直接读 `res/` 目录或 `res/index.md` |

资源文件存储在 `~/.inv-knowledge/res/`，知识摘要存储在 `~/.inv-knowledge/entries/`。
