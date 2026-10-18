---
name: skill-deployer
description: 软链接方式部署技能到 Hermes 目录，同步 _shared/ 模块。Use when 部署/同步技能时
version: 1.1.0
trigger:
  - 部署技能
  - 同步技能
  - deploy
  - 发布技能
---

# 技能部署

部署目标只有 Hermes（`deploy.json` 中的 `hermes`）。不部署到 WorkBuddy，也不要恢复该目标。

## ⚡ 先行判断

| 场景 | 操作 |
|------|------|
| 修改了技能内容（SKILL.md/脚本/references） | 无需部署，软链接即时生效；只需 lint |
| 新增/删除技能、修复链接 | 部署 + lint |
| 修改 deploy.json | 部署受影响 agent |

## 执行流程

`--agent` 必填，未指定直接退出。`sync.py` 带 PEP 723 依赖（python-dotenv），用 `uv run` 启动，不要用 `python3` 直跑。

```bash
# 列出可用 agent
uv run .claude/skills/skill-deployer/scripts/sync.py --list

# 预览
uv run .claude/skills/skill-deployer/scripts/sync.py --agent hermes --dry-run

# 部署
uv run .claude/skills/skill-deployer/scripts/sync.py --agent hermes
```

可选参数：

| 参数 | 作用 |
|------|------|
| `--dry-run` | 预览，不实际操作 |
| `--force` | 强制替换非空目录（慎用） |
| `--list` | 列出可用 agent |

部署后检查 `~/.hermes/skills/inv-skills/` 包含所有技能的软链接，`ls -la` 可确认指向源目录。

## 目录结构

```
~/.hermes/
  skills/
    inv-skills/            ← 部署目标（软链接，子目录名来自 .env 的 DEPLOY_SKILLS_DIR）
      inv-stock-data → ~/.inv-skills-factory/custom-skills/inv-stock-data
      inv-valuation-engine → ~/.inv-skills-factory/custom-skills/inv-valuation-engine
      ...
    [其他来源技能...]       ← 不受部署影响
```

## deploy.json 配置

```json
{
  "agents": {
    "hermes": { "skills_dir": "~/.hermes/skills" }
  }
}
```

实际部署目录 = `skills_dir` + `/` + `.env` 中的 `DEPLOY_SKILLS_DIR`（如 `inv-skills`），不影响其他来源的技能。

## sync.py 核心逻辑

### 同步流程

```
1. 加载 deploy.json 与 .env（DEPLOY_SKILLS_DIR 缺失时交互询问并写入 .env）
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
