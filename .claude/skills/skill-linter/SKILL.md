---
name: skill-linter
description: 校验技能结构与文档一致性：检查 frontmatter spec 合规、命名/行数/脚本/路径/依赖/引用深度/时间敏感/反斜杠路径等 17 项。用于修改技能后、lint、检查技能、优化技能时。
trigger:
  - 修改技能
  - lint
  - 检查技能
  - 优化技能
---

# 技能 Lint 检查

每次修改技能（新增/合并/删除/编辑 SKILL.md 或脚本）后执行。

## 执行流程

### ① 结构校验 — `lint_skills.py`

```bash
python3 .claude/skills/skill-linter/scripts/lint_skills.py
```

17 项自动检查。有错误先修。

## 检查项清单

### 元数据 spec 合规（#1, #2, #10, #16）

| # | 检查 | 来源 |
|---|------|------|
| 1 | SKILL.md frontmatter 存在，name 与目录名匹配，version/description 必填 | agentskills.io spec |
| 2 | name: 1-64 字符，小写字母/数字/连字符，首尾不能为连字符 | agentskills.io spec |
| 10 | name 不含保留字（anthropic/claude），name/description 不含 XML 标签 | Anthropic API docs |
| 16 | 建议有 trigger 字段列出触发词，辅助 agent 路由发现 | Anthropic 最佳实践 |

### description 最佳实践（#1 子规则）

基于 [agentskills.io 最佳实践](https://agentskills.io/skill-creation/best-practices) 和 [Anthropic 文档](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)：

| # | 规则 | 说明 |
|---|------|------|
| 0 | ≤1024 字符（spec 硬限制） | — |
| 0b | 不含 XML 标签 | — |
| 1 | 第三人称（"Processes..."），非"I can"/"You can" | Anthropic 要求 |
| 2 | 不含触发句式（"当...时"），那是 trigger 字段职责 | 职责分离 |
| 3 | 中文 ≤80 字符，英文 ≤120 字符 | 简洁 |
| 4 | 不以省略号结尾 | 防截断 |
| 5 | 功能描述优于场景描述（不以"当"开头） | — |
| 6 | 同时包含"做什么"和"何时用"（含"Use when..."） | Anthropic 要求 |
| 7 | 过短（<20 字符）建议加负向触发（negative triggers） | 精准路由 |

### 内容质量（#6, #11, #12, #13, #14, #17）

| # | 检查 | 来源 |
|---|------|------|
| 6 | SKILL.md ≤500 行（spec 上限），建议 ≤200 | agentskills.io spec |
| 11 | 不含面向人类的文档（README.md, CHANGELOG.md 等） | mgechev/skills-best-practices |
| 12 | references/ 保持一级深度，无链式引用（a→b→c） | Anthropic 最佳实践 |
| 13 | 路径使用 forward slash，无 Windows 反斜杠 | Anthropic 最佳实践 |
| 14 | 无时间敏感信息（"before 2025""currently using"等） | Anthropic 最佳实践 |
| 17 | 不列出 3+ 个并行选项，应提供默认方案 | Anthropic 最佳实践 |

### 脚本质量（#7, #8, #15）

| # | 检查 | 来源 |
|---|------|------|
| 7 | 入口脚本 --help 可执行，PEP 723 内联依赖可用 uv run | — |
| 8 | `__file__` 必须调用 `.resolve()` 或 `abspath()` | 软链接兼容 |
| 15 | 裸 open() 需异常处理，魔法数字需注释说明 | mgechev/skills-best-practices |

### 仓库一致性（#3, #4, #5, #9）

| # | 检查 |
|---|------|
| 3 | 无空壳目录（目录存在但缺少 SKILL.md） |
| 4 | deploy.json agent 配置完整 |
| 5 | CLAUDE.md 收录所有技能 |
| 9 | 无 `/Users/xxx`、`/home/xxx` 等个人路径泄露 |

## 关键最佳实践参考

- [agentskills.io Best Practices](https://agentskills.io/skill-creation/best-practices) — 官方 spec 站点
- [Anthropic Skill Authoring Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — Anthropic 官方文档
- [mgechev/skills-best-practices](https://github.com/mgechev/skills-best-practices) — 社区最佳实践集合

核心原则：
- **Progressive Disclosure**: SKILL.md 是"大脑"，细节放 references/，按需加载
- **简洁优先**: 不要解释 agent 已经知道的事（如 "PDF stands for Portable Document Format"）
- **Defaults not menus**: 选一个默认工具，必要时提替代方案，而非列出多个平等选项
- **Procedures over declarations**: 教 agent 如何做一类事，而非给出一个具体答案
- **第三人称指令**: "Extract the text..." 而非 "I will extract..."

### ② 合并分析

读取新增/修改技能的内容，逐一比对已有技能：

- 功能重叠？→ 分析重叠度，给出合并建议
- 是变体/子模式？→ 建议作为新命令或 reference 并入
- 是补充流程？→ 建议作为新章节并入
- 完全独立？→ 可以独立存在

已有案例：`inv-qarp-web-search→inv-qarp-strategy`、`inv-landscape-scan→inv-topic-researcher`。

### ③ SKILL.md 瘦身

读取目标 SKILL.md，将"参考数据"抽到 `references/`，保留"执行指令"：

| → 抽到 references/ | 保留在 SKILL.md |
|--------------------|-----------------|
| 输出模板、报告格式 | 执行流程 |
| 踩坑记录、常见错误 | 决策规则、闸门/纪律 |
| 案例、实操记录 | 命令用法 |
| 数据源映射、工具选择表 | 评分标准（简要） |
| 子模式详细工作流 | Gotchas（环境特定事实） |
| 已知常量、命令清单 | — |

目标 ≤200 行。按 agentskills.io 标准，SKILL.md 上限 500 行，建议 ≤200 以减少上下文占用。

### ④ CLAUDE.md 同步

修改后确保一致：目录结构、依赖关系图、实际文件系统。
