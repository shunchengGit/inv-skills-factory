# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个 Skills 管理和开发仓库，存放自定义投资分析技能（股票估值、行业分析、研报分析、前置指标追踪）。

## 目录结构

```
custom-skills/                  # 自定义 Skills
  general/                      # 通用技能
    knowledge-mgr/              # 个人知识管理
      ...
  invest/                       # 投资分析技能
    <skill-name>/               # 每个 Skill 一个子目录（kebab-case）
      SKILL.md                  # 技能定义文件（必需），YAML frontmatter + Markdown 指令
      _meta.json                # 元数据：name/version/description/commands/scripts/references/dependencies/derivedFrom
      scripts/                  # Python 数据脚本（snake_case.py）
        ...
      references/               # 参考文档
        ...
```

## 技能依赖关系

```
cs-stock（数据层）────────────────────────────┐
  ↑                                          │
  ├── value-investing-valuation（估值引擎）   │
  │     ↑                                    │
  │     └── quality-growth-qarp（操作决策）   │
  ├── porter-five-forces-analysis（五力分析）  │
  └── (其他技能通过 CLI 子进程调用)            │

tencent-leading-indicators / fuyao-leading-indicators（前置指标，独立脚本）
stock-research-report-analysis（研报分析，独立脚本）
```

## 技术栈

- Python 3.10+，uv 包管理
- 数据源：akshare（A股）、yfinance（美港股）、pymupdf（PDF）、playwright（浏览器抓取）

## 新建 Skill

```bash
mkdir -p custom-skills/invest/<skill-name>/{scripts,references}
touch custom-skills/invest/<skill-name>/SKILL.md
cat > custom-skills/invest/<skill-name>/_meta.json << 'EOF'
{
  "name": "<skill-name>",
  "version": "0.1.0",
  "description": "",
  "commands": [],
  "scripts": {},
  "references": {},
  "dependencies": [],
  "derivedFrom": null
}
EOF
```
