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
  inv-topic-researcher/         #   投资主题研究
  inv-hk-ipo-analysis/          #   港股IPO打新分析
  inv-portfolio-tracker/        #   持仓管理
  inv-knowledge-curator/        #   知识库 + 研报/资源管理（v3.2：km_import{store/res/read}/km_lint/km_graph；4 脚本，检索/统计交 LLM）

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
inv-knowledge-curator（知识库 + 研报管理，v3.2）────┐
  ↑  提供 /km_search, /km_import, /km_lint, /km_graph, km_import read │
  │  脚本只管确定性 IO；检索/统计/关联/综合交 LLM                    │
  │  下游读原始研报走 km_import read（只读，无副作用）              │
  ├── inv-valuation-engine（估值引擎）              │
  │     ↑                                          │
  │     └── inv-qarp-strategy（操作决策，深度+原始研报读取）│
  ├── inv-topic-researcher（信息采集框架，深度集成）│
  ├── inv-qarp-strategy（操作决策，深度+原始研报读取）│
  └── inv-porter-five-forces（五力分析，只读）      │


inv-stock-data（数据层，纯数据源不依赖知识库）──────┐
  ├── inv-valuation-engine（估值引擎）              │
  ├── inv-porter-five-forces（五力分析）            │
  └── inv-portfolio-tracker（持仓管理）             │

inv-topic-researcher（信息采集框架）─┐
  └── inv-portfolio-tracker（持仓管理）
```

> **知识库只读约定**：除 inv-knowledge-curator 自身外，下游技能对知识库均为**只读**（`/km_search` + `km_import read`），不调用 `/km_import` 写入。研判入库由知识库主流程统一负责，避免多入口污染。inv-qarp-strategy 是知识库最重消费方（L2 深度搜索 + 原始研报回溯流入三道闸门/买入必答）。

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
| `INV_KNOWLEDGE_REPO_URL` | 知识库 Git 远程仓库（研报/资源均在此） | `git@github.com:shunchengGit/inv-knowledge.git` |
| `INV_KNOWLEDGE_ROOT` | 知识库本地目录 | `~/.inv-knowledge` |
| `DEPLOY_SKILLS_DIR` | 部署目标子目录名 | `inv-skills` |

> `INV_REPORT_REPO_URL` 和 `RESEARCH_PDF_ROOT` 已删除。研报库已合并到知识库的 `res/` 目录。

## 新建 Skill

```bash
mkdir -p custom-skills/<prefix>-<name>/{scripts,references}
touch custom-skills/<prefix>-<name>/SKILL.md
```

## 约束

- 技能命名必须遵循 `{前缀}-{语义名}` 格式
- `_shared/` 中的模块供所有技能复用，不要放业务逻辑
- harness 技能（`.claude/skills/`）与业务技能（`custom-skills/`）隔离
- 其他技能引用知识库能力时用 `/km_search` `/km_import` 等命令，不硬编码脚本路径
- **知识库只读约定**：下游技能对知识库只读（`/km_search` 检索 + `km_import read` 读原始研报 PDF），不调用 `/km_import store/res` 写入。研判入库由知识库主流程统一负责
- `km_import read --file <res/下PDF路径> --pages edges` 是读原始研报的唯一只读入口（无 git push/索引重建副作用）；`km_import res` 是导入（有副作用），勿混用
