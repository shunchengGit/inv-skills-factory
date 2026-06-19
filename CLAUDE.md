# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Skills 管理和开发仓库，通过软链接将技能和 hooks 按场景（profile）部署到各 Agent 目录。

## 命名规范

技能目录名格式：`{分类前缀}-{语义名}`

| 分类 | 前缀 | 示例 |
|------|------|------|
| base | `base-` | base-skill-loader |
| general | `gen-` | gen-daily-planner |
| invest | `inv-` | inv-stock-data |

## 目录结构

```
custom-skills/                  # 技能源码（按分类隔离）
  base/                         # 基础技能（所有 profile 必含）
    base-skill-loader/          #   技能使用指南
  general/                      # 通用技能
    gen-daily-planner/          #   日程安排
    gen-dingtalk-group-report/  #   群聊月度消息分析报告
    gen-dingtalk-personal-daily/  #   个人每日工作日志
    gen-dingtalk-personal-weekly-mail/  #   个人周报邮件生成
    gen-dingtalk-team-weekly-review/    #   团队周报审阅总结
    gen-interviewer/            #   面试辅助
    gen-knowledge-curator/      #   知识管理
  invest/                       # 投资分析技能
    _shared/                    #   共享工具模块
    inv-stock-data/             #   数据层
    inv-web-crawler/            #   爬虫
    inv-valuation-engine/       #   估值引擎
    inv-qarp-strategy/          #   操作决策
    inv-porter-five-forces/     #   五力分析
    inv-tencent-indicators/     #   前置指标（腾讯）
    inv-research-analyzer/      #   研报分析
    inv-topic-researcher/       #   投资主题研究

custom-hooks/                   # Hooks 源码（按 agent 隔离）
  hermes/                       # Hermes 专属 hooks
    base-skill-loader/          #   技能加载 hook

lib/
  dotenv.py                     # .env 加载
  proxy.py                      # 代理检测
  pwright.py                    # Playwright 抓取
  git.py                        # Git 操作

deploy/
  sync.py                       # 部署同步
  deploy.json                   # 部署配置：profiles + agents

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
python deploy/sync.py --profile work          # 同步 work 场景
python deploy/sync.py --profile home --dry-run # 预览
python deploy/sync.py --profile home --agent hermes  # 仅同步指定 agent
python deploy/sync.py --profile home --hooks-only    # 仅同步 hooks
python deploy/sync.py --profile home --force   # 强制替换非空目录
python deploy/sync.py --list                  # 列出可用 profiles
```

同步时会自动清理目标目录中不在当前 profile 范围内的过期软链接。

## 技能依赖关系

```
inv-stock-data（数据层）────────────────────────────┐
  ↑                                                │
  ├── inv-valuation-engine（估值引擎）              │
  │     ↑                                          │
  │     └── inv-qarp-strategy（操作决策）           │
  ├── inv-porter-five-forces（五力分析）            │
  └── (其他技能通过 CLI 子进程调用)                  │

inv-topic-researcher ─┐
  ├── inv-web-crawler（搜索+抓取）
  └── gen-knowledge-curator（存储）  ↑ 串联两个技能的编排层

inv-tencent-indicators（前置指标，独立脚本）
inv-research-analyzer（研报分析，独立脚本）
```

## 技术栈

- Python 3.10+，uv 包管理
- 数据源：akshare（A股）、yfinance（美港股）、pymupdf（PDF）、playwright（浏览器抓取）

## 新建 Skill

```bash
mkdir -p custom-skills/<category>/<prefix>-<name>/{scripts,references}
touch custom-skills/<category>/<prefix>-<name>/SKILL.md
cat > custom-skills/<category>/<prefix>-<name>/_meta.json << 'EOF'
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

- 不同分类目录下技能必须隔离，禁止跨分类引用
- 技能命名必须遵循 `{前缀}-{语义名}` 格式