# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Skills 管理和开发仓库，通过软链接将技能和 hooks 按场景（profile）部署到各 Agent 目录。

## 目录结构

```
custom-skills/                  # 技能源码（按分类隔离）
  base/                         # 基础技能（所有 profile 必含）
    using-custom-skills/        #   技能使用指南
  general/                      # 通用技能
    daily-arrange/              #   日程安排
    dingding/                   #   钉钉集成
    interview/                  #   面试辅助
    knowledge-mgr/              #   知识管理
    mail-mgr/                   #   邮件管理
    todo/                       #   待办管理
  invest/                       # 投资分析技能
    _shared/                    #   共享工具模块
    cs-stock/                   #   数据层
    cs-crawl/                   #   爬虫
    value-investing-valuation/  #   估值引擎
    quality-growth-qarp/        #   操作决策
    porter-five-forces-analysis/#   五力分析
    tencent-leading-indicators/ #   前置指标（腾讯）
    fuyao-leading-indicators/   #   前置指标（福耀）
    stock-research-report-analysis/ # 研报分析

custom-hooks/                   # Hooks 源码（按 agent 隔离）
  hermes/                       # Hermes 专属 hooks

scripts/
  sync.py                       # 同步脚本（软链接模式）

deploy.json                     # 部署配置：profiles + agents

openspec/                       # OpenSpec 变更管理
  config.yaml
  changes/
  specs/
```

## 部署配置 (deploy.json)

```json
{
  "profiles": {
    "home":   { "hermes": ["general", "invest"], "workbuddy": ["general"] },
    "work":   { "hermes": ["general"],           "workbuddy": ["general"] },
    "server": { "hermes": ["invest"] }
  },
  "agents": {
    "hermes":    { "skills_dir": "~/.hermes/skills",    "hooks_dir": "~/.hermes/hooks" },
    "workbuddy": { "skills_dir": "~/.workbuddy/skills", "hooks_dir": "~/.workbuddy/hooks" }
  }
}
```

base 分类始终同步，无需在 profile 中声明。

## 同步脚本

```bash
python scripts/sync.py --profile work          # 同步 work 场景
python scripts/sync.py --profile home --dry-run # 预览
python scripts/sync.py --profile home --agent hermes  # 仅同步指定 agent
python scripts/sync.py --profile home --hooks-only    # 仅同步 hooks
python scripts/sync.py --profile home --force   # 强制替换非空目录
python scripts/sync.py --list                  # 列出可用 profiles
```

同步时会自动清理目标目录中不在当前 profile 范围内的过期软链接。

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
mkdir -p custom-skills/<category>/<skill-name>/{scripts,references}
touch custom-skills/<category>/<skill-name>/SKILL.md
cat > custom-skills/<category>/<skill-name>/_meta.json << 'EOF'
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

## 约束

- 不同分类目录下技能必须隔离，禁止跨分类引用
