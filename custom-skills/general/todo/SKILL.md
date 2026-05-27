---
name: todo
description: >-
  TODO 管理技能（git 仓库驱动，多设备同步）。从 git@github.com:shunchengGit/todo.git 拉取数据。
  当用户说"今天要做什么""添加任务""标记完成""看看待办""本周计划""我的日程"时，使用本技能。
metadata:
  openclaw:
    emoji: ✅
---

# TODO Manager

Git 仓库驱动的 TODO 管理，数据存储在 `~/.todo/`（remote `git@github.com:shunchengGit/todo.git`，master 分支）。

纯数据层——只做任务的增删改查 + git 同步。展示和编排由 `daily-arrange` 技能负责。

## 命令

| 命令 | 用途 | git 操作 |
|------|------|----------|
| `python3 scripts/todo.py init` | 拉取仓库 + 输出 TODO.md 全量任务 JSON | clone/pull |
| `python3 scripts/todo.py add "内容"` | 添加任务（默认中优） | pull → write → commit → push |
| `python3 scripts/todo.py add "内容" --priority high` | 添加高优任务 | 同上 |
| `python3 scripts/todo.py done "关键词"` | 标记任务完成 | pull → mark → commit → push |

## init 输出

```json
{
  "success": true,
  "action": "clone|pull",
  "tasks": {
    "high": [{"status": "pending", "priority": "high", "content": "..."}],
    "important_not_urgent": [...],
    "deferred": [...],
    "done": [...]
  }
}
```

## 数据

```
~/.todo/                    ← git 仓库
├── TODO.md                 # 任务总池（高优/重要不紧急/暂缓/已完成）
└── YYYY-MM-DD.md           # 每日日志（add/done 的落点）
```

## 典型工作流

```
1. todo.py init           ← 拉取最新数据，Claude 感知全量任务池
2. todo.py add "xxx"      ← 添加任务，自动 push
3. todo.py done "xxx"     ← 完成任务，自动 push
```

## 依赖

- Python 3.10+，标准库 only
- git（命令行）
