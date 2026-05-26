## ADDED Requirements

### Requirement: URL 抓取
脚本 SHALL 接收一个 URL，优先用 Firecrawl scrape 抓取，失败后用 pwright_scrape 兜底。

#### Scenario: Firecrawl 成功
- **WHEN** Firecrawl adapter 对目标 URL 返回有效内容
- **THEN** 输出 JSON `{success: true, source: "firecrawl", title, content, url}`

#### Scenario: Firecrawl 失败，pwright 兜底成功
- **WHEN** Firecrawl 返回空内容/错误，且 pwright_scrape 成功
- **THEN** 输出 JSON `{success: true, source: "pwright", title, content, url}`

#### Scenario: 两者均失败
- **WHEN** Firecrawl 和 pwright_scrape 均失败
- **THEN** 输出 JSON `{success: false, error: <原因>, url}`

### Requirement: 知识条目存储
脚本 SHALL 提供 `store` 子命令，将总结后的知识写入 md 文件并更新 Index.md。

#### Scenario: 存储到分类目录
- **WHEN** 调用 `km_import.py store --title <t> --category <c> --url <u> --content <md>`
- **THEN** 写入 `~/.knowledge/<category>/<slug>.md`，slug 由标题生成（kebab-case）
- **AND** md 文件包含 YAML frontmatter（url, imported 日期, category）和正文
- **AND** 更新 `~/.knowledge/Index.md`，在对应 `## <category>` 下追加条目

#### Scenario: 分类目录不存在
- **WHEN** 指定的 category 目录不存在
- **THEN** 自动创建目录

#### Scenario: _unsorted 兜底
- **WHEN** 未指定 category 或 category 为空
- **THEN** 存储到 `~/.knowledge/_unsorted/`

### Requirement: Git 同步
脚本 SHALL 在 store 完成后执行 git add + commit + push。

#### Scenario: 正常同步
- **WHEN** store 写入文件并更新 Index.md 成功
- **THEN** 在 `~/.knowledge` 中执行 `git add -A && git commit -m "import: <标题> → <category>/" && git push`

#### Scenario: push 失败
- **WHEN** git push 因网络或其他原因失败
- **THEN** 保留本地 commit，输出警告信息提示手动 `git push`，不回滚

### Requirement: 知识条目 md 格式
每个知识条目文件 SHALL 遵循以下格式：

```markdown
---
url: https://example.com/article
imported: 2026-05-26
category: investing
---

# 文章标题

## 摘要
3-5 句总结

## 关键要点
- 要点1
- 要点2
```

### Requirement: 单条 URL 限制
脚本 SHALL 每次只处理一个 URL，不支持批量导入。