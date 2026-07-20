## ADDED Requirements

### Requirement: Initialize todo repository
The system SHALL clone or pull the remote git repository `git@github.com:shunchengGit/todo.git` (master branch) to `~/.todo` and output today's pending tasks plus high-priority tasks as structured JSON.

#### Scenario: First run — clone
- **WHEN** `~/.todo` does not exist and user runs `init`
- **THEN** system clones `git@github.com:shunchengGit/todo.git` to `~/.todo` and outputs `{"success": true, "action": "clone", "today": {...}, "high_priority": [...]}`

#### Scenario: Already cloned — pull
- **WHEN** `~/.todo` exists with correct remote and user runs `init`
- **THEN** system runs `git pull` in `~/.todo` and outputs `{"success": true, "action": "pull", "today": {...}, "high_priority": [...]}`

#### Scenario: Wrong remote
- **WHEN** `~/.todo` exists but remote URL does not match
- **THEN** system outputs `{"success": false, "error": "...", "hint": "..."}` and exits with code 1

#### Scenario: Clone failure
- **WHEN** clone fails (network, SSH key, repo not found)
- **THEN** system outputs `{"success": false, "action": "clone", "error": "...", "hint": "..."}` and exits with code 1

### Requirement: Read today's tasks
The system SHALL read the local `~/.todo/YYYY-MM-DD.md` file and the `## 高优` section from `~/.todo/TODO.md` without triggering any git operations.

#### Scenario: Today file exists
- **WHEN** user runs `today` and today's file exists
- **THEN** system reads and outputs the file content plus high-priority tasks from TODO.md

#### Scenario: Today file does not exist
- **WHEN** user runs `today` and no file exists for today
- **THEN** system outputs an empty result indicating no tasks for today

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
