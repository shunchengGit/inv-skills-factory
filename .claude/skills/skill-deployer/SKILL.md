---
name: skill-deployer
description: 软链接方式部署技能到 Agent 目录，同步 _shared/ 模块。Use when 部署/同步技能时
version: 1.0.0
trigger:
  - 部署技能
  - 同步技能
  - deploy
  - 发布技能
---

# 技能部署

修改技能后、push 前执行，确保 Agent 目录同步最新。

## ⚡ 先行判断

| 场景 | 操作 |
|------|------|
| 修改了技能内容（SKILL.md/脚本/references） | 部署到对应 agent |
| 新增/删除技能 | 部署 + lint |
| 修改 deploy.json | 部署受影响 agent |

## 执行流程

### ① 确定 agent（必填）

`--agent` 强制必填，未指定直接退出。可多选，或用 `all` 部署全部。

```bash
python3 .claude/skills/skill-deployer/scripts/sync.py --list
```

### ② 执行部署

```bash
# 单个 agent
python3 .claude/skills/skill-deployer/scripts/sync.py --agent hermes

# 多个 agent
python3 .claude/skills/skill-deployer/scripts/sync.py --agent hermes workbuddy

# 全部 agent
python3 .claude/skills/skill-deployer/scripts/sync.py --agent all

# 预览
python3 .claude/skills/skill-deployer/scripts/sync.py --agent hermes --dry-run
```

可选参数：

| 参数 | 作用 |
|------|------|
| `--dry-run` | 预览，不实际操作 |
| `--force` | 强制替换非空目录（慎用） |
| `--list` | 列出可用 agent |

### ③ 验证

部署后检查目标目录结构：

- `~/.hermes/skills/inv-skills/` — 应包含所有技能的软链接
- `~/.workbuddy/skills/inv-skills/` — 应包含所有技能的软链接
- 软链接指向源目录，`ls -la` 可确认

## 目录结构

```
~/.hermes/
  skills/
    inv-skills/            ← 部署目标（软链接）
      inv-stock-data → ~/.skills-store/custom-skills/inv-stock-data
      inv-valuation-engine → ~/.skills-store/custom-skills/inv-valuation-engine
      ...
    [其他来源技能...]       ← 不受部署影响
```

## deploy.json 配置

```json
{
  "agents": {
    "hermes":    { "skills_dir": "~/.hermes/skills/inv-skills" },
    "workbuddy": { "skills_dir": "~/.workbuddy/skills/inv-skills" }
  }
}
```

- 每个 agent 的技能部署到 `skills/inv-skills/` 子目录，不影响其他来源的技能

## sync.py 核心逻辑

脚本路径：`.claude/skills/skill-deployer/scripts/sync.py`

### 输入

1. `.claude/skills/skill-deployer/scripts/deploy.json` — agents 配置
2. `custom-skills/` — 技能源码目录（扁平结构）

### 同步流程

```
1. 加载 deploy.json
2. 扫描 custom-skills/ 顶层 → 收集所有技能目录
3. 对 --agent 指定的每个 agent：
   a. 确保目标目录存在
   b. 创建软链接：目标/技能名 → 源/技能名
   c. 清理不再存在的过期软链接
4. 汇报结果：created / skipped / failed / removed
```

### 扫描规则

- `_shared` 目录不是技能，作为共享工具模块单独同步
- `custom-skills/` 下所有含 `SKILL.md` 的子目录都是技能

### 清理规则

- 仅删除**软链接**，不删除普通目录或文件
- 如果目标目录下存在**非空普通目录**且名称不在当前技能列表中：
  - 默认跳过并警告
  - `--force` 模式下删除
