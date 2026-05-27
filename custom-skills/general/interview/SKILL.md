---
name: interview
description: >-
  面试管理技能。列出候选人、生成面试题模板、记录面试反馈。
  当用户说"面试题怎么出""列出候选人""给XX出面试题""记录面试反馈""候选人评估"时，使用本技能。
metadata:
  openclaw:
    emoji: 🎯
---

# Interview Manager

管理 `~/.interview/` 目录下的候选人信息和面试题。

## 命令

| 命令 | 用途 |
|------|------|
| `python3 scripts/interview.py list` | 列出所有候选人及状态 |
| `python3 scripts/interview.py generate <名> --level senior` | 生成面试题模板（senior: 2维度） |
| `python3 scripts/interview.py generate <名> --level mid` | 生成面试题模板（mid: 3维度，默认） |
| `python3 scripts/interview.py feedback <名> --score 45 --rating A` | 记录面试反馈 |

## 数据

```
~/.interview/
├── resume/                  # 候选人简历 PDF
│   ├── 某某某_Android.pdf
│   ├── 面试题_某某某.md      # 面试题 + 评分
│   └── ...
└── archived/                # 已归档候选人
```

## 评估框架

候选人按年限分级评估：
- **Senior (10+年):** 学习能力 + 毅力（2维度，50/50，每题6题）
- **Mid (2-3年):** 智力 + 学习能力 + 毅力（3维度，35/35/30，每题4题）

评分：每题1-5分，总分60分
- A (45-60): 强烈推荐
- B (36-44): 推荐
- C (27-35): 待定
- D (<27): 不推荐

## 依赖

- Python 3.8+，标准库 only
