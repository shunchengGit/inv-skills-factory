# 已知常量、dws 命令清单与数据源结构

## dws 命令清单

| 用途 | 命令 |
|------|------|
| 搜索知识库 | `dws wiki space search --keyword "客户端" --format json` |
| 获取知识库详情 | `dws wiki space get --id <workspaceId> --format json` |
| 列出文档节点 | `dws doc list --workspace <workspaceId> [--folder <folderId>] --format json` |
| 读取文档内容 | `dws doc read --node <nodeId> --format json` |
| 搜索文档 | `dws doc search --query "周报" --workspace-ids <workspaceId> --format json` |
| 获取文档信息 | `dws doc info --node <nodeId> --format json` |

## 已知常量

| 名称 | 值 | 说明 |
|------|----|------|
| 客户端知识库 workspaceId | `O5pXB2wb5j2VaX7Z` | 可通过 `wiki space search --keyword "客户端"` 验证 |
| 04_团队管理文件夹 nodeId | `EpGBa2Lm8ajke6zXUEKN1QdwWgN7R35y` | 周会周报的父文件夹 |
| 周会周报文件夹 nodeId | `dpYLaezmVNgnG1LoUGeDE06kJrMqPxX6` | 在 04_团队管理 下 |

## 数据源结构参考

主周报 markdown 结构：
- `# **1 上周TODO**` — TODO 跟进
- `# **2 本周核心议题**` — 议题
- `# **3 业务相关**` — **核心数据源**：业务迭代表格（点点开黑/点点狼人/兔小铲）
- `# **4 技术相关**` — **核心数据源**：技术专项表格（性能优化/架构升级/研发运维）
- `# **5 个人工作情况**` — 个人维度
- `# **6 本周TODO**` — 下周 TODO

技术指标周报结构：
- `# **1 总结说明**` — 崩溃率/网络错误数/卡顿率/图片成功率变化总结
- `# **2 指标详情**` — 各指标详细数据表格
