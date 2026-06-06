# 个人周总结更新工作流

在钉钉个人空间中定位本周的「周总结」文档，将用户提供的今日工作内容写入当天对应的表格行和分类章节中。

## 前置条件

1. `dws` 已安装且已登录（详见主 Skill 前置条件）
2. 已授权 `doc:read` 和 `doc:update` 权限

## 流程步骤

### Step 1: 定位本周周总结文档

文件夹层级：`周总结` → `{year}年Q{quarter}` → `{M.D-M.D}` 文档

#### 1.1 列出个人空间根目录

```bash
dws doc list --format json
```

从返回的 `nodes` 中找到 `name == "周总结"` 的文件夹，获取其 `nodeId`。

#### 1.2 确定季度文件夹

根据当前日期计算所在季度（Q1: 1-3月, Q2: 4-6月, Q3: 7-9月, Q4: 10-12月），拼接年份。

```bash
dws doc list --folder <周总结_folder_nodeId> --format json
```

从返回的 `nodes` 中匹配 `{year}年Q{quarter}` 文件夹。

**已知常量**：
- 个人空间 workspaceId: `O5pXBALbn7A2az7Z`
- 周总结文件夹 nodeId: `ydxXB52LJqexwD71FMp9m0y7JqjMp697`

#### 1.3 找到本周文档

```bash
dws doc list --folder <季度_folder_nodeId> --format json
```

`nodes` 中的文档按 `createTime` 降序排列，找到文件名包含本周日期范围的文档（如 `5.26-5.29`）。

### Step 2: 读取文档内容

```bash
dws doc read --node <nodeId> --format json
```

返回的 `markdown` 字段包含完整文档内容。

### Step 3: 解析并更新内容

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
2. **分类章节**：根据内容性质判断归属：
   - 技术研究类 → `1.1 技术研究`
   - 产品研究/竞品分析/策略研究类 → `1.2 产品研究`
   - 团队协作/管理类 → `1.3 协作推进`
   - 业务迭代 → `2.1 业务迭代`
   - 技术专项 → `2.2 技术专项`
3. 保持原文档结构不变，仅追加新内容

### Step 4: 写回文档

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

### Step 5: 验证更新

```bash
dws doc read --node <nodeId> --format json
```

确认 `markdown` 中已包含新增内容。

## 已知常量

| 名称 | 值 | 说明 |
|------|----|------|
| 个人空间 workspaceId | `O5pXBALbn7A2az7Z` | 用户个人钉钉文档空间 |
| 周总结文件夹 nodeId | `ydxXB52LJqexwD71FMp9m0y7JqjMp697` | 个人空间根目录下的"周总结"文件夹 |
