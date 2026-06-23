# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Skills 管理和开发仓库，通过软链接将技能部署到各 Agent 目录（hermes / workbuddy）。

## 命名规范

技能目录名格式：`{前缀}-{语义名}`，前缀反映技能领域（如 `inv-` 投资类）。

## 目录结构

```
custom-skills/                  # 技能源码（扁平结构）
  _shared/                      #   共享工具模块（dotenv/proxy/git）
  inv-stock-data/               #   数据层
  inv-valuation-engine/         #   估值引擎
  inv-qarp-strategy/            #   操作决策
  inv-porter-five-forces/       #   五力分析
  inv-research-analyzer/        #   研报分析
  inv-topic-researcher/         #   投资主题研究
  inv-hk-ipo-analysis/          #   港股IPO打新分析
  inv-portfolio-tracker/        #   持仓管理
  inv-knowledge-curator/        #   个人知识管理

.claude/skills/                 # harness 技能（非业务）
  skill-creator/                #   创建/优化技能
  skill-deployer/               #   部署技能到 agent 目录
  skill-linter/                 #   技能结构与文档一致性检查
  project-init/                 #   项目初始化：引导 env 配置并拉取仓库

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

inv-knowledge-curator（知识库，独立）
```

## 技术栈

- Python 3.10+，uv 包管理
- 数据源：akshare（A股）、yfinance（美港股）、pymupdf（PDF）
- 抓取：Firecrawl（本地 `http://localhost:3672`）

## 部署

```bash
# 部署到指定 agent（必填，可多选或 all）
python3 .claude/skills/skill-deployer/scripts/sync.py --agent hermes
python3 .claude/skills/skill-deployer/scripts/sync.py --agent all

# 修改技能后跑 lint
python3 .claude/skills/skill-linter/scripts/lint_skills.py
```

部署目标：
- `~/.hermes/skills/inv-skills/`
- `~/.workbuddy/skills/inv-skills/`

## 环境变量（.env）

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `INV_KNOWLEDGE_REPO_URL` | inv-knowledge-curator 远程仓库 | `git@github.com:shunchengGit/inv-knowledge.git` |
| `INV_KNOWLEDGE_ROOT` | 知识库本地根目录 | `~/.inv-knowledge` |
| `DEPLOY_SKILLS_DIR` | 部署目标子目录名 | `inv-skills` |

## 新建 Skill

```bash
mkdir -p custom-skills/<prefix>-<name>/{scripts,references}
touch custom-skills/<prefix>-<name>/SKILL.md
```

## 约束

- 技能命名必须遵循 `{前缀}-{语义名}` 格式
- `_shared/` 中的模块供所有技能复用，不要放业务逻辑
- harness 技能（`.claude/skills/`）与业务技能（`custom-skills/`）隔离
