---
name: gen-todo-tracker
description: 当需要查看、添加、完成或管理待办任务时使用，支持多设备同步的任务列表管理
metadata:

# TODO Manager

Git 仓库驱动的 TODO 管理，数据存储在 `~/.todo/`（remote `git@github.com:shunchengGit/todo.git`，master 分支）。

**单一数据源**——所有任务存储在 `TODO.md`，`add`/`done`/`init` 均操作此文件。每日日志文件已废弃。

## 命令

| 命令 | 用途 | git 操作 |
|------|------|----------|
| `python3 scripts/todo.py init` | 拉取仓库 + 输出 TODO.md 全量任务 JSON | clone/pull --rebase |
| `python3 scripts/todo.py add "内容"` | 添加任务（默认中优）到 TODO.md | pull --rebase → write → commit → push |
| `python3 scripts/todo.py add "内容" --priority high` | 添加高优任务 | 同上 |
| `python3 scripts/todo.py done "关键词"` | 完成任务（移到已完成 section） | pull --rebase → move → commit → push |
| `python3 scripts/todo.py done --id abc1234` | 按 ID 精确完成任务 | 同上 |
| `python3 scripts/todo.py migrate` | 合并每日日志到 TODO.md + 添加 ID | pull → merge → commit → push |

## 任务格式

每个任务行包含确定性 ID 注释，用 section 区分完成状态（无 `[x]`/`[ ]` checkbox）：

```
# 高优
- 🔴 任务内容 <!-- id:abc1234 -->

# 已完成
- 🟡 已完成任务 <!-- id:def5678 -->
```

- ID 由任务内容的 sha1 前 7 位生成，相同内容 = 相同 ID
- 完成状态由 section 决定，不需要 checkbox 标记
- `done` 支持关键词匹配（模糊）和 `--id`（精确），多个关键词匹配时返回候选列表

## init 输出

```json
{
  "success": true,
  "action": "clone|pull",
  "tasks": {
    "high": [{"status": "pending", "priority": "high", "content": "...", "id": "abc1234"}],
    "important_not_urgent": [...],
    "deferred": [...],
    "done": [...]
  }
}
```

## 数据

```
~/.todo/                    ← git 仓库
└── TODO.md                 # 唯一数据源（高优/重要不紧急/暂缓/已完成）
```

## 典型工作流

```
1. todo.py init           ← 拉取最新数据，感知全量任务池
2. todo.py add "xxx"      ← 添加任务到 TODO.md，自动 push
3. todo.py done "xxx"     ← 完成任务，移到已完成 section，自动 push
```

## git 同步安全

- 写入前 `pull --rebase`，写入后 `add TODO.md` + commit + push
- push 失败自动重试（最多 2 次）
- rebase 冲突时 abort 并返回明确错误

## 依赖

- Python 3.10+，标准库 only
- git（命令行）
