---
name: assist
description: >-
  管理 Assist 工作知识库：面试管理、文档生成（日报/周报）。
  当用户说"生成日报/周报""面试题怎么出""列出候选人""给XX出面试题""记录面试反馈""候选人评估""团队汇报材料"时，使用本技能。
metadata:
  openclaw:
    emoji: 📋
---

# Assist Manager

管理 `/Users/chengshun/Assist` 工作知识库。

> **注意**: TODO 管理已迁移至 `todo` 独立技能；文章抓取已删除。

## 目录结构

```
Assist/
├── 团队/           # 汇报材料、技术方案
├── 需求/           # 产品需求文档
├── 面试/           # 候选人简历 + 面试题
└── AI学习/         # AI 工程化学习资料
```

## 命令

### 面试管理

**列出候选人：**
```bash
python3 scripts/interview.py list
```

**生成面试题：**
```bash
python3 scripts/interview.py generate <候选人名> --level senior
python3 scripts/interview.py generate <候选人名> --level mid  # 默认
```

**记录面试反馈：**
```bash
python3 scripts/interview.py feedback <候选人名> --score 45 --rating A
```

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

## 面试评估

候选人按年限分级评估：
- **Senior (10+年):** 学习能力 + 毅力（2维度，50/50）
- **Mid (2-3年):** 智力 + 学习能力 + 毅力（3维度，35/35/30）

评分：每题1-5分，总分60分
- A (45-60): 强烈推荐
- B (36-44): 推荐
- C (27-35): 待定
- D (<27): 不推荐

## 依赖

- Python 3.8+，标准库 only（除 Playwright 外）
- `~/Assist/` 目录结构

## 参考

- 详细工作流见 [references/workflow.md](references/workflow.md)
