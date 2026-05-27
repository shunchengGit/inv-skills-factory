## Why

当前 `todo.py` 纯本地文件操作（`~/Assist/TODO/`），无版本历史、无法多设备同步。参考 `knowledge-mgr` 的 git 仓库模式，将 TODO 数据纳入版本管理，实现单人+多设备间的自然同步。

## What Changes

- **新增 `init` 命令**：clone/pull `git@github.com:shunchengGit/todo.git`（master 分支）到 `~/.todo`，输出今日待办 + 高优任务 JSON。
- **数据目录迁移**：从 `~/Assist/TODO/` 改为 `~/.todo/`（git 仓库）。**BREAKING**：依赖原路径的外部调用需更新（`assist` 技能中的 `todo.py` 副本不受影响）。
- **`add` / `done` 命令增加 git 同步**：pull → 写文件 → git add -A → commit → push。push 失败时本地保留，提示手动 pull。
- **`today` 保持只读**：不触发 git 操作，保证瞬时响应。
- **`archive` 暂不做**：MVP 不包含，git history 本身已记录状态变更。

## Capabilities

### New Capabilities
- `todo-git-sync`: git clone/pull/push 集成，数据存储在 `~/.todo` 仓库

### Modified Capabilities
<!-- None: this is a new skill, no existing specs to modify -->

## Impact

- 影响文件：`custom-skills/general/todo/scripts/todo.py`（重写）、`custom-skills/general/todo/SKILL.md`（更新命令文档）
- 不涉及其他技能
- 依赖：Python 标准库 + git（命令行），无第三方包
