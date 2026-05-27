## 1. todo.py 精简

- [x] 1.1 删除 ROUTINES 解析函数：`_parse_daily_routines`、`_parse_weekly_routines`、`_parse_table_section`、`_daily_template`
- [x] 1.2 删除展示命令：`cmd_today`、`cmd_week`、`_week_monday`、`WEEKDAY_NAMES`
- [x] 1.3 新增 `_list_todo_md()` 函数，解析 `~/.todo/TODO.md` 所有 `##` section，输出 `{high: [...], important_not_urgent: [...], deferred: [...], done: [...]}`
- [x] 1.4 修改 `cmd_init`：去掉 routines/high_priority 聚合，改为调用 `_list_todo_md()` 输出 `tasks` 字段
- [x] 1.5 修改 `__main__`：移除 `today`/`week` 子命令注册

## 2. daily-arrange 配置文件

- [x] 2.1 创建 `preferences.md`：工作时段 09:00-20:00、午休 12:00-13:30、晚间休息 18:00-19:00、过滤 `[提醒]` 前缀日历事件
- [x] 2.2 创建 `routines.md`：每日固定（带时间+时长）、每周固定（带星期+时间+时长）

## 3. daily-arrange SKILL.md 重写

- [x] 3.1 更新执行流程：加载 preferences → 调 dws calendar → 调 todo.py init → 读 routines.md → 编排输出
- [x] 3.2 写明日历过滤规则：`[提醒]` 前缀事件排除
- [x] 3.3 写明编排算法：固定块（日历+例程+休息）→ 空闲时段 → 按高优→重要不紧急→暂缓填充
- [x] 3.4 输出格式含时间轴，已排任务带时段，未排任务列在「待排」
- [x] 3.5 新增 week 模式说明

## 4. todo SKILL.md 更新

- [x] 4.1 删除 `today`/`week` 命令文档
- [x] 4.2 更新 `init` 命令说明：输出 TODO.md 全量 sections JSON
- [x] 4.3 移除 ROUTINES.md 引用

## 5. 同步与验证

- [x] 5.1 运行 `sync_skills.py --category general` 同步到所有 agent
- [x] 5.2 端到端验证：`todo.py init` JSON 输出正确、daily-arrange 编排输出正确
