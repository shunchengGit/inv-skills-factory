## Context

当前 `todo.py`（~465 行）混合了数据 CRUD（add/done）和展示编排（today/week），且 `today` 命令为了展示"今日全貌"，同时读取三个文件（今日文件、ROUTINES.md、TODO.md 高优段）。`daily-arrange` 作为编排层再解析其文本输出，编排逻辑两处冗余且耦合脆弱。

本设计将 todo 简化为纯数据层（只关心 TODO.md 和每日文件的读写），所有编排逻辑集中到 daily-arrange。

### 现有数据文件

```
~/.todo/
├── TODO.md          # 任务总池：## 高优 / ## 重要不紧急 / ## 暂缓 / ## 已完成
├── ROUTINES.md      # 日程配置：## 每日固定 / ## 每周固定（无时间点）
└── YYYY-MM-DD.md    # 每日日志：add/done 的落点文件
```

### ROUTINES.md 当前格式

```markdown
## 每日固定
| 事项 | 大概时长 |
|------|------|
| 晨间阅读 | 60min |

## 每周固定
| 事项 | 大概时长 | 星期 |
|------|------|------|
| 周会 | 60min | 周一 |
```

问题：没有具体时间点，daily-arrange 无法做时间排布。

## Goals / Non-Goals

**Goals:**
- todo.py 缩减为三个命令：`init`（git clone/pull）、`add`（写入 + git push）、`done`（标记 + git push）。新增内部函数 `_list_todo_md()` 供 init 输出用
- todo.py 删除所有 routines 解析逻辑（~100 行）和 `today`/`week` 命令（~70 行）
- daily-arrange 拥有自己的 `routines.md`，带时间点
- daily-arrange 通过两个 CLI 调用获取结构化数据：`dws calendar event list --format json` + `python3 todo.py init`（JSON）

**Non-Goals:**
- 不改变 git 同步策略（pull-before-write 不变）
- 不改变 `~/.todo` 仓库结构
- 不动 `YYYY-MM-DD.md` 的 add/done 落地逻辑
- 不实现 daily-arrange 的 Python 脚本——保持纯 SKILL.md 指令驱动

## Decisions

### 1. 命令精简：三个命令 vs 四个命令

**删 `today`/`week`，`list` 合并到 `init` 输出中。**

`init` 已经输出 JSON，只需要改其输出结构——去掉 routines/high_priority 聚合，改为输出 TODO.md 的全量 sections：

```json
{
  "success": true,
  "action": "clone|pull",
  "tasks": {
    "high": [
      {"status": "pending", "priority": "high", "content": "Q2 规划"},
      {"status": "done", "priority": "high", "content": "完成周报"}
    ],
    "important_not_urgent": [...],
    "deferred": [...],
    "done": [...]
  }
}
```

新增 `_list_todo_md()` 内部函数，遍历 TODO.md 所有 ## section，每个 section 下解析 checkbox 行。

daily-arrange 调用 `todo.py init` 获取全量任务池，调用 `dws calendar event list --format json` 获取日历，读本地 `routines.md` 获取固定例程，三者合并编排。

如果 init 因网络不通失败，daily-arrange 降级：跳过 git pull 报错，直接读本地 `~/.todo/TODO.md` 文件。

### 2. routines.md 格式：加时间点

从 todo 仓库的 ROUTINES.md（无时间）升级为 daily-arrange 自己的 `routines.md`（有时间）：

```markdown
## 每日固定
| 事项 | 时间 | 时长 |
|------|------|------|
| 晨间阅读 | 07:00 | 60min |
| 健身 | 18:00 | 60min |

## 每周固定
| 事项 | 星期 | 时间 | 时长 |
|------|------|------|------|
| 周会 | 周一 | 09:00 | 60min |
| 代码评审 | 周五 | 15:00 | 90min |
```

加了 `时间` 列后，daily-arrange 可以直接按时间轴排布，不需要"猜测"例程该放哪个时段。

### 3. daily-arrange 编排算法

```python
# 伪代码
# 1. 固定时间块（不可移动）
fixed_blocks = []
fixed_blocks += calendar_events                    # dws calendar event list
fixed_blocks += daily_routines                     # routines.md 每日固定
fixed_blocks += weekly_routines_for_today          # routines.md 每周固定中匹配今天星期
fixed_blocks.sort(by=start_time)

# 2. 空闲时段
free_slots = []
cursor = 06:00
for block in fixed_blocks:
    if cursor < block.start:
        free_slots.append((cursor, block.start))
    cursor = max(cursor, block.end)

# 3. 填充待办（优先级：高优 → 重要不紧急 → 暂缓）
for slot in free_slots:
    duration = slot.end - slot.start
    # 从任务池取下一个匹配时长的任务，预估每个 30-60min
    ...

# 4. 剩余未排入的任务列在「待排」区
```

### 4. week 模式

daily-arrange 的 week 模式按天循环上述算法，每周固定例程按星期匹配：

```
python3 todo.py init                          ← 一次拉取全量任务池
dws calendar event list --start Mon --end Sun ← 一周日历
读 routines.md                                ← 每日固定 + 每周固定
→ 输出 7 天计划
```

### 5. 删除代码清单

从 `todo.py` 删除的函数和变量：

| 删除项 | 行数（估算） | 原因 |
|--------|-------------|------|
| `_parse_daily_routines()` | 5 | 移到 daily-arrange 的 routines.md |
| `_parse_weekly_routines()` | 5 | 同上 |
| `_parse_table_section()` | 25 | 只被 routines 解析使用 |
| `_daily_template()` | 15 | 创建文件时的默认模板，不再需要 |
| `_week_monday()` | 5 | 只被 week 命令使用 |
| `WEEKDAY_NAMES` | 1 | 不再需要 |
| `cmd_today()` | 30 | 合并到 daily-arrange |
| `cmd_week()` | 45 | 合并到 daily-arrange |

保留的函数：`_run_git`、`_is_git_repo`、`_same_remote`、`_git_sync`、`_init_repo`、`_parse_tasks`、`_parse_section_lines`、`cmd_init`、`cmd_add`、`cmd_done`

新增函数：`_list_todo_md()` — 解析 TODO.md 所有 section 为 JSON

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| ROUTINES.md 迁移遗漏 | 用户手动将旧 ROUTINES.md 内容转为 daily-arrange 的 routines.md 格式，内容量小（通常 <10 行），一次性操作 |
| init 网络不通时 daily-arrange 无数据 | daily-arrange 降级：git pull 失败时直接 `cat ~/.todo/TODO.md` 解析本地文件 |
| `_parse_section_lines` 删除后 `cmd_done` 不可用 | `cmd_done` 仍然需要它来标记 TODO.md 中的任务——保留这个函数 |
| daily-arrange 无脚本，纯指令驱动可能编排质量不稳定 | 当前 todo.py 的 today/week 编排也很简单（纯拼接），daily-arrange 由 Claude 做编排决策，质量上限更高 |
