## ADDED Requirements

### Requirement: Initialize todo repository
The system SHALL clone or pull the remote git repository `git@github.com:shunchengGit/todo.git` (master branch) to `~/.todo` and output all tasks from `~/.todo/TODO.md` grouped by section as structured JSON. The system SHALL NOT read `ROUTINES.md` or parse routines data.

#### Scenario: First run — clone
- **WHEN** `~/.todo` does not exist and user runs `init`
- **THEN** system clones `git@github.com:shunchengGit/todo.git` to `~/.todo` and outputs `{"success": true, "action": "clone", "tasks": {"high": [...], "important_not_urgent": [...], "deferred": [...], "done": [...]}}`

#### Scenario: Already cloned — pull
- **WHEN** `~/.todo` exists with correct remote and user runs `init`
- **THEN** system runs `git pull` in `~/.todo` and outputs `{"success": true, "action": "pull", "tasks": {...}}`

#### Scenario: Wrong remote
- **WHEN** `~/.todo` exists but remote URL does not match
- **THEN** system outputs `{"success": false, "error": "...", "hint": "..."}` and exits with code 1

#### Scenario: Clone failure
- **WHEN** clone fails (network, SSH key, repo not found)
- **THEN** system outputs `{"success": false, "action": "clone", "error": "...", "hint": "..."}` and exits with code 1

### Requirement: Add task with git sync
The system SHALL pull latest changes, append a task to today's file, then commit and push.

#### Scenario: Successful add
- **WHEN** user runs `add "任务内容" --priority high` and git operations succeed
- **THEN** system runs `git pull`, appends `- [ ] 🔴 任务内容` to `~/.todo/YYYY-MM-DD.md`, runs `git add -A && git commit -m "add: 任务内容" && git push`, outputs success

#### Scenario: Push rejected
- **WHEN** `git push` fails (non-fast-forward)
- **THEN** system outputs warning "push 失败，本地已保存。请手动 git pull 后重新 push" and exits with code 0 (local save succeeded)

#### Scenario: Today file does not exist yet
- **WHEN** today's file does not exist and user runs `add`
- **THEN** system creates the file with `# YYYY-MM-DD\n\n` header before appending the task

### Requirement: Mark task done with git sync
The system SHALL pull latest changes, replace `- [ ]` with `- [x]` for matching tasks in today's file and TODO.md, then commit and push.

#### Scenario: Successful mark done
- **WHEN** user runs `done "关键词"` and the keyword matches an unchecked task
- **THEN** system replaces `- [ ] 关键词...` with `- [x] 关键词...`, runs git commit+push

#### Scenario: No match found
- **WHEN** user runs `done "关键词"` and no unchecked task matches
- **THEN** system outputs "未找到包含 '关键词' 的未完成任务" and does NOT trigger git operations

#### Scenario: Push fails after done
- **WHEN** `git push` fails after marking done
- **THEN** system outputs warning, local changes preserved

### Requirement: List all tasks from TODO.md
The system SHALL provide an internal function `_list_todo_md()` that reads `~/.todo/TODO.md` and parses all `##` sections, extracting checkbox items with status and priority for each section. This function SHALL be called by `init` to populate the `tasks` field in its JSON output.

#### Scenario: TODO.md has multiple sections
- **WHEN** `_list_todo_md()` is called and TODO.md has `## 高优`, `## 重要不紧急`, `## 暂缓`, `## 已完成` sections
- **THEN** system returns a dict with keys `high`, `important_not_urgent`, `deferred`, `done`, each containing an array of `{status, priority, content}` objects

#### Scenario: TODO.md section is empty
- **WHEN** `_list_todo_md()` is called and a section has no checkbox items
- **THEN** system returns an empty array for that section key

#### Scenario: TODO.md does not exist
- **WHEN** `_list_todo_md()` is called and `~/.todo/TODO.md` does not exist
- **THEN** system returns an empty dict `{}`
