---
name: daily-arrange
description: >-
  每日安排技能。从 dingding 读取钉钉日历，从 todo 读取待办任务池，结合本地固定例程和偏好设置，输出结构化每日/每周时间计划。
  当用户说"今天怎么安排""每日安排""今天有什么""排一下今天""本周计划""today plan"时使用本技能。
version: 0.2.0
metadata:
  openclaw:
    emoji: 📋
---

# 每日安排 (Daily Arrange)

整合钉钉日历 + TODO 任务池 + 固定例程 + 偏好设置，输出时间轴计划。

## 配置文件

| 文件 | 说明 |
|------|------|
| `preferences.md` | 工作时段时间、休息时段、日历过滤规则、任务时长预估规则 |
| `routines.md` | 每日固定例程（时间+时长）、每周固定例程（星期+时间+时长） |

## 数据来源

| 来源 | 命令 | 产出 |
|------|------|------|
| 钉钉日历 | `dws calendar event list --start <今日T00:00:00+08:00> --end <明日T00:00:00+08:00> --format json` | 今日日程列表 |
| TODO 任务池 | `python3 custom-skills/general/todo/scripts/todo.py init` | JSON: `{success, action, tasks: {high, important_not_urgent, deferred, done}}` 每个任务含 `id` 字段 |
| 偏好设置 | `custom-skills/general/daily-arrange/preferences.md` | 工作时段、休息、过滤规则 |
| 固定例程 | `custom-skills/general/daily-arrange/routines.md` | 每日/每周固定事项 |

## 执行流程

### Step 1: 加载偏好设置

从 `preferences.md` 读取：
- 工作时段：09:00-20:00
- 午休：12:00-13:30
- 晚间休息：18:00-19:00
- 日历过滤：排除以 `[提醒]` 开头的事件、organizer 含 `Teambition` 的事件
- 任务时长预估：快速任务(回复/检查/确认/提交)30min，标准任务60min，大型任务(报告/方案/设计/写/整理)90min

### Step 2: 获取钉钉日历日程

```bash
dws calendar event list --start "YYYY-MM-DDT00:00:00+08:00" --end "YYYY-MM-DDT23:59:59+08:00" --format json
```

从返回 JSON 中提取每个日程：
- `summary`（标题）→ 过滤：以 `[提醒]` 开头的**排除**
- `organizer.displayName` → 过滤：含 `Teambition` 的**排除**，不占时间块
- `start.dateTime` / `end.dateTime` → 时间范围
- `location.displayName` → 地点（可选）

### Step 3: 获取 TODO 任务池

```bash
python3 custom-skills/general/todo/scripts/todo.py init
```

从 JSON 的 `tasks` 字段获取全量任务池，按 section 分组：
- `high` → 高优，优先安排
- `important_not_urgent` → 重要不紧急，高优排完后安排
- `deferred` → 暂缓，最后安排
- `done` → 忽略（已完成）

如果 `init` 失败（网络不通），降级为直接读取 `~/.todo/TODO.md`，手动解析 `##` section。

### Step 4: 读取固定例程

从 `routines.md` 读取：
- **每日固定**：`| 事项 | 时长 | 推荐时间 |` 表格行。有推荐时间的优先安排在该时段，若被日历占用则浮动到最近空闲时段；无推荐时间的灵活排入空闲时段。标注 🔁
- **每周固定**：`| 事项 | 时长 | 推荐时间 |` 表格行。放入本周任务池，尽量安排，标注 🔁

### Step 5: 编排时间块

按以下规则生成今日时间轴（06:00-24:00）：

1. **构建固定时间块列表**：
   - 日历日程（已过滤 `[提醒]`）
   - 休息时段（午休 12:00-13:30、晚间 18:00-19:00）
   - 按开始时间排序

2. **计算空闲时段**：
   - 从 09:00（工作开始）遍历到 20:00（工作结束）
   - 固定块之间的空隙即为空闲时段
   - 忽略 <30min 的空隙（无法安排任何任务）

3. **填充任务**（优先级：每日例程 🔁 > 高优 🔴 > 重要不紧急 🟡 > 暂缓 ⚪）：
   - 先排每日固定例程（从 routines.md），按时长占用空闲时段
   - 再排高优任务（从 todo init）
   - 再排重要不紧急任务
   - 最后排暂缓任务
   - 每周例程放到本周任务池，day 模式下列在「本周待安排」提醒，week 模式下列入本周计划

4. **未排任务**：无法安排的任务列入「待排」区域

### Step 6: 输出

```
=== 今日安排 YYYY-MM-DD 周X ===

📅 日程（固定时间）
  09:00-10:00  周会  📍3楼会议室A
  14:00-15:00  项目评审  📍线上

🔁 每日例程
  10:00-10:30  招聘简历获取 (30min)

🍽 休息
  12:00-13:30  午休
  18:00-19:00  晚间休息

✅ 待办
  10:30-11:30  🔴 完成Q2季度报告
  13:30-14:00  🟡 回复邮件
  15:00-16:00  🟡 代码审查

📥 待排
  ⚪ 阅读行业资讯
```

## Week 模式

用户说"本周计划"时触发：

1. 以本周一 00:00 到周日 23:59 为时间范围调 `dws calendar event list`
2. 调用 `todo.py init` 一次获取全量任务池
3. 读取 `routines.md` 每日固定 + 每周固定
4. 按天循环上述编排算法
5. 输出 7 天计划概览（每天一个简要时间块表 + 每日待办列表）

## 注意事项

- 日历日程时间不可调整，待办围绕日程排布
- 时区默认为 Asia/Shanghai (UTC+8)
- `dws` 命令需要已登录钉钉授权
- `todo.py init` 需要 SSH key 配置（访问 GitHub）
- 如果 `init` 网络不通，降级直接读 `~/.todo/TODO.md`
