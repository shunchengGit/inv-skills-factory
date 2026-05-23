## Context

用户在本仓库 `custom-skills/` 下维护 7 个投资分析技能。多个 Claude 客户端（Desktop、Code IDE 扩展等）各自有独立的技能目录，需要将本仓库的技能同步过去。当前无自动化机制，手动操作易遗漏和产生版本漂移。

## Goals / Non-Goals

**Goals:**
- 提供一键脚本，将 `custom-skills/` 所有技能通过软链接同步到配置中列出的所有 Agent
- 安全处理冲突：非软链接的现有目录自动命名为 `_bak` 后创建软链接
- 支持 `--dry-run` 预览
- 配置文件可扩展，用户添加新 Agent 只需编辑 JSON

**Non-Goals:**
- 不支持 Windows（仅 macOS/Linux，依赖 POSIX 软链接）
- 不做双向同步（仓库是唯一数据源，Agent 端的变更不会被回写）
- 不处理 Agent 进程的自动重启（同步后用户需手动重启 Agent）
- 不检测 Agent 端技能目录中的孤立软链接（指向已删除 source 的死链接）

## Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 脚本语言 | Python 3.10+（仅标准库） | 与仓库现有技能脚本一致，`pathlib` 处理路径比 bash 健壮 |
| 配置格式 | JSON（`scripts/agent_targets.json`） | 简单、无外部依赖、人类可读写、仓库内已有 JSON 惯例 |
| 同步方式 | 符号链接（symlink） | 零维护——源更新后 Agent 端自动生效，无需重新同步 |
| 冲突检测 | `pathlib.Path.is_symlink()` + `os.readlink()` | 标准库能力，无需外部工具 |
| 仅同步有效技能 | 只同步含 `SKILL.md` 的目录 | 避免同步 `_未分类` 等非技能目录 |

**为什么不使用硬链接？** 硬链接不能跨文件系统，且无法直观区分 "本仓库管理的" 和 "Agent 自有的"。

**为什么不用配置文件 `.yaml`？** YAML 需要第三方库。JSON 是 Python 标准库内置支持，且 `_meta.json` 已建立 JSON 惯例。

## Configuration Format

`scripts/agent_targets.json`:

```json
{
  "agents": [
    {
      "name": "claude-desktop",
      "skills_dir": "~/Library/Application Support/Claude/skills",
      "enabled": true
    }
  ]
}
```

- `name`: 用于日志输出的可读名称
- `skills_dir`: Agent 技能目录的绝对路径（支持 `~` 展开）
- `enabled`: `false` 时跳过该 Agent

## Symlink Strategy

```
source:  ~/.SkillsStore/custom-skills/cs-stock/
target:  ~/Library/Application Support/Claude/skills/cs-stock/

场景 A: target 不存在 → ln -s source target
场景 B: target 是软链接且指向正确 → 跳过
场景 C: target 是软链接但指向错误 → 更新（删除旧链接，创建新链接）
场景 D: target 不是软链接（普通目录/文件） → mv target target_bak → ln -s source target
场景 E: target 是断开的软链接 → 删除，重建
```

## Conflict Rename Strategy

命名冲突时：`<原名>_bak`，若 `_bak` 也已存在则追加数字：`<原名>_bak2`, `_bak3` ...

## Risks / Trade-offs

- [软链接在 zip/归档时可能断掉] → 不影响，技能目录始终在本机
- [Agent 不支持跟随软链接] → 已知问题，目前主流的 Claude 客户端均支持；若某 Agent 不支持，需将该 Agent 的 `enabled` 设为 `false`
- [删除源技能后 Agent 端产生死链接] → Non-goal，用户手动清理即可；未来可加 `--cleanup` 选项
- [非技能目录被软链接] → 通过 `SKILL.md` 存在性过滤
