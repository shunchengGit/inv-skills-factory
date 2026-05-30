#!/usr/bin/env python3
"""
按月拉取钉钉群聊消息并生成数据分析HTML报告。

Usage:
    python3 group_monthly_analysis.py --conv-id <CONV_ID> --year 2026 --month 4 --output-dir ./
"""

import argparse
import calendar
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta


ENV = {**os.environ, "LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"}


def fetch_messages_before(conv_id, time_cursor, limit=50):
    """从 time_cursor 往回拉取一页消息"""
    cmd = [
        "dws", "chat", "message", "list",
        "--group", conv_id,
        "--time", time_cursor,
        "--forward=false",
        "--limit", str(limit),
        "--format", "json"
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30, env=ENV)
    data = json.loads(result.stdout.decode('utf-8'))
    if not data.get('success', False):
        return [], False
    result_data = data.get('result', {})
    return result_data.get('messages', []), result_data.get('hasMore', False)


def fetch_range(conv_id, start_time, end_time):
    """拉取指定时间范围内的所有消息"""
    all_messages = []
    cursor = end_time
    page = 0

    while True:
        page += 1
        messages, has_more = fetch_messages_before(conv_id, cursor, limit=50)

        if not messages:
            break

        filtered = [m for m in messages
                    if m.get('createTime', '') >= start_time
                    and m.get('createTime', '') <= end_time]
        all_messages.extend(filtered)

        times = [m.get('createTime', '') for m in messages if m.get('createTime')]
        if not times:
            break
        earliest = min(times)

        print(f"  Page {page}: {len(messages)} msgs, {len(filtered)} in range. Earliest: {earliest}")

        if earliest < start_time:
            break
        if not has_more:
            break
        cursor = earliest
        if page >= 200:
            break

    return all_messages


def get_weekly_batches(year, month):
    """将一个月拆分为按周的批次"""
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


def analyze_messages(messages, year, month):
    """分析消息数据，返回统计结果"""
    if not messages:
        return {}

    # 基础统计
    total = len(messages)
    senders = Counter(m.get('sender', 'Unknown') for m in messages)
    sender_count = len(senders)

    # 按日期统计
    daily_counts = Counter()
    for m in messages:
        dt = datetime.strptime(m['createTime'], '%Y-%m-%d %H:%M:%S')
        daily_counts[dt.strftime('%Y-%m-%d')] += 1

    # 按小时统计
    hourly_counts = Counter()
    for m in messages:
        dt = datetime.strptime(m['createTime'], '%Y-%m-%d %H:%M:%S')
        hourly_counts[dt.hour] += 1

    # 按星期统计
    weekday_counts = Counter()
    for m in messages:
        dt = datetime.strptime(m['createTime'], '%Y-%m-%d %H:%M:%S')
        weekday_counts[dt.strftime('%A')] += 1

    # 表情回应
    emotion_counter = Counter()
    for m in messages:
        for emotion in m.get('emotionReplyList', []):
            emotion_counter[emotion.get('emotion', 'Unknown')] += 1

    # 提取疑似工单号（6-8位数字）
    ticket_pattern = re.compile(r'\b\d{6,8}\b')
    tickets = Counter()
    for m in messages:
        found = ticket_pattern.findall(m.get('content', ''))
        for t in found:
            tickets[t] += 1

    days_in_month = calendar.monthrange(year, month)[1]
    avg_daily = total / days_in_month

    return {
        'total': total,
        'sender_count': sender_count,
        'avg_daily': round(avg_daily, 1),
        'top_senders': senders.most_common(20),
        'daily_counts': dict(sorted(daily_counts.items())),
        'hourly_counts': {str(h): hourly_counts.get(h, 0) for h in range(24)},
        'weekday_counts': dict(weekday_counts),
        'top_emotions': emotion_counter.most_common(10),
        'top_tickets': tickets.most_common(10),
    }


def generate_html_report(messages, stats, year, month, output_path):
    """生成 HTML 可视化报告"""
    daily_data = list(stats['daily_counts'].items())
    daily_labels = [d[0][-2:] for d in daily_data]  # 只显示日期
    daily_values = [d[1] for d in daily_data]

    hourly_labels = list(range(24))
    hourly_values = [stats['hourly_counts'].get(str(h), 0) for h in hourly_labels]

    sender_rows = "\n".join(
        f"<tr><td>{name}</td><td>{count}</td><td>{count/stats['total']*100:.1f}%</td></tr>"
        for name, count in stats['top_senders']
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>群聊消息分析报告 {year}-{month:02d}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
.container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
h1 {{ color: #333; border-bottom: 2px solid #1890ff; padding-bottom: 10px; }}
.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
.stat-card {{ background: #f0f5ff; padding: 20px; border-radius: 8px; text-align: center; }}
.stat-value {{ font-size: 32px; font-weight: bold; color: #1890ff; }}
.stat-label {{ color: #666; margin-top: 5px; }}
.chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
.chart-container {{ background: #fafafa; padding: 15px; border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #f0f5ff; font-weight: 600; }}
</style>
</head>
<body>
<div class="container">
<h1>📊 群聊消息分析报告 {year}-{month:02d}</h1>

<div class="stats">
    <div class="stat-card"><div class="stat-value">{stats['total']}</div><div class="stat-label">总消息数</div></div>
    <div class="stat-card"><div class="stat-value">{stats['sender_count']}</div><div class="stat-label">发言人数</div></div>
    <div class="stat-card"><div class="stat-value">{stats['avg_daily']}</div><div class="stat-label">日均消息</div></div>
    <div class="stat-card"><div class="stat-value">{len(messages[0].get('emotionReplyList', [])) if messages else 0}</div><div class="stat-label">引用回复</div></div>
</div>

<div class="chart-row">
    <div class="chart-container"><canvas id="dailyChart"></canvas></div>
    <div class="chart-container"><canvas id="hourlyChart"></canvas></div>
</div>

<h2>👥 发言人排行 Top 20</h2>
<table>
<thead><tr><th>发言人</th><th>消息数</th><th>占比</th></tr></thead>
<tbody>{sender_rows}</tbody>
</table>

</div>

<script>
new Chart(document.getElementById('dailyChart'), {{
    type: 'line',
    data: {{ labels: {daily_labels}, datasets: [{{ label: '每日消息量', data: {daily_values}, borderColor: '#1890ff', tension: 0.3 }}] }},
    options: {{ responsive: true, plugins: {{ title: {{ display: true, text: '每日消息量趋势' }} }} }}
}});

new Chart(document.getElementById('hourlyChart'), {{
    type: 'bar',
    data: {{ labels: {hourly_labels}, datasets: [{{ label: '消息数', data: {hourly_values}, backgroundColor: '#52c41a' }}] }},
    options: {{ responsive: true, plugins: {{ title: {{ display: true, text: '24小时时段分布' }} }} }}
}});
</script>

</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="按月拉取钉钉群聊消息并生成数据分析报告")
    parser.add_argument("--conv-id", required=True, help="群聊 openConversationId")
    parser.add_argument("--year", type=int, required=True, help="目标年份")
    parser.add_argument("--month", type=int, required=True, help="目标月份")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    args = parser.parse_args()

    year, month = args.year, args.month
    batches = get_weekly_batches(year, month)
    all_messages = []

    for start, end in batches:
        print(f"\n=== Batch: {start} to {end} ===")
        msgs = fetch_range(args.conv_id, start, end)
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
    unique.sort(key=lambda m: m.get('createTime', ''))

    # 保存原始数据
    json_file = os.path.join(args.output_dir, f"messages_{year}{month:02d}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {len(unique)} messages to {json_file}")

    # 分析并生成报告
    if unique:
        stats = analyze_messages(unique, year, month)
        html_file = os.path.join(args.output_dir, f"report_{year}{month:02d}.html")
        generate_html_report(unique, stats, year, month, html_file)
        print(f"✅ Report generated: {html_file}")
    else:
        print("⚠️ No messages found, skipping report generation")


if __name__ == "__main__":
    main()
