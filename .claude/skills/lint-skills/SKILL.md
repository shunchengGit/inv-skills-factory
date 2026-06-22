---
name: lint-skills
description: 技能全面检查与自动修复：结构校验 → 合并分析 → description 优化 → 瘦身 → 索引同步。每次修改技能后执行。
---

# 技能 Lint 检查

每次新增、合并、删除技能，或修改了 SKILL.md、_meta.json、脚本后执行。

## ⚡ 先行判断：确定检查范围

执行前先判断改动范围，跳过无关步骤：

| 改动类型 | 需执行的步骤 |
|----------|:----------:|
| 新增技能 | ①→②→③→④→⑤（全流程） |
| 删除技能 | ①→⑤（清索引） |
| 修改 SKILL.md | ①→③→④（校验+瘦身） |
| 修改 _meta.json | ①（结构校验） |
| 修改/新增脚本 | ①（结构校验） |
| 合并技能 | ②→③→④→⑤（全流程） |

## 执行流程

### ① 结构校验 — `lint_skills.py` 基线

```bash
python3 .claude/skills/lint-skills/scripts/lint_skills.py
```

9 项自动检查：_meta.json、frontmatter、命名、空壳、deploy.json、索引表、行数、脚本执行、路径解析。有错误先修。

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
| 5 | frontmatter 与 _meta.json 一致 | — |
| 6 | version / commands 在 fm 和 meta 中也一致 | — |

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

目标 ≤200 行。新建 reference 文件后更新 `_meta.json` 的 `references` 字段。

### ⑤ CLAUDE.md 同步

修改后确保两者一致：

- `CLAUDE.md` 目录结构
- `CLAUDE.md` 依赖关系图
- 实际的 `custom-skills/` 文件系统
