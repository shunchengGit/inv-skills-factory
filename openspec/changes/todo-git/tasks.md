## 1. Git 基础设施

- [x] 1.1 从 `knowledge-mgr` 搬运 `_run_git`、`_is_git_repo`、`_same_remote`、`_git_sync` 到 `todo.py`，改常量为 `TODO_REPO`/`TODO_DIR`

## 2. init 命令

- [x] 2.1 实现 `cmd_init`：clone → 或 pull，返回 JSON（含 `success`/`action`/error/hint）
- [x] 2.2 实现 `parse_today`：解析 `~/.todo/YYYY-MM-DD.md` 中的 `- [ ]` / `- [x]` 行，提取优先级 emoji
- [x] 2.3 实现 `parse_high_priority`：从 `~/.todo/TODO.md` 提取 `## 高优` section 全部行
- [x] 2.4 init 成功后输出合并 JSON（today + high_priority）

## 3. today 命令

- [x] 3.1 实现 `cmd_today`：读本地文件，输出今日待办 + 高优（不触发 git），文本格式

## 4. add 命令

- [x] 4.1 实现 `cmd_add`：git pull → 追加 `- [ ] emoji task` 到今日文件 → `_git_sync("add: ...")`
- [x] 4.2 今日文件不存在时自动创建 `# YYYY-MM-DD\n` 头

## 5. done 命令

- [x] 5.1 实现 `cmd_done`：git pull → 在今日文件 + TODO.md 中替换 `- [ ]` 为 `- [x]` → `_git_sync("done: ...")`
- [x] 5.2 无匹配时不触发 git 操作

## 6. 收尾

- [x] 6.1 更新 `SKILL.md`：新命令文档、新数据路径 `~/.todo`
- [x] 6.2 运行 `sync_skills.py --category general` 同步到 Agent
- [x] 6.3 端到端验证：init → today → add → done 全流程
