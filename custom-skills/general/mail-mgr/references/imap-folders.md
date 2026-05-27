# 邮箱文件夹参考

## 腾讯企业邮箱 (exmail.qq.com)

| 文件夹名 | 用途 | 备注 |
|---------|------|------|
| INBOX | 收件箱 | 默认文件夹 |
| Sent Messages | 已发送 | 注意有空格，IMAP 命令需加引号 |
| Drafts | 草稿箱 | |
| Junk | 垃圾邮件 | |
| Deleted Messages | 已删除 | 注意有空格 |

> 文件夹名称区分大小写。IMAP 操作含空格的文件夹时需用引号包裹，如 `"Sent Messages"`。

## IMAP 协议说明

### 列出文件夹
```
LIST "" "*"
```
返回格式：`(\HasNoChildren) "/" "INBOX"`，括号内为文件夹属性。

### 常用属性
| 属性 | 含义 |
|------|------|
| \HasNoChildren | 无子文件夹 |
| \HasChildren | 有子文件夹 |
| \Drafts | 草稿箱标记 |
| \Sent | 已发送标记 |
| \Junk | 垃圾邮件标记 |
| \Trash | 已删除标记 |

### 搜索语法 (IMAP SEARCH)
| 条件 | 示例 |
|------|------|
| 按日期 | `SINCE 20-May-2026` |
| 按发件人 | `FROM "user@example.com"` |
| 按主题 | `SUBJECT "会议"` |
| 未读 | `UNSEEN` |
| 已读 | `SEEN` |
| 星标 | `FLAGGED` |
| 组合 | `(SINCE 20-May-2026 FROM "user@example.com")` |
