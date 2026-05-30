---
name: gen-dingtalk-group-report
description: 按月维度拉取指定钉钉群聊消息到本地，并生成数据分析报告。基于 dws CLI 实现。
version: 1.0.0
trigger:
  - 月度群消息分析
  - 群消息月报
  - 拉取群聊月度消息
  - dingtalk group monthly analysis
  - 客服群月度分析
  - 月度消息拉取
  - 群消息数据分析
---

# 钉钉群聊月度消息拉取与分析

## 概述

按月维度拉取指定钉钉群聊的历史消息到本地 JSON 文件，然后对消息数据进行多维度分析并生成可视化 HTML 报告。

**执行方式**：通过 `dws`（DingTalk Workspace CLI）命令行工具操作。

## 前置条件

1. `dws` 已安装且已登录（详见 `gen-dingtalk` 前置条件）
2. 已授权 `chat:message` 权限（读取群消息所需）

## 中文编码注意事项

`dws` 在 LC_CTYPE=C 环境下终端中文乱码，但 raw bytes 是正确 UTF-8。**必须使用 Python subprocess capture_output + decode('utf-8') 读取**，禁止直接在 Bash 中用管道处理 `dws` 的中文输出。

```python
import subprocess, json
result = subprocess.run(cmd, capture_output=True, timeout=30)
data = json.loads(result.stdout.decode('utf-8'))
```

## 流程步骤

### Step 1: 确定参数

用户需指定（或由技能推断）：
- **群聊 convId**：目标群的 openConversationId
- **目标月份**：如 "2026-04" 表示拉取 2026 年 4 月的消息

已知常量：
- 客服问题反馈群 convId: `cidGu2NRRnnLvzO014c19vtVg==`

如用户未指定 convId，可先通过 `dws chat message list-all` 拉取近期消息来获取群列表，或询问用户。

### Step 2: 计算时间范围

根据目标月份计算：
- `start_time`: `YYYY-MM-01 00:00:00`
- `end_time`: `YYYY-MM-DD 23:59:59`（DD 为该月最后一天）

### Step 3: 按周分批拉取消息

**核心策略**：使用 `dws chat message list` 按**周**分批拉取，避免 API 超时。

**为什么不直接用 `list-all`？**
- `dws chat message list-all` 适合短时间范围（7天内），长时间范围会超时
- `dws chat message list --group <convId>` 专拉单群历史，配合 `--forward=false` 从新往旧翻页

**拉取命令**：

```bash
dws chat message list --group <convId> --time <cursor> --forward=false --limit 50 --format json
```

**返回结构**：

```json
{
  "success": true,
  "result": {
    "hasMore": true,
    "messages": [
      {
        "content": "消息内容",
        "createTime": "2026-04-22 10:30:00",
        "sender": "发送人",
        "senderOpenDingTalkId": "...",
        "openMessageId": "唯一ID",
        "openConversationId": "群convId",
        "emotionReplyList": [...],
        "quotedMessage": {...}
      }
    ]
  }
}
```

**分批拉取 Python 脚本模板**：

```python
import subprocess, json, os
from datetime import datetime, timedelta
from collections import Counter

CONV_ID = "<convId>"  # 替换为实际 convId
OUTPUT_DIR = os.getcwd()

def fetch_messages_before(time_cursor, limit=50):
    """从 time_cursor 往回拉取一页消息"""
    cmd = [
        "dws", "chat", "message", "list",
        "--group", CONV_ID,
        "--time", time_cursor,
        "--forward=false",
        "--limit", str(limit),
        "--format", "json"
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    data = json.loads(result.stdout.decode('utf-8'))
    if not data.get('success', False):
        return [], False
    result_data = data.get('result', {})
    return result_data.get('messages', []), result_data.get('hasMore', False)

def fetch_range(start_time, end_time):
    """拉取指定时间范围内的所有消息"""
    all_messages = []
    cursor = end_time
    page = 0
    
    while True:
        page += 1
        messages, has_more = fetch_messages_before(cursor, limit=50)
        
        if not messages:
            break
        
        # 过滤在范围内的消息
        filtered = [m for m in messages 
                    if m.get('createTime','') >= start_time 
                    and m.get('createTime','') <= end_time]
        all_messages.extend(filtered)
        
        # 找最早消息时间作为下一页 cursor
        times = [m.get('createTime','') for m in messages if m.get('createTime')]
        if not times:
            break
        earliest = min(times)
        
        print(f"  Page {page}: {len(messages)} msgs, {len(filtered)} in range. Earliest: {earliest}")
        
        if earliest < start_time:
            break
        if not has_more:
            break
        cursor = earliest
        if page >= 200:  # 安全上限
            break
    
    return all_messages

# 将月份按周拆分为批次
def get_weekly_batches(year, month):
    """将一个月拆分为按周的批次"""
    import calendar
    first_day = datetime(year, month, 1)
    last_day = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
    
    batches = []
    current = first_day
    while current <= last_day:
        week_end = min(current + timedelta(days=6), last_day)
        batches.append((
            current.strftime('%Y-%m-%d 00:00:00'),
            week_end.strftime('%Y-%m-%d 23:59:59')
        ))
        current = week_end + timedelta(days=1)
    return batches

# 主流程
year, month = 2026, 4  # 替换为目标月份
batches = get_weekly_batches(year, month)
all_messages = []

for start, end in batches:
    print(f"\n=== Batch: {start} to {end} ===")
    msgs = fetch_range(start, end)
    print(f"  Result: {len(msgs)} messages")
    all_messages.extend(msgs)

# 去重（按 openMessageId）
seen = set()
unique = []
for m in all_messages:
    mid = m.get('openMessageId', '')
    if mid and mid not in seen:
        seen.add(mid)
        unique.append(m)

# 按时间排序
unique.sort(key=lambda m: m.get('createTime', ''))

# 保存
output_file = os.path.join(OUTPUT_DIR, f"kefu_feedback_{year}{month:02d}.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(unique, f, ensure_ascii=False, indent=2)
print(f"Saved {len(unique)} messages to {output_file}")
```

### Step 4: 数据分析与报告生成

对拉取的消息进行以下维度的分析，并生成 HTML 可视化报告：

**分析维度**：

1. **基础统计**：总消息数、发言人数、日均消息、引用回复数
2. **每日消息量趋势**：折线/柱状图
3. **消息时段分布**：24小时分布，区分工作时段(9-18)与非工作时段
4. **星期分布**：区分工作日与周末
5. **发言人排行**：Top 20 发言人及占比
6. **表情回应统计**：各类 emoji 使用频次
7. **高频关键词/工单号**：提取消息中的 6-8 位数字（疑似工单号）
8. **消息样本浏览**：最新 N 条消息快速浏览

**报告输出格式**：HTML 文件，内联 CSS + JavaScript，可直接在浏览器打开。

**报告命名**：`<群名>_<年月>_report.html`，如 `kefu_feedback_202604_report.html`

### Step 5: 展示报告

用 `preview_url` 工具在 WorkBuddy 内预览 HTML 报告。

## 注意事项

1. **分批拉取是必须的**：单次拉取超过约 7 天的数据会导致 API 超时，必须按周分批
2. **翻页方向**：`--forward=false` 表示从 cursor 时间往回翻（从新到旧），这是拉取历史消息的正确方向
3. **createTime 是字符串格式**：`"2026-05-22 13:27:21"`，不是毫秒时间戳，字符串比较即可判断时间先后
4. **去重必须做**：跨批次边界可能存在重复消息，按 `openMessageId` 去重
5. **安全页数上限**：每批最多翻 200 页（约 10,000 条），超出应停止并报告
6. **数据只追加不覆盖**：如果已有同月数据文件，应合并而非覆盖

## 已知常量

| 名称 | 值 | 说明 |
|------|----|------|
| 客服问题反馈群 convId | `cidGu2NRRnnLvzO014c19vtVg==` | 客服问题反馈群 |

## dws 命令清单

| 用途 | 命令 |
|------|------|
| 拉取单群消息 | `dws chat message list --group <convId> --time <cursor> --forward=false --limit 50 --format json` |
| 拉取全量消息(短期) | `dws chat message list-all --start <start> --end <end> --cursor <cursor> --limit 50 --format json` |
| 检查 dws 版本 | `dws version --format json` |
| 检查登录状态 | `dws auth status --format json` |
