---
name: gen-dingtalk-personal-weekly-mail
description: 个人周报生成技能。当用户说"写周报"、"生成周报"、"个人周报"、"发周报邮件"、"周报整理"时触发。从钉钉文档读取周报模板，将表格中每日工作按类别整理到"个人工作"部分，生成优化格式的邮件草稿。基于 dws CLI 和企业微信邮箱(exmail)实现。
version: 1.0.0
trigger:
  - 写周报
  - 生成周报
  - 个人周报
  - 发周报邮件
  - 周报整理
  - weekly report
---

# 个人周报生成

## 概述

从钉钉文档读取周报模板，将顶部表格中的每日工作记录按类别整理到"1 个人工作"各子标题下，然后生成格式优化的邮件草稿存入企业微信邮箱草稿箱。

## 完整工作流

### 1. 读取钉钉文档

用 `dws doc read` 读取文档内容，用 `dws doc block list` 获取结构化 block 数据。

```bash
# 环境变量设置（所有 dws 命令都需要）
export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# 读取文档内容（输出重定向到文件避免终端乱码）
dws doc read --node <NODE_ID> --format json > /tmp/dingtalk_doc.json 2>&1

# 读取 block 结构
dws doc block list --node <NODE_ID> --format json > /tmp/dingtalk_blocks.json 2>&1
```

从 URL `https://alidocs.dingtalk.com/i/nodes/<NODE_ID>` 中提取 NODE_ID。

**编码注意**：dws CLI 输出的中文在终端会乱码，必须重定向到文件后用 Read 工具读取。

### 2. 解析文档结构

典型周报文档结构：
- 顶部表格：日期 | 今日工作 | 明日计划
- `1 个人工作`（h1）
  - `1.1 技术研究`（h2）— 通常为空需填充
  - `1.2 产品研究`（h2）— 通常为空需填充
  - `1.3 协作推进`（h2）— 通常为空需填充
- `2 团队工作`（h1）— 已有内容，保持不变

### 3. 整理表格内容到个人工作

**核心原则：按类别总结，不要逐条罗列每天做了什么。**

将表格中每日工作按性质归类：
- **技术研究**：技术方案设计/研发、项目结项、性能/架构相关
- **产品研究**：新产品尝试、AI/Agent探索、业务价值提炼
- **协作推进**：团队协作、流程梳理、管理方案

归类后用简洁的一句话描述工作成果，不加日期前缀。例如：
- ❌ "知识库技术方案设计（5.19）：完成团队知识库管理的技术方案设计"
- ✅ "完成团队知识库管理的技术方案设计，推进技术方案研发实现"

### 4. 更新钉钉文档

**重要：使用 `doc update --content-file` 全文覆写，不要用 `block insert/update`。**

`block insert` 对 unorderedList 的中文 text 传递有 bug（写入后 text 为空），`block update` 同样有问题。必须用 Markdown 全文覆写方式。

```bash
# 1. 构建完整 Markdown 内容（包含表格+个人工作+团队工作），写入临时文件
# 2. 用 doc update 更新
dws doc update --node <NODE_ID> --content-file /tmp/dingtalk_doc_update.md --format json
```

**PAT 授权**：doc update 需要 `doc:update` scope 授权，首次使用会弹出授权 URL，需用户在浏览器确认。

### 5. 生成邮件草稿

#### 5.1 邮件内容规则

- **不包含顶部表格**：邮件直接从"1 个人工作"开始
- **内容完整保留**：与文档内容一致，不做删减
- **格式简洁**：标题 + 列表，不加装饰性标签/边框
- **亮点绿色高亮**：标记数据优化成果（性能指标提升、耗时缩短等量化数据），用 `<span class="g">` 标签
  - ✅ 高亮：`降低18%-30%`、`353ms→287ms`、`1.5s→1.3s`、`由30+分钟缩短到5分钟`
  - ❌ 不高亮：`已上线`、`已发布`（状态词不是数据）

#### 5.2 HTML 样式模板

```html
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; color: #333; line-height: 1.7; font-size: 14px; }
h1 { font-size: 16px; color: #1a1a1a; margin: 20px 0 10px; }
h2 { font-size: 14px; color: #1a1a1a; margin: 14px 0 6px; }
h3 { font-size: 14px; color: #444; margin: 10px 0 4px; font-weight: 600; }
ul { padding-left: 18px; margin: 4px 0; }
li { margin-bottom: 4px; }
.g { color: #52c41a; font-weight: 600; }
</style>
```

#### 5.3 存草稿方式

**exmail 的 send_email 只能发送不能存草稿。必须用 IMAP APPEND 方式。**

收件人信息从 `.env` 文件读取（`TL_MAIL_USER` 为发件人、`WEEKLY_REPORT_TO`、`WEEKLY_REPORT_CC`）。

```python
import os
import imaplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

imap = imaplib.IMAP4_SSL("imap.exmail.qq.com", 993)
imap.login("<发件邮箱>", "<授权码>")

msg = MIMEMultipart("alternative")
msg["From"] = f"{os.environ['WEEKLY_REPORT_FROM_NAME']} <{os.environ['TL_MAIL_USER']}>"
msg["To"] = os.environ["WEEKLY_REPORT_TO"]       # 从 .env 读取
msg["Cc"] = os.environ.get("WEEKLY_REPORT_CC", "")  # 从 .env 读取
msg["Subject"] = "程舜 X.XX 周报"

msg.attach(MIMEText(text_content, "plain", "utf-8"))
msg.attach(MIMEText(html_content, "html", "utf-8"))

# 先删除旧草稿
imap.select("Drafts")
typ, data = imap.search(None, "ALL")
for mid in data[0].split():
    imap.store(mid, "+FLAGS", "\\Deleted")
imap.expunge()

# 保存新草稿
imap.append("Drafts", "\\Draft", None, msg.as_bytes())
imap.logout()
```

#### 5.4 邮件标题格式

`程舜 MM.DD 周报`（如"程舜 5.22 周报"），日期取周报最后一日。

## 收件人信息

收件人邮箱配置在项目根目录的 `.env` 文件中：

- `WEEKLY_REPORT_FROM_NAME` — 发件人展示名（如"程舜"）
- `WEEKLY_REPORT_TO` — 主收件人
- `WEEKLY_REPORT_CC` — 抄送人（逗号分隔）

**注意**：公司邮箱格式不统一，不能按规则推测，必须从记忆或邮件记录中确认。

## 常见问题

### dws 中文乱码
所有 dws 命令输出重定向到文件，用 Read 工具读取。设置 `LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8`。

### block insert/update 中文丢失
unorderedList block 的 text 字段中文内容写入后为空。改用 `doc update --content-file` 全文覆写。

### PAT 授权
doc update / block insert / block update 都需要 PAT 授权。首次使用会返回授权 URL，需引导用户在浏览器中确认。

### 邮箱格式不统一
公司邮箱不能按"姓全拼+名首字母"规则推测（如何宏辉是 hhh@tuwan.com 而非 hehhonghui），必须从记忆或邮件记录确认。
