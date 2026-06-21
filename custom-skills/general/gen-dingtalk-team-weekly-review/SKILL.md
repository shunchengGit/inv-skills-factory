---
name: gen-dingtalk-team-weekly-review
description: 从钉钉客户端知识库的"周会周报"文件夹中查找最新周报，按指定格式总结业务迭代和技术专项（仅重大进展）。基于 dws CLI 实现。
version: 2.1.0
trigger:
  - 总结客户端周报
  - 客户端周报总结
  - 周报总结
  - dingtalk weekly summary
  - 本周周报
  - 最新周报
---

# 钉钉客户端知识库周报总结

## 概述

从钉钉"客户端"知识库 → "周会周报"文件夹中找到最新周报，按固定格式总结**业务迭代**和**技术专项**（仅保留有重大进展的项目）。

**执行方式**：通过 `dws`（DingTalk Workspace CLI）命令行工具操作，不依赖 MCP。

## 前置条件

1. `dws` CLI 已安装且已登录
2. 已授权 `doc:read` 权限（如未授权，执行 `dws pat chmod doc:read --agentCode workbuddy --grant-type permanent --format json`）

**检查 dws 可用性**：

```bash
dws version --format json
dws auth status --format json
```

- 版本不满足或未安装 → 安装 `npm install -g dingtalk-workspace-cli`
- 未登录 → 执行 `dws auth login`
- 未授权 → 执行 `dws pat chmod doc:read --agentCode workbuddy --grant-type permanent --format json`

## 中文编码注意事项

`dws` 在终端中可能输出乱码中文。所有 `dws` 命令必须通过 Python 调用并设置 UTF-8 环境变量：

```python
import subprocess, os, json

env = {**os.environ, "LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"}
r = subprocess.run(
    ["dws", "doc", "read", "--node", "<nodeId>", "--format", "json"],
    env=env, capture_output=True
)
data = json.loads(r.stdout)
markdown_content = data.get("markdown", "")
```

**禁止**直接在 Bash 中执行 `dws` 命令并期望中文正确显示。必须使用 Python 包装。

## 流程步骤

### Step 1: 确认 dws 可用并已登录

```bash
dws version --format json
dws auth status --format json
```

- 版本不满足或未安装 → 安装/升级
- 未登录 → 执行 `dws auth login`
- 未授权 doc:read → 执行 `dws pat chmod doc:read --agentCode workbuddy --grant-type permanent --format json`

### Step 2: 定位知识库

使用 `dws wiki space search` 按关键词"客户端"搜索，获取 `workspaceId`。

```python
r = subprocess.run(
    ["dws", "wiki", "space", "search", "--keyword", "客户端", "--format", "json"],
    env=env, capture_output=True
)
```

```
已知常量：客户端知识库 workspaceId = "O5pXB2wb5j2VaX7Z"
```

如果 workspaceId 已知，可跳过搜索直接进入 Step 3。

### Step 3: 定位"周会周报"文件夹

使用 `dws doc list` 列出知识库根目录或子文件夹，找到名为"周会周报"的文件夹，获取其 `nodeId`。

"周会周报"文件夹位于 `04_团队管理` (nodeId: `EpGBa2Lm8ajke6zXUEKN1QdwWgN7R35y`) 下的子文件夹。

```python
# 方式1：已知常量直接使用
folder_id = "dpYLaezmVNgnG1LoUGeDE06kJrMqPxX6"

# 方式2：遍历查找
# 先列出 04_团队管理 文件夹的内容
r = subprocess.run(
    ["dws", "doc", "list", "--workspace", workspace_id, "--folder", "EpGBa2Lm8ajke6zXUEKN1QdwWgN7R35y", "--format", "json"],
    env=env, capture_output=True
)
# 从返回的 nodes 中找到 name 包含 "周会周报" 的文件夹
```

```
已知常量：周会周报文件夹 nodeId = "dpYLaezmVNgnG1LoUGeDE06kJrMqPxX6"
```

### Step 4: 获取最新周报

使用 `dws doc list` 遍历"周会周报"文件夹，按 `createTime` 降序排列，找到最新的周报文档。

```python
r = subprocess.run(
    ["dws", "doc", "list", "--workspace", workspace_id, "--folder", folder_id, "--format", "json"],
    env=env, capture_output=True
)
data = json.loads(r.stdout)
nodes = data.get("nodes", [])
# 按 createTime 降序排序，取第一个文件类型节点
nodes.sort(key=lambda x: x.get("createTime", 0), reverse=True)
latest = next((n for n in nodes if n["nodeType"] == "file"), None)
```

**重要**：刚创建的周报可能只是空模板！需读取内容后检查业务相关和技术相关部分是否有实质填写。如果为空模板，回退到上一期周报。

空模板判断标准：
- Section 3（业务相关）的表格中产品线行只有表头，无实际内容
- Section 4（技术相关）的表格中所有项目状态为空或"/"
- markdown 总长度明显短于历史周报（如 < 4000 字符）

### Step 5: 读取周报内容

```python
r = subprocess.run(
    ["dws", "doc", "read", "--node", latest_node_id, "--format", "json"],
    env=env, capture_output=True
)
data = json.loads(r.stdout)
md = data.get("markdown", "")
```

1. 读取主周报（综合周报）
2. 主周报 markdown 中会引用/链接子周报（技术指标周报、产品体验周报），提取其中的 `dentryUuid` 或 nodeId，额外读取这些子文档

提取子文档 nodeId 的方法：在 markdown 中查找 `alidocs.dingtalk.com/api/doc/transit?dentryUuid=XXXXX` 格式的链接，提取 `dentryUuid` 作为子文档的 nodeId。

### Step 6: 按格式总结

**输出为纯文本，不要生成 HTML、表格、Markdown 表格或其他富格式。直接在对话中输出。**

输出格式（严格遵循以下样式）：

```
**1 业务迭代**
**点点开黑：** 3.3.9版本预计5月25日提审。已完成：消费限额合规提醒、关注功能优化、广场/照片墙视频内容标注、产品体验优化、电竞培训机构合作支持、FM厅支持小游戏、帖子评论支持删除、播放音视频降低厅内音量。进行中：首页厅列表背景展示框、羊村之巅新厅模板、RTC双通道支持、王者buff赛。未开始：车队内优化。
**点点狼人：** 已完成：私聊搜索页、Unity退出误报过滤、队长申请流程优化。进行中：我的页无网兜底处理。iOS 3.3.4版本已于5月15日提审，3.3.5版本计划26号提审。Android 3.4.0版本已于5月15日提审。
**兔小铲：** 已完成：分享逻辑适配、帖子删除评论、金铲铲小厅铲铲会、厅战力榜（双端）；照片墙5.0、人脸识别进厅逻辑、群组（iOS）。1.5.5版本已于5月20日发布。

**2 技术专项**
**性能优化**
iOS核心页面加载时长： 点点狼人核心页面加载降低18%-30%，大厅353ms→287ms，个人主页184ms→106ms，已上线。
iOS启动耗时： 点点狼人同步开黑启动策略，测试数据1.5s→1.3s。
Android R8混淆整体性能优化： 开黑App启动1.13s→993ms，已完成队长测试，下周正式灰度上线。
**架构升级**
iOS Socket优化： socket解析耗时占比1%→0，已在队长包验证，整体改造完成进入稳定性验证阶段。
**研发运维**
核心指标研发运维优化（高优）： 统计时间由30+分钟缩短到5分钟左右，APM自定义看板已配置，崩溃和网络告警均已配置。
```

格式规则：
1. **业务迭代**：每个产品线一段，产品名加粗后冒号起头，统一模板：**版本计划 → 已完成 → 进行中 → 未开始**，无内容的环节省略，用句号或分号分隔
2. **业务迭代不提左移进展**：周报"3 业务相关"表格中的"左移进展"列内容不纳入总结，仅取"项目进展"列
3. **技术专项**：按技术项目大类（性能优化/架构升级/研发运维）分组，每个子项单独一行，子项目名后冒号+空格，紧跟量化数据和里程碑，不加项目符号
4. **技术专项严格过滤**：仅保留有明确关键结果（量化数据）的项目，仅有进展描述但无关键结果的项目不提，跳过"暂无进展"、"/"、"自测中无数据"等项目；如果某个大类下所有子项都被过滤，则该大类标题也不出现
5. **标题加粗**：一级标题（"1 业务迭代"、"2 技术专项"）、二级分类标题（"性能优化"、"架构升级"、"研发运维"）和产品线名称均使用加粗
6. **纯文本输出**：不要 HTML、不要 Markdown 表格、不要代码块包裹、不要生成文件

## 注意事项

1. **文件夹范围**：只看"周会周报"文件夹下的周报，不要搜索整个知识库
2. **内容范围**：只要业务迭代 + 技术专项，不要质量指标、产品体验、个人工作情况、TODO 等章节
3. **业务迭代不提左移进展**：周报"3 业务相关"表格中的"左移进展"列内容不纳入总结
4. **技术专项严格过滤**：仅有进展描述但无关键结果（量化数据）的项目不提；某大类下所有子项被过滤则该大类标题也不出现
5. **周报时效**：优先最新期，但需检查是否为空模板
6. **子文档关联**：主周报内嵌了技术指标周报和产品体验周报的链接，但这些子文档主要用于补充技术指标数据，核心业务迭代信息在主周报的"3 业务相关"表格中
7. **中文编码**：所有 `dws` 命令必须通过 Python 调用，设置 UTF-8 环境变量，不要直接在 Bash 中执行

## 已知常量、命令清单与数据源结构

见 `references/constants.md`。
