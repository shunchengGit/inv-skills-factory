---
name: mail-mgr
description: 当需要发送、查看或管理邮件时使用，支持SMTP/IMAP直连，覆盖收发、草稿、删除、标记、移动等操作
version: 0.2.0
commands:
  - /mail_send - 发送邮件
  - /mail_list - 列出邮件
  - /mail_read - 读取邮件
  - /mail_draft - 保存草稿
  - /mail_delete - 删除邮件
  - /mail_flag - 标记已读/未读/星标
  - /mail_move - 移动邮件到其他文件夹
  - /mail_folders - 查看所有文件夹
dependencies: []
---

# mail — 通用邮件管理技能

## 触发词

| 用户说 | 触发操作 |
|--------|----------|
| "发邮件"、"发送邮件"、"写邮件" | 发送 (send) |
| "查邮件"、"收件箱"、"最近邮件"、"邮件列表" | 列出 (list) |
| "看邮件"、"读邮件"、"邮件内容" | 读取正文 (read) |
| "草稿"、"存草稿"、"保存到草稿" | 存草稿 (draft) |
| "删邮件"、"删除邮件" | 删除 (delete) |
| "已读"、"标为已读"、"未读"、"星标" | 标记 (flag) |
| "移动到"、"移到"、"归档" | 移动 (move) |
| "有哪些文件夹"、"邮箱文件夹" | 文件夹列表 (folders) |

## 使用流程

1. **收集信息**：根据操作类型，向用户确认必要的参数
2. **执行前确认**：发送/删除操作前必须向用户确认
3. **调用脚本**：执行 `uv run {baseDir}/scripts/mail.py <子命令>`

## 配置

### 凭据

环境变量 `TL_MAIL_USER` 和 `TL_MAIL_PASS`，写入 `~/.zshrc`：

```bash
export TL_MAIL_USER="your@email.com"
export TL_MAIL_PASS="授权码"
```

脚本首次运行时会交互式提示输入并自动写入。

### 服务器默认值

| 协议 | 地址 | 端口 |
|------|------|------|
| SMTP | smtp.exmail.qq.com | 465 (SSL) |
| IMAP | imap.exmail.qq.com | 993 (SSL) |

可通过 `--smtp-host`/`--smtp-port`/`--imap-host`/`--imap-port` 覆盖。

## 子命令

### send — 发送邮件

```bash
uv run {baseDir}/scripts/mail.py send \
  --to "user@example.com" \
  --subject "会议通知" \
  --body "明天下午 3 点开会"

# HTML 邮件
uv run {baseDir}/scripts/mail.py send \
  --to "user@example.com" \
  --subject "周报" \
  --body-html "<h1>本周总结</h1><p>...</p>"

# 抄送/密送/附件
uv run {baseDir}/scripts/mail.py send \
  --to "a@x.com,b@x.com" \
  --cc "c@x.com" \
  --bcc "d@x.com" \
  --subject "合同" \
  --body "请查收" \
  --attachments ./contract.pdf ./quote.xlsx

# 自定义 SMTP
uv run {baseDir}/scripts/mail.py send \
  --smtp-host smtp.qq.com --smtp-port 587 --use-tls \
  --to "friend@example.com" \
  --subject "你好" \
  --body "测试"
```

### list — 列出邮件

```bash
# 收件箱最近 10 封
uv run {baseDir}/scripts/mail.py list

# 最近 3 天，最多 20 封
uv run {baseDir}/scripts/mail.py list --days 3 --limit 20

# 指定文件夹
uv run {baseDir}/scripts/mail.py list --folder "Sent Messages"

# 按发件人过滤
uv run {baseDir}/scripts/mail.py list --from "boss@example.com"

# 输出纯文本（适合展示）
uv run {baseDir}/scripts/mail.py list --format text
```

输出 JSON：
```json
{
  "success": true,
  "folder": "INBOX",
  "count": 3,
  "messages": [
    {
      "id": "1",
      "subject": "会议通知",
      "from": "boss@example.com",
      "to": "me@example.com",
      "date": "Mon, 26 May 2026 14:30:00 +0800",
      "seen": true,
      "flagged": false
    }
  ]
}
```

### read — 读取邮件正文

```bash
uv run {baseDir}/scripts/mail.py read --id "123"
uv run {baseDir}/scripts/mail.py read --id "123" --folder "Drafts"
```

输出 JSON 包含 subject/from/to/date/text_body/html_body/attachments。

### draft — 保存草稿

```bash
uv run {baseDir}/scripts/mail.py draft \
  --to "user@example.com" \
  --subject "草稿标题" \
  --body "草稿内容"

# 替换已有草稿
uv run {baseDir}/scripts/mail.py draft \
  --to "user@example.com" \
  --subject "修改后的草稿" \
  --body "新内容" \
  --replace

# HTML 草稿
uv run {baseDir}/scripts/mail.py draft \
  --to "user@example.com" \
  --subject "HTML 草稿" \
  --body-html "<h1>标题</h1><p>内容</p>"
```

### delete — 删除邮件

```bash
uv run {baseDir}/scripts/mail.py delete --id "123"
uv run {baseDir}/scripts/mail.py delete --id "123" --folder "Junk"
```

### flag — 标记邮件

```bash
uv run {baseDir}/scripts/mail.py flag --id "123" --seen       # 标为已读
uv run {baseDir}/scripts/mail.py flag --id "123" --unseen     # 标为未读
uv run {baseDir}/scripts/mail.py flag --id "123" --flagged    # 加星标
uv run {baseDir}/scripts/mail.py flag --id "123" --unflagged  # 取消星标
```

### move — 移动邮件

```bash
uv run {baseDir}/scripts/mail.py move --id "123" --to "Sent Messages"
uv run {baseDir}/scripts/mail.py move --id "123" --to "Junk"
```

### folders — 列出文件夹

```bash
uv run {baseDir}/scripts/mail.py folders
```

输出 JSON：
```json
{
  "success": true,
  "folders": [
    {"name": "INBOX", "flags": ["\\HasNoChildren"]},
    {"name": "Drafts", "flags": ["\\HasNoChildren", "\\Drafts"]},
    {"name": "Sent Messages", "flags": ["\\HasNoChildren", "\\Sent"]}
  ]
}
```

## HTML 邮件样式参考

```css
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.65; color: #333; }
h1 { color: #1677ff; }
.good { color: #52c41a; }
.bad { color: #ff4d4f; }
table { border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #e8e8e8; padding: 8px 12px; }
```

## 文件夹参考

详见 `references/imap-folders.md`。

## 安全提醒

- 不要在对话中暴露授权码
- 发送/删除前必须向用户确认
- 凭据存储在 `~/.zshrc` 的环境变量中，不会提交到仓库
