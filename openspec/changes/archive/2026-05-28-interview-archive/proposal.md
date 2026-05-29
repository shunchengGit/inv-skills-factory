## Why

面试技能目前候选人状态链到"已面试"就断了，`archived/` 目录在 SKILL.md 中声明但从未使用。面试完成后简历和面试题文件一直留在 `resume/` 下，活跃候选人列表越积越多，无法区分进行中和已结束的流程。

## What Changes

- 新增 `archive <名>` 命令：将候选人 PDF 和面试题 .md 移动到 `archived/<姓名>/` 目录
- 归档前校验：必须已完成面试（面试题文件存在且含评分）
- `list` 命令默认只显示 `resume/` 下活跃候选人，新增 `--all` 参数追加显示已归档候选人
- SKILL.md 更新命令表和数据目录说明

## Capabilities

### New Capabilities
- `interview-archive`: 面试完成后的候选人归档流程，包含归档命令、目录结构、list 过滤

### Modified Capabilities
<!-- 无现有 spec 需要修改 -->

## Impact

- `custom-skills/general/interview/scripts/interview.py` — 新增 `archive` 子命令，修改 `list` 函数
- `custom-skills/general/interview/SKILL.md` — 更新命令表和数据目录说明
