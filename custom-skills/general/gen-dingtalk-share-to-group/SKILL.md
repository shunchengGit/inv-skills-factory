---
name: gen-dingtalk-share-to-group
description: 将链接、文章或文本消息分享到指定的钉钉群聊。支持搜索群名、发送文本/Markdown消息。基于 dws CLI 实现。
version: 1.0.0
trigger:
  - 分享到钉钉群
  - 发到钉钉群
  - 发到群
  - 分享到群
  - 钉钉群分享
  - share to dingtalk group
  - 把XX发到XX群
  - 把XX分享到XX群
---

# 钉钉群消息发送

## 概述

将链接、文章或文本消息分享到指定的钉钉群聊。核心流程：**搜索群 → 发送消息**。

**执行方式**：通过 `dws`（DingTalk Workspace CLI）命令行工具操作。

## 前置条件

1. `dws` 已安装且已登录（详见 `gen-dingtalk` 前置条件）
2. 已授权 `chat:message` 权限（发送群消息所需）

## 流程步骤

### Step 1: 搜索目标群聊

使用 `dws chat search` 按关键词搜索群名，获取 `openConversationId`。

```bash
dws chat search --keyword "群名关键词" --format json
```

返回结果中取 `result.groups[].openConversationId` 字段。

如果有多个匹配结果，根据群名和成员数选择正确的群。

### Step 2: 发送消息

使用 `dws chat message send` 发送消息到群。

```bash
dws chat message send \
  --group "<openConversationId>" \
  --title "消息标题" \
  --text '消息正文（支持Markdown）' \
  --format json
```

**关键参数说明**：
- `--group`：群的 openConversationId（必填）
- `--title`：消息标题，会以加粗方式显示
- `--text`：消息正文，支持 Markdown 格式
- `--at-all`：@所有人（可选，仅群聊支持）
- `--at-users`：@指定用户（可选，传 userId，多个用逗号分隔）

### Step 3: 确认发送成功

返回结果中 `errcode: 0` 且 `success: true` 表示发送成功。

## 常见场景

### 场景1：分享链接到群

```bash
dws chat message send \
  --group "cidmm1/rgxgUBJH7PNkZxbbNg==" \
  --title "AI学习资料分享" \
  --text '分享一篇好文章，大家学习一下 👇

https://mp.weixin.qq.com/s/vK-xC0xHKAzg8WV83p4dBg' \
  --format json
```

### 场景2：分享链接并@所有人

```bash
dws chat message send \
  --group "cidmm1/rgxgUBJH7PNkZxbbNg==" \
  --title "重要通知" \
  --text '请大家阅读以下文章 👇

https://example.com/article' \
  --at-all \
  --format json
```

### 场景3：发送纯文本通知

```bash
dws chat message send \
  --group "cidmm1/rgxgUBJH7PNkZxbbNg==" \
  --title "会议提醒" \
  --text '今天下午3点开周会，请准时参加' \
  --format json
```

## 注意事项

1. **换行符处理**：`--text` 参数必须用**单引号**包裹（`'...'`），直接在文本中换行即可。不要用双引号加 `\n`，否则换行符会被当成字面文本。
2. **群ID是 openConversationId**：不是 groupId 或 chatId，搜索结果中的 `openConversationId` 字段才是正确的。
3. **中文乱码**：`dws` 在终端中可能输出乱码中文，但 JSON 数据本身是正确的。如需在脚本中处理中文输出，参考 `gen-dingtalk-weekly-summary` 技能中的 Python UTF-8 包装方式。
4. **消息长度**：钉钉单条消息有长度限制，正文建议控制在 2000 字以内。
5. **发送频率**：避免短时间内向同一群发送大量消息，可能被限流。

## dws 命令清单

| 用途 | 命令 |
|------|------|
| 搜索群聊 | `dws chat search --keyword "关键词" --format json` |
| 发送消息 | `dws chat message send --group <id> --title "标题" --text '正文' --format json` |
| @所有人 | 在 send 命令中加 `--at-all` |
| @指定人 | 在 send 命令中加 `--at-users userId1,userId2` |
| 查看群消息 | `dws chat message list --group <id> --limit 10 --format json` |
