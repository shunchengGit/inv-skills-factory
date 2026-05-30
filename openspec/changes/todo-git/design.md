## Context

当前 `todo.py` 在 `~/Assist/TODO/` 下做纯文件读写，无多设备同步能力。`gen-knowledge-curator` 已验证 git 仓库 + pull-before-write + commit+push 模式在单人+多设备场景下可行。本设计将同一模式移植到 TODO 管理。

## Goals / Non-Goals

**Goals:**
- 单脚本 `todo.py`，`init`/`today`/`add`/`done` 四个子命令
- 数据存储在 `~/.todo/`（git 仓库，remote `git@github.com:shunchengGit/todo.git`，master 分支）
- 写操作（add/done）自动 git pull → write → commit → push
- 读操作（init/today）输出结构化 JSON，供 AI agent 解析
- 直接复用 `gen-knowledge-curator` 的 git 操作模式

**Non-Goals:**
- 不处理 `archive`（MVP 外）
- 不迁移 `~/Assist/TODO/` 历史数据
- 不处理多人协作冲突（仅单人使用）

## Decisions

### 1. 单脚本 vs 多脚本

**选单脚本 `todo.py` + 子命令。** 参考 `assist` 技能的风格（一个脚本管理一个领域），而不是 `gen-knowledge-curator` 的多脚本拆分。TODO 的领域逻辑极少（增删查改），多脚本会增加路径引用复杂度，收益为零。

### 2. Git 同步策略：pull-before-write

每次 `add`/`done` 先 `git pull` 再写文件。采用 fast-forward-only（默认行为），不自动 merge。push 失败 → 本地保留 + 警告用户手动处理。与 `km_import.py` 中的 `_git_sync` 行为完全一致。

```
add "xxx"
  → git pull (fast-forward)
  → 追加行到 YYYY-MM-DD.md
  → git add -A
  → git commit -m "add: xxx"
  → git push
  → 成功 ✓ 或 警告 "push 失败，本地已保存"
```

### 3. 今日文件命名

沿用现有格式 `YYYY-MM-DD.md`（如 `2026-05-27.md`），与 `assist/todo.py` 完全兼容。主清单仍为 `TODO.md`。

### 4. 输出格式：JSON（init）vs 文本（today）

- `init` → JSON：作为 Agent 工作流入口，AI 需要结构化数据来计划今日工作
- `today` → 文本：快速查看，人类可读，不触发 git

### 5. init 输出结构

```json
{
  "success": true,
  "action": "clone|pull",
  "today": {
    "date": "2026-05-27",
    "tasks": [
      {"status": "pending", "priority": "high", "content": "完成周报"},
      {"status": "pending", "priority": "medium", "content": "review PR"}
    ]
  },
  "high_priority": [
    {"status": "pending", "priority": "high", "content": "Q2 规划"},
    {"content": "非 task 行（无 checkbox）"}
  ]
}
```

`today.tasks` 仅解析 `- [ ]` / `- [x]` 行，提取优先级 emoji（🔴/🟡/⚪）和内容。`high_priority` 从 `TODO.md` 的 `## 高优` section 提取全部行。

### 6. 复用 gen-knowledge-curator 的 git 工具函数

`_run_git`、`_is_git_repo`、`_same_remote`、`_git_sync` 四个函数从 `km_init.py` + `km_import.py` 照搬，只改常量（REPO_URL、TODO_DIR）。不抽取共享库 —— 技能隔离原则。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| `git push` 在弱网环境超时 | 本地已保存，push 失败不丢数据，仅警告 |
| 同一天在两设备分别 add 后 push，第二个会冲突 | 警告用户手动 `git pull`，单人场景极少发生 |
| `~/.todo` 目录被误删 | git clone 可恢复，数据在远程 |
