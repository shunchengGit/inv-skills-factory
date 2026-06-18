---
name: gen-dingtalk-personal-daily
description: 在钉钉个人空间的周总结文档中添加/更新今日工作内容。当用户说"更新周总结""周报加工作""今日加上""周总结加条目""my weekly summary"时触发。基于 dws CLI 实现。
version: 1.0.0
trigger:
  - 更新周总结
  - 周总结加
  - 周报加工作
  - 今日加上
  - 周总结更新
  - 加到周总结
  - my weekly summary
---

# 个人周总结更新

## 概述

在钉钉个人空间中定位本周的「周总结」文档，将用户提供的今日工作内容写入当天对应的表格行中。**仅更新表格部分，不修改分类章节。**

**执行方式**：通过 `dws`（DingTalk Workspace CLI）命令行工具操作。

## 前置条件

1. `dws` CLI 已安装且已登录
2. 已授权 `doc:read` 和 `doc:update` 权限

**检查 dws 可用性**：

```bash
dws version --format json
dws auth status --format json
```

- 版本不满足或未安装 → 安装 `npm install -g dingtalk-workspace-cli`
- 未登录 → 执行 `dws auth login`
- doc:read 缺失 → `dws pat chmod doc:read --agentCode workbuddy --grant-type permanent --format json`
- doc:update 缺失 → `dws pat chmod doc:update --agentCode workbuddy --grant-type permanent --format json`

## 流程步骤

### Step 1: 确认 dws 可用并已登录

```bash
dws version --format json
dws auth status --format json
```

- 版本不满足或未安装 → `npm install -g dingtalk-workspace-cli`
- 未登录 → `dws auth login`
- doc:read 缺失 → `dws pat chmod doc:read --agentCode workbuddy --grant-type permanent --format json`

### Step 2: 定位本周周总结文档

文件夹层级：`周总结` → `{year}年Q{quarter}` → `{M.D-M.D}` 文档

#### 2.1 列出个人空间根目录

```bash
dws doc list --format json
```

从返回的 `nodes` 中找到 `name == "周总结"` 的文件夹，获取其 `nodeId`。

#### 2.2 确定季度文件夹

根据当前日期计算所在季度（Q1: 1-3月, Q2: 4-6月, Q3: 7-9月, Q4: 10-12月），拼接年份。

```bash
dws doc list --folder <周总结_folder_nodeId> --format json
```

从返回的 `nodes` 中匹配 `{year}年Q{quarter}` 文件夹。

**已知常量**：
- 个人空间 workspaceId: `O5pXBALbn7A2az7Z`
- 周总结文件夹 nodeId: `ydxXB52LJqexwD71FMp9m0y7JqjMp697`

#### 2.3 找到本周文档

```bash
dws doc list --folder <季度_folder_nodeId> --format json
```

`nodes` 中的文档按 `createTime` 降序排列，找到文件名包含本周日期范围的文档（如 `5.26-5.29`）。

### Step 3: 读取文档内容

```bash
dws doc read --node <nodeId> --format json
```

返回的 `markdown` 字段包含完整文档内容。

### Step 4: 解析并更新内容

**文档结构**：

1. 顶部表格：`| 日期 | 今日工作 | 明日计划 |`，每天一行
2. 分类章节：
   - `# 1 个人工作`
     - `## 1.1 技术研究`
     - `## 1.2 产品研究`
     - `## 1.3 协作推进`
   - `# 2 团队工作`
     - `## 2.1 业务迭代`
     - `## 2.2 技术专项`

**更新规则**：

1. **表格行**：在当日日期行（如 `5.26`）的「今日工作」列追加内容，多项用 `<br>` 分隔
2. **分类章节不更新**：只修改顶部表格，分类章节（1.1 技术研究、1.2 产品研究、1.3 协作推进等）保持原样不动
3. 保持原文档其余结构不变

### Step 5: 写回文档

**推荐方式**（避免中文编码问题）：将更新后的 markdown 写入临时文件，使用 `--content-file` 传入。

```bash
# 先 dry-run 预览
dws doc update --node <nodeId> --content-file /tmp/weekly_update.md --dry-run --format json

# 确认无误后执行
dws doc update --node <nodeId> --content-file /tmp/weekly_update.md --yes --format json
```

**注意事项**：
- `--node` 参数使用长横线 `--node`，不是 `--node-id`
- 更新操作会**全量覆盖**文档内容，必须保留所有原始内容
- 执行前务必 `--dry-run` 预览，确认内容正确后再 `--yes` 执行

### Step 6: 验证更新

```bash
dws doc read --node <nodeId> --format json
```

确认 `markdown` 中已包含新增内容。

## 中文编码注意事项

当 shell locale 不是 UTF-8 时（`LC_CTYPE=C`），直接在 Bash 参数传中文可能导致乱码。先检查：

```bash
locale
```

如果不是 UTF-8 locale，改用 Python 包装 `dws` 调用：

```python
import subprocess, os, json
env = {**os.environ, "LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"}
r = subprocess.run(
    ["dws", "doc", "update", "--node", nodeId, "--content-file", filepath, "--yes", "--format", "json"],
    env=env, capture_output=True
)
```

如果 locale 已是 UTF-8（如 `en_US.UTF-8`），可直接在 Bash 中使用 `--content-file` 传入包含中文的临时文件。

## dws 命令清单

| 用途 | 命令 |
|------|------|
| 列出个人空间文档 | `dws doc list --format json` |
| 列出文件夹内容 | `dws doc list --folder <folderId> --format json` |
| 读取文档内容 | `dws doc read --node <nodeId> --format json` |
| 全量更新文档 | `dws doc update --node <nodeId> --content-file <path> --yes --format json` |
| 预览更新 | `dws doc update --node <nodeId> --content-file <path> --dry-run --format json` |

## 已知常量

| 名称 | 值 | 说明 |
|------|----|------|
| 个人空间 workspaceId | `O5pXBALbn7A2az7Z` | 用户个人钉钉文档空间 |
| 周总结文件夹 nodeId | `ydxXB52LJqexwD71FMp9m0y7JqjMp697` | 个人空间根目录下的"周总结"文件夹 |
