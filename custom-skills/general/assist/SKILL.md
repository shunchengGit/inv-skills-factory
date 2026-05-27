---
name: assist
description: >-
  管理 Assist 工作知识库：文档生成（日报/周报）。
  当用户说"生成日报""生成周报""今日总结""团队汇报材料"时，使用本技能。
metadata:
  openclaw:
    emoji: 📋
---

# Assist Manager

管理 `/Users/chengshun/Assist` 工作知识库。

> **注意**: TODO 管理已迁移至 `todo` 技能；面试管理已迁移至 `interview` 技能。

## 目录结构

```
Assist/
├── 团队/           # 汇报材料、技术方案
├── 需求/           # 产品需求文档
└── AI学习/         # AI 工程化学习资料
```

## 命令

### 文档生成

**生成日报：**
```bash
python3 scripts/docgen.py daily
python3 scripts/docgen.py daily --date 2026-05-16
```

**生成周报：**
```bash
python3 scripts/docgen.py weekly
python3 scripts/docgen.py weekly --date 2026-05-16
```

## 依赖

- Python 3.8+，标准库 only
- `~/Assist/` 目录结构

## 参考

- 详细工作流见 [references/workflow.md](references/workflow.md)
