---
name: gen-dingtalk-personal-weekly-mail
description: 从钉钉文档读取周报模板，按类别整理内容并生成邮件草稿存入企业微信邮箱
version: 2.0.0
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

用 `dws doc block list` 获取结构化 block 数据（`doc read` 通常不需要，block list 已包含全部内容）。

```bash
# 环境变量设置（所有 dws 命令都需要）
export LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8

# 读取 block 结构（输出重定向到文件避免终端乱码）
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
- **产品研究**：新产品尝试、AI/Agent探索、业务价值提炼、用户召回/增长策略、push优化等运营类产品工作
- **协作推进**：团队协作、流程梳理、管理方案

归类规则：
- 用简洁的一句话描述工作成果，不加日期前缀
- 同一件事多天在做时合并为一条（如"启动对小程序的研究"+"研究各种竞对小程序产品思路" → "研究竞对小程序产品思路，启动小程序研究"）
- 用户召回、push优化等运营类工作归入产品研究，不归入协作推进

示例：
- ❌ "知识库技术方案设计（5.19）：完成团队知识库管理的技术方案设计"
- ✅ "完成团队知识库管理的技术方案设计，推进技术方案研发实现"
- ❌ "启动对小程序的研究"、"研究各种竞对小程序产品思路"（两条分开）
- ✅ "研究竞对小程序产品思路，启动小程序研究"（合并为一条）

### 4. 更新钉钉文档

**重要：使用 `doc update --content-file` 全文覆写，不要用 `block insert/update`。**

`block insert` 对 unorderedList 的中文 text 传递有 bug（写入后 text 为空），`block update` 同样有问题。必须用 Markdown 全文覆写方式。

```bash
# 1. 构建完整 Markdown 内容（包含表格+个人工作+团队工作），写入临时文件
# 2. 用 doc update 更新（必须用 --mode overwrite 全文覆写；添加 -y 跳过确认提示）
dws doc update --node <NODE_ID> --content-file /tmp/dingtalk_doc_update.md --mode overwrite --format json -y
```

**PAT 授权**：doc update 需要 `doc:update` scope 授权，首次使用会弹出授权 URL，需用户在浏览器确认。

### 5. 生成邮件草稿

#### 5.1 邮件内容规则

- **不包含顶部表格**：邮件直接从个人工作开始
- **内容与文档完全一致**：不精简、不重写、不合并，保持原文
- **只优化展示形式**：用 emoji + 粗体标题替代编号层级，业务迭代用项目名+状态标签，技术专项用紧凑行式
- **个人工作与团队工作明确分区**：用一级粗标题 + 粗分隔线区分，不能混在一起
- **亮点绿色高亮**：标记数据优化成果（性能指标提升、耗时缩短等量化数据），用 `<span class="g">` 标签
  - ✅ 高亮：`降低18%-30%`、`353ms→287ms`、`1.5s→1.3s`、`由30+分钟缩短到5分钟`、`下降13M`
  - ❌ 不高亮：`已上线`、`已发布`（状态词不是数据）

#### 5.2 邮件展示区分级规则

邮件内容严格按文档原文，展示形式按以下规则处理：

**一级分区（个人工作/团队工作）**：
- 用 `.main-title` 粗标题 + 2px 粗底部分隔线，字号16px
- emoji 前缀：👤个人工作、👥团队工作
- 个人工作和团队工作之间必须有明确的视觉分隔，不能混在一起

**二级子标题（技术研究/产品研究等）**：
- 用 `.section-title` 细标题 + 1px 浅色底部分隔线，字号14px
- emoji 前缀：🔍技术、💡产品、🤝协作、📦业务、⚡专项

**业务迭代项目的展示规则**：
- 用 `.proj-line` + `.proj-name` + `.tag` 组合，一行一个项目
- **tag 只用于版本/发版信息**（如 `3.4.x · 6.25提审`、`1.5.6已发版✓`），不用于普通需求
- 普通需求（如改名卡）直接作为"已完成/进行中/未开始"状态的描述内容，不用 tag 标签
- 状态之间用 `.sep` 分隔符连接

**技术专项**：
- 主项目作为独立标题行（加粗）
- 子项目缩进排列，格式：`子项目名：描述内容`
- 量化数据用 `.g` 绿色高亮

#### 5.3 HTML 样式模板

```html
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; color: #333; line-height: 1.8; font-size: 14px; max-width: 680px; }
.main-title { font-size: 16px; font-weight: 700; color: #1a1a1a; margin: 24px 0 10px; padding-bottom: 6px; border-bottom: 2px solid #1a1a1a; }
.main-title span { margin-right: 6px; }
.section { margin: 14px 0 8px; }
.section-title { font-size: 14px; font-weight: 600; color: #1a1a1a; margin: 0 0 6px; padding-bottom: 4px; border-bottom: 1px solid #eee; }
.section-title span { margin-right: 6px; }
ul { padding-left: 18px; margin: 2px 0; }
li { margin-bottom: 3px; font-size: 14px; }
.tag { display: inline-block; font-size: 12px; padding: 1px 6px; border-radius: 3px; margin-right: 4px; font-weight: 500; }
.tag-doing { background: #e6f7ff; color: #1890ff; }
.tag-done { background: #f6ffed; color: #52c41a; }
.tag-todo { background: #fff7e6; color: #fa8c16; }
.g { color: #52c41a; font-weight: 600; }
.proj-line { margin: 6px 0; font-size: 14px; }
.proj-name { font-weight: 600; color: #1a1a1a; margin-right: 4px; }
.sep { color: #d9d9d9; margin: 0 6px; }
</style>
```

#### 5.4 邮件 HTML 结构模板

```html
<!-- 一级分区 -->
<div class="main-title"><span>👤</span>个人工作</div>

<div class="section">
  <div class="section-title"><span>🔍</span>技术研究</div>
  <ul>
    <li>工作项1</li>
    <li>工作项2</li>
  </ul>
</div>

<div class="section">
  <div class="section-title"><span>💡</span>产品研究</div>
  <ul>
    <li>工作项1</li>
  </ul>
</div>

<div class="section">
  <div class="section-title"><span>🤝</span>协作推进</div>
  <ul>
    <li>工作项1</li>
  </ul>
</div>

<!-- 一级分区 -->
<div class="main-title"><span>👥</span>团队工作</div>

<div class="section">
  <div class="section-title"><span>📦</span>业务迭代</div>
  <!-- 有版本号信息的项目：tag 用于版本/发版 -->
  <div class="proj-line"><span class="proj-name">项目A</span><span class="tag tag-todo">3.4.x · 6.25提审</span>进行中：xxx<span class="sep">|</span>未开始：xxx</div>
  <div class="proj-line"><span class="proj-name">项目B</span><span class="tag tag-done">1.5.6已发版✓</span></div>
  <!-- 无版本号信息的项目：普通需求不用 tag，直接写状态 -->
  <div class="proj-line"><span class="proj-name">项目C</span>已完成：改名卡<span class="sep">|</span>进行中：体验优化<span class="sep">|</span>未开始：S3氛围、助战优化</div>
</div>

<div class="section">
  <div class="section-title"><span>⚡</span>技术专项</div>
  <div><b>主项目名</b></div>
  <div style="padding-left:14px; margin:2px 0; font-size:14px;"><b>子项目名：</b>描述 <span class="g">量化数据</span></div>
  <div style="padding-left:14px; margin:2px 0; font-size:14px;"><b>子项目名：</b>描述</div>
</div>
```

**tag 使用规则**：
- ✅ tag 用于：版本号（`3.4.x`）、发版信息（`1.5.6已发版✓`）、提审日期等版本级别信息
- ❌ tag 不用于：普通需求（改名卡、体验优化等），这些直接作为状态描述的文字内容

#### 5.5 存草稿方式

**exmail 的 send_email 只能发送不能存草稿。必须用 IMAP APPEND 方式。**

收件人信息从 `.env` 文件读取（`TL_MAIL_USER` 为发件人、`WEEKLY_REPORT_TO`、`WEEKLY_REPORT_CC`）。

.env 文件位置：`/Users/chengshun/.skills-store/.env`

```python
import imaplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

# 配置从 .env 读取
from_email = os.environ["TL_MAIL_USER"]          # chengs@tuwan.com
mail_pass = os.environ["TL_MAIL_PASS"]
from_name = os.environ["WEEKLY_REPORT_FROM_NAME"] # 程舜
to_email = os.environ["WEEKLY_REPORT_TO"]         # hhh@tuwan.com
cc_email = os.environ.get("WEEKLY_REPORT_CC", "") # qupq@tuwan.com,wangfz@tuwan.com,zhaoyy@tuwan.com

imap = imaplib.IMAP4_SSL("imap.exmail.qq.com", 993)
imap.login(from_email, mail_pass)

msg = MIMEMultipart("alternative")
msg["From"] = formataddr((from_name, from_email))
msg["To"] = to_email
msg["Cc"] = cc_email
msg["Subject"] = "程舜 MM.DD 周报"

msg.attach(MIMEText(text_content, "plain", "utf-8"))
msg.attach(MIMEText(html_content, "html", "utf-8"))

# 先删除旧草稿
imap.select("Drafts")
typ, data = imap.search(None, "ALL")
if data[0]:
    for mid in data[0].split():
        imap.store(mid, "+FLAGS", "\\Deleted")
    imap.expunge()

# 保存新草稿
imap.append("Drafts", "\\Draft", None, msg.as_bytes())
imap.logout()
```

#### 5.6 邮件标题格式

`程舜 MM.DD 周报`（如"程舜 6.5 周报"），日期取周报最后一日。

## 收件人配置与常见问题

见 `references/configuration.md`。
