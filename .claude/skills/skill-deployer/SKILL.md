---
name: skill-deployer
description: 将技能按场景（profile）软链接部署到各 Agent 目录。修改技能后执行。
---

# 技能部署

修改技能后、push 前执行，确保各 Agent 目录同步最新。

## ⚡ 先行判断

| 场景 | 操作 |
|------|------|
| 修改了技能内容（SKILL.md/脚本/references） | 部署当前 profile |
| 新增/删除技能 | 部署 + lint |
| 修改 deploy.json | 部署受影响 profile |

## 执行流程

### ① 确定当前 profile

默认 `home`。如果用户指定了 profile 则用指定的。

```bash
python3 .claude/skills/skill-deployer/scripts/sync.py --list
```

### ② 执行部署

```bash
python3 .claude/skills/skill-deployer/scripts/sync.py --profile home
```

可选参数：

| 参数 | 作用 |
|------|------|
| `--dry-run` | 预览，不实际操作 |
| `--force` | 强制替换非空目录（慎用） |
| `--agent hermes` | 仅部署指定 agent |

### ③ 验证

部署后检查目标目录结构：

- `~/.hermes/skills/skills-store/` — 应包含所有技能的软链接
- `~/.workbuddy/skills/skills-store/` — 应包含所有技能的软链接
- 软链接指向源目录，`ls -la` 可确认

## 目录结构

```
~/.hermes/
  skills/
    skills-store/          ← 部署目标（软链接）
      inv-stock-data → ~/.skills-store/custom-skills/inv-stock-data
      inv-valuation-engine → ~/.skills-store/custom-skills/inv-valuation-engine
      ...
    [其他来源技能...]       ← 不受部署影响
```

## deploy.json 配置

```json
{
  "profiles": {
    "home":   ["hermes", "workbuddy"],
    "work":   ["hermes", "workbuddy"],
    "server": ["hermes"]
  },
  "agents": {
    "hermes":    { "skills_dir": "~/.hermes/skills/skills-store" },
    "workbuddy": { "skills_dir": "~/.workbuddy/skills/skills-store" }
  }
}
```

- 每个 agent 的技能部署到 `skills/skills-store/` 子目录，不影响其他来源的技能
- profile 是 agent 名称列表，所有技能都会部署到列出的 agent

## sync.py 核心逻辑

脚本路径：`.claude/skills/skill-deployer/scripts/sync.py`

### 输入

1. `.claude/skills/skill-deployer/scripts/deploy.json` — profiles 与 agents 配置
2. `custom-skills/` — 技能源码目录（扁平结构）

### 同步流程

```
1. 加载 deploy.json
2. 扫描 custom-skills/ 顶层 → 收集所有技能目录
3. 对 profile 中的每个 agent：
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
