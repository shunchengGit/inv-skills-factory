## ADDED Requirements

### Requirement: Agent 目标配置

系统 SHALL 从 `scripts/agent_targets.json` 读取一组 Agent 配置，每个 Agent 包含 `name`（名称）、`skills_dir`（技能目录路径，支持 `~` 展开）、`enabled`（是否启用）字段。

#### Scenario: 读取有效配置

- **WHEN** `scripts/agent_targets.json` 存在且格式正确
- **THEN** 系统解析所有 `enabled: true` 的 Agent 条目，并对每个 Agent 展开 `skills_dir` 中的 `~` 为用户 home 目录

#### Scenario: 跳过禁用的 Agent

- **WHEN** 某 Agent 条目的 `enabled` 为 `false`
- **THEN** 系统在同步时跳过该 Agent，并在日志中注明

#### Scenario: 配置文件缺失

- **WHEN** `scripts/agent_targets.json` 不存在
- **THEN** 系统 SHALL 输出错误信息并退出，退出码非零

### Requirement: 技能发现

系统 SHALL 扫描 `custom-skills/` 目录，仅将包含 `SKILL.md` 的子目录识别为有效技能。

#### Scenario: 识别有效技能

- **WHEN** `custom-skills/<name>/` 目录存在且包含 `SKILL.md` 文件
- **THEN** 该目录被识别为有效技能，纳入同步范围

#### Scenario: 排除非技能目录

- **WHEN** `custom-skills/<name>/` 目录存在但不包含 `SKILL.md` 文件
- **THEN** 该目录被排除，不进行同步

### Requirement: 软链接同步

系统 SHALL 对每个 Agent × 技能组合，在 Agent 技能目录下创建指向 `custom-skills/<name>/` 的符号链接。

#### Scenario: 目标不存在 —— 创建软链接

- **WHEN** Agent 技能目录下不存在同名技能目录 `skills/<name>`
- **THEN** 系统创建符号链接：`<skills_dir>/<name>` → `custom-skills/<name>`

#### Scenario: 已是正确软链接 —— 跳过

- **WHEN** 目标路径已是符号链接，且其指向与源路径相同（经 `os.readlink` 比对）
- **THEN** 系统跳过该条目，不做任何变更

#### Scenario: 软链接指向不同源 —— 更新

- **WHEN** 目标路径是符号链接，但指向与当前 `custom-skills/<name>/` 不同
- **THEN** 系统 SHALL 删除旧链接，创建新链接指向正确的源路径

#### Scenario: 目标路径是普通目录 —— 重命名后创建

- **WHEN** 目标路径存在且不是符号链接（普通目录）
- **THEN** 系统 SHALL 将该目录重命名为 `<name>_bak`（若 `_bak` 已存在则尝试 `_bak2`、`_bak3`...），然后创建符号链接指向源路径

#### Scenario: 目标路径是断开的符号链接 —— 删除后重建

- **WHEN** 目标路径是符号链接但指向的源已不存在
- **THEN** 系统 SHALL 删除断开的链接，创建新链接指向当前正确的源路径

### Requirement: Dry-run 模式

系统 SHALL 支持 `--dry-run` 参数，在预览模式下仅输出将要执行的操作，不执行任何文件系统变更。

#### Scenario: Dry-run 输出预览

- **WHEN** 传入 `--dry-run` 参数
- **THEN** 系统输出每条计划操作（创建/跳过/更新/重命名），但不执行任何 `ln -s`、`mv` 或 `rm` 操作

### Requirement: 操作日志

系统 SHALL 在标准输出逐条报告同步操作，包括：技能名称、目标 Agent、操作类型（创建/跳过/更新/重命名）。

#### Scenario: 同步完成后输出汇总

- **WHEN** 同步完成
- **THEN** 系统输出汇总：共 N 个技能，创建 X，跳过 Y，更新 Z，重命名 W
