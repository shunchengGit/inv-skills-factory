## Why

用户在 `custom-skills/` 中维护 7 个投资分析技能，但需要将它们同步到本机安装的多个非代码类 Agent（Claude Desktop、Claude Code IDE 扩展等）各自的技能目录中。当前没有自动化同步机制，手动复制容易遗漏、产生版本漂移，且无法区分 "Agent 自行安装的技能" 和 "从本仓库同步的技能"。

## What Changes

- 新建 `scripts/` 目录（仓库根目录），存放通用工具脚本
- 新增 `scripts/sync_skills.py`：将 `custom-skills/` 中的所有技能通过软链接同步到目标 Agent 的技能目录
- 支持通过配置文件（`scripts/agent_targets.json`）定义多个目标 Agent 及其技能目录路径
- 冲突处理：若目标路径已存在同名技能目录且不是软链接，自动重命名为 `<name>_bak` 后创建软链接；若已是软链接则跳过或更新指向
- 支持 `--dry-run` 预览模式，不实际执行变更

## Capabilities

### New Capabilities

- `skill-sync`: 技能同步脚本 — 读取目标配置，将 custom-skills 通过软链接同步到各 Agent 目录，处理冲突（非软链接→重命名 _bak），支持 dry-run 预览

### Modified Capabilities

（无现有 capability 被修改）

## Impact

- 仓库根目录新增 `scripts/` 文件夹和 `scripts/sync_skills.py`、`scripts/agent_targets.json`
- 不影响任何现有 skill 的结构或内容
- 目标 Agent 的技能目录结构会变更（新增软链接，冲突项被重命名）
