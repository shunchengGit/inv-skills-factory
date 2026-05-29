## ADDED Requirements

### Requirement: Archive command
系统 SHALL 提供 `archive <名>` 子命令，将候选人 PDF 和面试题 .md 移动到 `archived/<姓名>/` 目录下。

#### Scenario: 成功归档已面试候选人
- **WHEN** 执行 `archive 某某某`，且该候选人面试题文件存在且含评分
- **THEN** 在 `archived/某某某/` 下创建目录，将 PDF 和面试题 .md 移入，打印确认信息

#### Scenario: 归档未面试的候选人
- **WHEN** 执行 `archive 某某某`，但该候选人面试题文件不存在或不含评分
- **THEN** 打印错误提示"候选人尚未完成面试"，不执行移动

#### Scenario: 归档不存在的候选人
- **WHEN** 执行 `archive 某某某`，但 resume/ 下无该姓名的 PDF
- **THEN** 打印错误提示"未找到该候选人的简历"

#### Scenario: 归档目录已存在
- **WHEN** 执行 `archive 某某某`，但 `archived/某某某/` 目录已存在
- **THEN** 打印错误提示"该候选人已归档"，不执行移动

### Requirement: List with archive filter
`list` 命令 SHALL 默认只显示 `resume/` 下活跃候选人，`--all` 参数追加显示已归档候选人。

#### Scenario: 默认列出活跃候选人
- **WHEN** 执行 `list`
- **THEN** 只显示 resume/ 下的候选人，状态为待处理/已出题/已面试

#### Scenario: 列出全部候选人
- **WHEN** 执行 `list --all`
- **THEN** 显示 resume/ 下的活跃候选人 + archived/ 下的已归档候选人，已归档者状态标注为"已归档"
