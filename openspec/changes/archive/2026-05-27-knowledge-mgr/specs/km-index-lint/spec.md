## ADDED Requirements

### Requirement: Index.md 引用完整性检查
脚本 SHALL 检查 Index.md 中引用的所有 md 文件是否存在。

#### Scenario: 引用的文件存在
- **WHEN** Index.md 中 `- [标题](path)` 的 path 指向一个存在的文件
- **THEN** 标记为 OK

#### Scenario: 引用的文件不存在
- **WHEN** Index.md 中引用的 path 对应文件不存在
- **THEN** 标记为 dead_link，报告该条目

### Requirement: 原文 URL 可达性检查
脚本 SHALL 对每个知识条目 frontmatter 中的 url 字段发起 HEAD 请求检查可达性。

#### Scenario: URL 可达
- **WHEN** HEAD 请求返回 2xx/3xx 状态码
- **THEN** 标记为 OK

#### Scenario: URL 不可达
- **WHEN** HEAD 请求超时（10s）或返回 4xx/5xx
- **THEN** 标记为 dead_url，报告该条目

#### Scenario: frontmatter 缺少 url
- **WHEN** md 文件的 frontmatter 中没有 url 字段
- **THEN** 标记为 missing_url

### Requirement: 孤立文件检测
脚本 SHALL 检查 `~/.knowledge/` 下所有 md 文件（排除 Index.md）是否在 Index.md 中被引用。

#### Scenario: 文件被 Index 引用
- **WHEN** md 文件出现在 Index.md 的路径中
- **THEN** 标记为 OK

#### Scenario: 文件未被 Index 引用
- **WHEN** md 文件存在但未出现在 Index.md 中
- **THEN** 标记为 orphan，报告该文件

### Requirement: 输出格式
脚本 SHALL 以 JSON 格式输出检查结果：

```json
{
  "dead_links": [{"title": "...", "path": "..."}],
  "dead_urls": [{"path": "...", "url": "...", "status": 404}],
  "missing_urls": [{"path": "..."}],
  "orphans": [{"path": "...", "title": "..."}],
  "total_entries": 10,
  "total_issues": 3
}
```