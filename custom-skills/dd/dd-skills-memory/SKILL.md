---
name: dd-skills-memory
description: 技能统一存储服务：纯通用存储，与技能无关，提供原子 CRUD 操作
version: 0.1.0
commands:
  - /sm_find - 查找文档
  - /sm_create - 创建文档
  - /sm_read - 读取文档内容
  - /sm_write - 写入文档内容
  - /sm_delete - 删除文档
  - /sm_list - 列出技能的所有文档
---

# dd-skills-memory：技能统一存储服务

纯通用存储服务，**与技能无关**。只提供原子 CRUD 操作，不感知任何业务语义。

## 设计原则

- **与技能无关**：不感知任何技能的记录格式、命名约定、业务逻辑
- **原子操作**：只提供 `find/create/read/update/delete/list` 六个原子操作
- **后端可配置**：支持多种存储后端，由环境变量指定
- **技能隔离**：每个技能有独立的命名空间

## 命令

| 命令 | 用途 | 示例 |
|------|------|------|
| `sm_find <skill_name> <doc_name>` | 查找文档 | `sm_find dd-todo-tracker TODO` |
| `sm_create <skill_name> <doc_name> <content>` | 创建文档 | `sm_create dd-todo-tracker TODO "# 高优\n"` |
| `sm_read <skill_name> <doc_id>` | 读取文档内容 | `sm_read dd-todo-tracker TODO` |
| `sm_write <skill_name> <doc_id> <content>` | 写入文档内容 | `sm_write dd-todo-tracker TODO "# 新内容\n"` |
| `sm_delete <skill_name> <doc_id>` | 删除文档 | `sm_delete dd-todo-tracker TODO` |
| `sm_list <skill_name>` | 列出技能的所有文档 | `sm_list dd-todo-tracker` |

## Python API

```python
from skills_memory import SkillsMemory

# 基础用法
sm = SkillsMemory(backend="dingtalk")  # 或 "dingtalk-drive"、"local"

# 自定义文件夹名称（可选，默认 "[勿动]SkillsMemory"）
sm = SkillsMemory(backend="dingtalk", folder_name="[勿动]MyFolder")

# 查找文档
result = sm.find_doc("dd-todo-tracker", "TODO")
# {"success": True, "nodeId": "xxx"} 或 {"success": True, "nodeId": None}

# 创建文档
result = sm.create_doc("dd-todo-tracker", "TODO", "# 高优\n")
# {"success": True, "nodeId": "xxx"}

# 获取或创建文档（便捷方法）
result = sm.get_or_create_doc("dd-todo-tracker", "TODO", "# 初始内容\n")
# {"success": True, "nodeId": "xxx"}

# 读取文档
result = sm.read_doc("dd-todo-tracker", "xxx")
# {"success": True, "content": "..."}

# 更新文档
result = sm.update_doc("dd-todo-tracker", "xxx", "# 新内容\n")
# {"success": True, "action": "overwrite"}

# 删除文档
result = sm.delete_doc("dd-todo-tracker", "xxx")
# {"success": True, "action": "delete"}

# 列出文档
result = sm.list_docs("dd-todo-tracker")
# {"success": True, "docs": [{"name": "TODO", "nodeId": "xxx"}]}
```

## 配置

### 环境变量

| 环境变量 | 说明 | 默认值 | 是否必填 |
|---------|------|--------|---------|
| `SM_BACKEND` | 存储后端，支持 `dingtalk`（知识库）、`dingtalk-drive`（钉盘）、`local` | `dingtalk` | 否 |
| `SM_WORKSPACE_ID` | 钉钉知识库空间 ID（仅 dingtalk） | 自动查询 | 否 |
| `SM_DRIVE_SPACE_ID` | 钉盘空间 ID（仅 dingtalk-drive） | 自动查询第一个空间 | 否 |
| `SM_DRIVE_ROOT_FOLDER_ID` | 钉盘根文件夹 ID（仅 dingtalk-drive） | 自动查询 | 否 |

### 构造函数参数

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `backend` | `str` | 存储后端，`dingtalk`、`dingtalk-drive` 或 `local` | 从 `SM_BACKEND` 读取，默认 `dingtalk` |
| `folder_name` | `str` | 钉钉/微云存储根文件夹名称 | `"[勿动]SkillsMemory"` |

**使用示例**：

```python
from skills_memory import SkillsMemory

# 默认配置
sm = SkillsMemory()

# 指定后端
sm = SkillsMemory(backend="dingtalk-drive")

# 指定后端 + 自定义文件夹名称
sm = SkillsMemory(backend="dingtalk", folder_name="[勿动]MyCustomFolder")
```

**后端切换**：

```bash
# 默认：钉钉知识库
python skills_memory.py list dd-todo-tracker

# 钉钉云盘（钉盘）
SM_BACKEND=dingtalk-drive python skills_memory.py list dd-todo-tracker

# 微云网盘
SM_BACKEND=weiyun python skills_memory.py list dd-todo-tracker

# 本地文件系统
SM_BACKEND=local python skills_memory.py list dd-todo-tracker
```

## 存储后端

### 钉钉知识库后端（默认）

```
知识库空间 (自动获取)
└── [勿动]SkillsMemory/         ← 自动创建
    └── <skill_name>/            ← 每个技能独立文件夹
        ├── <doc_name>           ← 文档（知识库格式）
        └── ...
```

### 钉钉云盘后端（钉盘）

> ⚠️ **注意**：钉盘后端需要额外的 API 权限（`drive` 权限），当前可能因权限不足无法使用。建议优先使用 `dingtalk`（知识库）后端。

```
钉盘根目录
└── [勿动]SkillsMemory/         ← 自动创建
    └── <skill_name>/            ← 每个技能独立文件夹
        ├── <doc_name>.txt       ← 文本文档
        └── ...
```

### 微云网盘后端（weiyun）

> ⚠️ **注意**：微云后端需要预先完成 OAuth 授权并配置 MCP Token。

```
微云根目录
└── SkillsMemory/               ← 自动创建
    └── <skill_name>/          ← 每个技能独立文件夹
        ├── <doc_name>.txt     ← 文本文档
        └── ...
```

**授权流程**：
1. 访问 [微云开放平台](https://www.weiyun.com/act/openclaw) 获取 Token
2. 保存 Token 到 `~/.skills-memory/.env`：
   ```bash
   mkdir -p ~/.skills-memory
   echo 'WEIYUN_MCP_TOKEN="your_token_here"' > ~/.skills-memory/.env
   ```
3. 使用：`SkillsMemory(backend="weiyun")`

**Token 加载优先级**：
1. `~/.skills-memory/.env` 文件中的 `WEIYUN_MCP_TOKEN`
2. 环境变量 `WEIYUN_MCP_TOKEN`

**注意**：微云后端通过 HTTP 直接调用微云 MCP API，无需安装 `mcporter`。

### 本地文件后端

```
~/.skills-memory/              ← 自动创建
└── <skill_name>/              ← 每个技能独立文件夹
    ├── <doc_name>.md          ← 文档
    └── ...
```

## 依赖

- Python 3.10+
- `dws` CLI（钉钉后端时需要）
- `requests` 库（微云后端时需要）

## 被委托技能

| 技能 | 存储委托 |
|------|---------|
| dd-todo-tracker | ✅ 纯声明式，无脚本 |
| dd-work-log | ✅ 纯声明式，无脚本 |
| ... | 其他 dd- 前缀技能 |

## 特性

| 特性 | 说明 |
|------|------|
| 与技能无关 | 不感知任何业务语义 |
| 原子操作 | 只提供 CRUD，不做任何业务处理 |
| 技能隔离 | 每个技能独立命名空间 |
| 后端可配置 | 支持钉钉知识库、钉钉云盘、微云网盘、本地文件四种后端 |
| 自动创建 | 文件夹、文档按需自动创建 |
