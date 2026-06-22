# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Skills 管理和开发仓库，通过软链接将技能按场景（profile）部署到各 Agent 目录。

## 命名规范

技能目录名格式：`{前缀}-{语义名}`，前缀反映技能领域（如 `inv-` 投资类）。

## 目录结构

```
custom-skills/                  # 技能源码（扁平结构）
  _shared/                      #   共享工具模块（dotenv/proxy/pwright/git/indicators）
  inv-stock-data/               #   数据层
  inv-valuation-engine/         #   估值引擎
  inv-qarp-strategy/            #   操作决策
  inv-porter-five-forces/       #   五力分析
  inv-research-analyzer/        #   研报分析
  inv-topic-researcher/         #   投资主题研究
  inv-hk-ipo-analysis/          #   港股IPO打新分析
  inv-portfolio-tracker/        #   持仓管理

openspec/                       # OpenSpec 变更管理
  config.yaml
  changes/
  specs/
```

## 技能依赖关系

```
inv-stock-data（数据层）────────────────────────────┐
  ↑                                                │
  ├── inv-valuation-engine（估值引擎）              │
  │     ↑                                          │
  │     └── inv-qarp-strategy（操作决策）           │
  ├── inv-porter-five-forces（五力分析）            │
  └── inv-portfolio-tracker（持仓管理）             │

inv-topic-researcher（信息采集框架）─┐
  ├── inv-research-analyzer（本地研报）
  └── inv-portfolio-tracker（持仓管理）
```

## 技术栈

- Python 3.10+，uv 包管理
- 数据源：akshare（A股）、yfinance（美港股）、pymupdf（PDF）

## 新建 Skill

```bash
mkdir -p custom-skills/<prefix>-<name>/{scripts,references}
touch custom-skills/<prefix>-<name>/SKILL.md
cat > custom-skills/<prefix>-<name>/_meta.json << 'EOF'
{
  "name": "<prefix>-<name>",
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

## 约束

- 技能命名必须遵循 `{前缀}-{语义名}` 格式
