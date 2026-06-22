# 收件人配置与常见问题

## 收件人信息

收件人邮箱配置在 `~/.skills-store/.env` 中：

- `WEEKLY_REPORT_FROM_NAME` — 发件人展示名（程舜）
- `TL_MAIL_USER` — 发件人邮箱（chengs@tuwan.com）
- `TL_MAIL_PASS` — 邮箱授权码
- `WEEKLY_REPORT_TO` — 主收件人（hhh@tuwan.com）
- `WEEKLY_REPORT_CC` — 抄送人（qupq@tuwan.com,wangfz@tuwan.com,zhaoyy@tuwan.com）

**注意**：公司邮箱格式不统一，不能按规则推测，必须从 .env 或邮件记录确认。

## 常见问题

### dws 中文乱码
所有 dws 命令输出重定向到文件，用 Read 工具读取。设置 `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8`。

### block insert/update 中文丢失
unorderedList block 的 text 字段中文内容写入后为空。改用 `doc update --content-file` 全文覆写。

### PAT 授权
doc update / block insert / block update 都需要 PAT 授权。首次使用会返回授权 URL，需引导用户在浏览器中确认。

### 邮箱格式不统一
公司邮箱不能按"姓全拼+名首字母"规则推测（如何宏辉是 hhh@tuwan.com 而非 hehhonghui），必须从 .env 或邮件记录确认。

### 邮箱授权码过期
TL_MAIL_PASS（企业邮箱授权码）可能过期，导致 IMAP/SMTP 登录失败。需用户在腾讯企业邮箱后台重新生成授权码并更新 .env 文件。