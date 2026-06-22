---
name: skill-linter
description: 技能结构与文档一致性检查：校验 frontmatter/命名/行数/脚本/路径/依赖，辅助合并分析与瘦身，同步 CLAUDE.md
trigger:
  - 修改技能
  - lint
  - 检查技能
  - 优化技能
---

# 技能 Lint 检查

每次修改技能（新增/合并/删除/编辑 SKILL.md 或脚本）后执行。

## 执行流程

### ① 结构校验 — `lint_skills.py` 基线

```bash
python3 .claude/skills/skill-linter/scripts/lint_skills.py
```

9 项自动检查：SKILL.md frontmatter、命名、空壳、deploy.json、CLAUDE.md、行数、脚本执行、路径解析、个人路径泄露。有错误先修。

### ② 合并分析

读取新增/修改技能的内容，逐一比对已有技能：

- 功能重叠？→ 分析重叠度，给出合并建议
- 是变体/子模式？→ 建议作为新命令或 reference 并入
- 是补充流程？→ 建议作为新章节并入
- 完全独立？→ 可以独立存在

已有案例：`inv-qarp-web-search→inv-qarp-strategy`、`inv-landscape-scan→inv-topic-researcher`。

### ③ description 审查

逐条检查所有目标技能的 description：

| # | 规则 | 示例 |
|---|------|------|
| 1 | 功能描述，不是场景描述 | ✅ 获取A股/港股/美股行情 ❌ 当需要查询股票时 |
| 2 | 单句，≤60 字（中文）/ ≤120 字符（英文） | 一行说清 |
| 3 | 触发词在 trigger 字段，不在 description | — |
| 4 | 不以 ... 结尾 | — |
| 5 | frontmatter 字段完整（name/version/description 必填） | — |
| 6 | dependencies 引用的技能必须存在 | — |

发现问题直接修复。

### ④ SKILL.md 瘦身

读取目标 SKILL.md，将"参考数据"抽到 `references/`，保留"执行指令"：

| → 抽到 references/ | 保留在 SKILL.md |
|--------------------|-----------------|
| 输出模板、报告格式 | 执行流程 |
| 踩坑记录、常见错误 | 决策规则、闸门/纪律 |
| 案例、实操记录 | 命令用法 |
| 数据源映射、工具选择表 | 评分标准（简要） |
| 子模式详细工作流 | — |
| 已知常量、命令清单 | — |

目标 ≤200 行。按 agentskills.io 标准，SKILL.md 上限 500 行，建议 ≤200 以减少上下文占用。

### ⑤ CLAUDE.md 同步

修改后确保一致：目录结构、依赖关系图、实际文件系统。
