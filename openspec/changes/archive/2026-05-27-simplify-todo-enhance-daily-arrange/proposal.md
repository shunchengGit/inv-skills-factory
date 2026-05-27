## Why

当前 `todo` 技能承担了数据 CRUD + 日程编排双重职责（`today`/`week` 命令混合输出待办、固定例程、高优任务），而 `daily-arrange` 也做编排但依赖解析 `todo today` 的文本输出，编排逻辑散落两处且耦合脆弱。将 `todo` 简化为纯数据层，把编排逻辑集中到 `daily-arrange`，形成清晰的"数据-编排"分层。

## What Changes

- **todo: 删除 `today` / `week` 命令** — 这两个命令做"展示编排"，不属于数据 CRUD。**BREAKING**：依赖 `todo.py today` 文本输出的调用方需迁移到新 `list` 命令
- **todo: 新增 `list` 命令** — 纯 JSON 输出今日待办（`{date, tasks}`），不读 ROUTINES.md、不读 TODO.md 高优段、不做任何格式化
- **todo: `init` 命令精简** — 去掉对 ROUTINES.md 和 TODO.md 高优段的解析输出，只做 git clone/pull + 输出今日待办 JSON
- **todo: 移除 ROUTINES.md 相关解析逻辑** — `_parse_daily_routines`、`_parse_weekly_routines`、`_parse_table_section`、`_daily_template` 全部删除
- **daily-arrange: 新增 `routines.md`** — 自己的日程配置文件，含每日固定（有时间点）和每周固定（有星期+时间点），不再放在 todo 仓库
- **daily-arrange: 增强编排逻辑** — 消费 `dws calendar event list` JSON + `todo.py list` JSON + `routines.md`，输出结构化今日/本周计划
- **daily-arrange: 新增 `week` 模式** — 整周日历+待办+每周固定例程的编排视图

## Capabilities

### New Capabilities
- `daily-arrange-schedule`: daily-arrange 技能的日程编排能力 — 消费日历 JSON + 待办 JSON + routines 配置，输出结构化每日/每周计划

### Modified Capabilities
- `todo-git-sync`: `init` 输出精简（去掉 routines/high_priority 聚合），移除 `today`/`week` 命令，新增 `list` 命令（纯 JSON）

## Impact

- 影响文件：`custom-skills/general/todo/scripts/todo.py`（重写，~465 → ~250 行）、`custom-skills/general/todo/SKILL.md`（更新命令文档）、`custom-skills/general/daily-arrange/SKILL.md`（增强编排指令）、`custom-skills/general/daily-arrange/routines.md`（新增）
- `~/.todo/ROUTINES.md` 不再被 todo 技能读取，用户需将例程配置迁移到 daily-arrange 的 `routines.md`
- 不影响其他 invest 技能
