## ADDED Requirements

### Requirement: 仓库初始化
脚本 SHALL 从 `git@github.com:shunchengGit/knowledge.git` 拉取仓库到 `~/.knowledge` 目录。

#### Scenario: 首次初始化（目录不存在）
- **WHEN** `~/.knowledge` 目录不存在
- **THEN** 执行 `git clone git@github.com:shunchengGit/knowledge.git ~/.knowledge`

#### Scenario: 已有仓库同步
- **WHEN** `~/.knowledge` 存在且其 git remote 指向同一仓库
- **THEN** 执行 `git -C ~/.knowledge pull`

#### Scenario: 目录存在但非 git 仓库
- **WHEN** `~/.knowledge` 存在但不是 git 仓库
- **THEN** 输出错误信息并退出，不覆盖现有内容

### Requirement: 初始化后输出 Index 数据
脚本 SHALL 在 clone/pull 完成后读取 `~/.knowledge/Index.md`，将解析后的结构化数据以 JSON 格式输出到 stdout。

#### Scenario: Index.md 存在
- **WHEN** `~/.knowledge/Index.md` 存在
- **THEN** 解析 Index.md 中的 `##` 标题为 category，`- [标题](路径) — url` 为条目，输出 JSON `{categories: {<name>: [{title, path, url}, ...]}, total_entries: <N>}`

#### Scenario: Index.md 不存在（首次 init）
- **WHEN** `~/.knowledge/Index.md` 不存在
- **THEN** 创建空 Index.md 模板（含 `# Knowledge Index` 标题），输出 `{categories: {}, total_entries: 0}`

### Requirement: 异常处理
脚本 SHALL 对网络失败、SSH 权限、远程仓库不存在等异常输出明确错误信息。

#### Scenario: 网络不通
- **WHEN** git clone/pull 因网络原因失败
- **THEN** 输出包含原始错误信息的 JSON，`success: false`

#### Scenario: 远程仓库不存在
- **WHEN** 远程仓库地址无效或无访问权限
- **THEN** 输出提示检查仓库地址和 SSH key 配置的 JSON，`success: false`