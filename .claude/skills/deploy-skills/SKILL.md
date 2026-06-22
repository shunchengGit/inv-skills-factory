---
name: deploy-skills
description: 将技能和 hooks 按场景（profile）软链接部署到各 Agent 目录。修改技能后执行。
---

# 技能部署

修改技能后、push 前执行，确保各 Agent 目录同步最新。

## ⚡ 先行判断

| 场景 | 操作 |
|------|------|
| 修改了技能内容（SKILL.md/脚本/references） | 部署当前 profile |
| 新增/删除技能 | 部署 + lint |
| 修改 deploy.json | 部署受影响 profile |
| 仅修改 hooks | `--hooks-only` |

## 执行流程

### ① 确定当前 profile

默认 `home`。如果用户指定了 profile 则用指定的。

```bash
python3 .claude/skills/deploy-skills/sync.py --list
```

### ② 执行部署

```bash
python3 .claude/skills/deploy-skills/sync.py --profile home
```

可选参数：

| 参数 | 作用 |
|------|------|
| `--dry-run` | 预览，不实际操作 |
| `--force` | 强制替换非空目录（慎用） |
| `--agent hermes` | 仅部署指定 agent |
| `--hooks-only` | 仅同步 hooks |
| `--skills-only` | 仅同步技能 |

### ③ 验证

部署后检查目标目录结构：

- `~/.hermes/skills/skills-store/` — 应包含 profile 对应的技能软链接
- `~/.workbuddy/skills/skills-store/` — 应包含 profile 对应的技能软链接
- 软链接指向源目录，`ls -la` 可确认

## 目录结构

```
~/.hermes/
  skills/
    skills-store/          ← 部署目标（软链接）
      base-skill-loader → ~/.skills-store/custom-skills/base/base-skill-loader
      gen-daily-planner → ~/.skills-store/custom-skills/general/gen-daily-planner
      ...
    [其他来源技能...]       ← 不受部署影响
  hooks/
    base-skill-loader → ~/.skills-store/custom-hooks/hermes/base-skill-loader
```

## deploy.json 配置

```json
{
  "profiles": {
    "home":   { "hermes": ["general", "invest"], "workbuddy": ["general"] },
    "work":   { "hermes": ["general"],           "workbuddy": ["general"] },
    "server": { "hermes": ["invest"] }
  },
  "agents": {
    "hermes":    { "skills_dir": "~/.hermes/skills/skills-store", "hooks_dir": "~/.hermes/hooks" },
    "workbuddy": { "skills_dir": "~/.workbuddy/skills/skills-store", "hooks_dir": "~/.workbuddy/hooks" }
  }
}
```

- `base` 分类始终同步，无需在 profile 中声明
- 每个 agent 的技能部署到 `skills/skills-store/` 子目录，不影响其他来源的技能

## sync.py 核心逻辑

脚本路径：`.claude/skills/deploy-skills/sync.py`

### 输入

1. `.claude/skills/deploy-skills/deploy.json` — profiles 与 agents 配置
2. `custom-skills/` — 技能源码目录
3. `custom-hooks/` — hooks 源码目录

### 同步流程

```
1. 加载 deploy.json
2. 展开所有分类 → 收集技能目录列表（base 始终包含）
3. 对每个 agent：
   a. 确保目标目录存在
   b. 创建软链接：目标/技能名 → 源/分类/技能名
   c. 清理不在当前 profile 范围内的过期软链接
4. 汇报结果：created / skipped / failed / removed
```

### 分类展开规则

- `base` 始终包含，profile 中无需声明
- `_shared` 目录不是技能，跳过
- profile 中声明的分类名对应 `custom-skills/` 下的子目录名

### 清理规则

- 仅删除**软链接**，不删除普通目录或文件
- 如果目标目录下存在**非空普通目录**且名称不在当前 profile 范围内：
  - 默认跳过并警告
  - `--force` 模式下删除

### hooks 同步

- 按代理隔离：`custom-hooks/hermes/` → `~/.hermes/hooks/`
- 同样使用软链接，同样的清理规则
