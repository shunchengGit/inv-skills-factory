---
name: dd-todo-tracker
description: 当需要查看、添加、完成或管理待办任务时使用，底层存储委托给 dd-skills-memory 统一服务，**强制使用微云后端**
version: 0.1.0
commands:
  - /td_init - 初始化/拉取 TODO 和当月 DONE 文档，输出全量任务 JSON
  - /td_add <任务内容> [--priority high/medium/low] - 添加任务到 TODO 文档
  - /td_done <关键词> [--id xxx] - 从 TODO 移除任务（按关键词或 ID 匹配），追加到 DONE 文档
  - /td_list - 列出 TODO 文档中所有未完成任务
---

# dd-todo-tracker：TODO 管理

**基于微云知识库的 TODO 管理。** 底层存储委托给 `dd-skills-memory` 统一服务，**强制使用微云后端**。

## 命令语义

| 命令 | 语义 | 存储操作 |
|------|------|---------|
| `/td_init` | 初始化/读取 TODO 和当月 DONE 文档，输出全量任务 JSON | `sm.get_or_create_doc("dd-todo-tracker", "TODO")` + `sm.get_or_create_doc("dd-todo-tracker", "DONE-YYYY-MM")` |
| `/td_add <任务内容> [--priority high/medium/low]` | 添加任务到 TODO 文档 | `sm.read_doc` → 解析 → 追加 → `sm.update_doc` |
| `/td_done <关键词> [--id xxx]` | 从 TODO 中移除任务，追加到 DONE 文档 | `sm.read_doc(TODO)` → 查找移除 → `sm.update_doc(TODO)` + `sm.read_doc(DONE)` → 追加 → `sm.update_doc(DONE)` |
| `/td_list` | 列出 TODO 文档中所有未完成任务 | `sm.read_doc(TODO)` → 按标签过滤 |

## 记录格式

每个任务行包含 ID 和优先级标签：

```markdown
- [#abc1234] 完成需求评审 [高优]
- [#def5678] 编写技术方案 [重要不紧急]
- [#ghi9012] 整理文档 [暂缓]
```

| `--priority` | 标签 | 说明 |
|-------------|------|------|
| `high` | `[高优]` | 紧急且重要 |
| `medium` | `[重要不紧急]` | 重要但不紧急 |
| `low` | `[暂缓]` | 可延后处理 |

- ID 格式：`[#xxx]`，放在任务内容前面
- ID 生成算法：任务内容的 sha1 哈希取前 7 位
- 优先级用标签表示，格式 `[标签名]`，放在任务内容后面- `done` 支持关键词匹配（模糊）和 `--id`（精确），多个关键词匹配时返回候选列表

## 文档命名约定

| 文档 | 命名格式 | 用途 | 内容格式 |
|------|---------|------|---------|
| TODO | `TODO` | 待办任务（高优/重要不紧急/暂缓） | 按标签区分优先级 |
| DONE-YYYY-MM | `DONE-2026-06` | 按月存放已完成任务 | 平铺列表，无 section |

### DONE 文档格式

已完成任务平铺存放，无 section 区分：

```markdown
# 2026年6月 已完成
- [#abc1234] 完成需求评审
- [#def5678] 编写技术方案
```

## 配置

**本技能强制使用微云知识库存储，不可配置为其他后端。**

所有存储操作通过 `dd-skills-memory` 统一服务完成，后端固定为 `weiyun`：

| 环境变量 | 说明 | 固定值 |
|---------|------|--------|
| `SM_BACKEND` | 存储后端 | `weiyun`（不可更改） |

> ⚠️ **强制要求**：必须使用微云知识库作为存储后端，以确保 TODO 列表在多设备间同步。
> 调用 `dd-skills-memory` 时不应覆盖后端配置。

## 依赖

- `dd-skills-memory`（统一存储服务，微云后端）

## 典型工作流

```
1. /td_init                ← 读取 TODO 和 DONE 文档，感知全量任务池
2. /td_add "完成需求评审" --priority high   ← 添加高优任务
3. /td_list                ← 查看当前未完成任务
4. /td_done "需求评审"      ← 完成任务，移到 DONE
```

## 特性

| 特性 | 说明 |
|------|------|
| 存储 | 委托给 dd-skills-memory，**强制微云后端**，多设备同步 |
| 优先级 | 高优 / 重要不紧急 / 暂缓 三级分类 |
| ID 追踪 | 基于 sha1 哈希的 7 位 ID，支持精确匹配 |
| 归档 | 已完成任务按月自动分文档存储 |
| 搜索 | `done` 支持关键词模糊匹配和 `--id` 精确匹配 |
