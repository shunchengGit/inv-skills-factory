## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Read today's tasks
**Reason**: The `today` command is removed. Its display logic moves to `daily-arrange` skill. Task data is now accessed via `init` (JSON output of TODO.md sections) instead.
**Migration**: Callers should use `todo.py init` to get the full task pool as JSON, or read `~/.todo/TODO.md` directly for a lightweight local read.

## ADDED Requirements

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
