## Context

用户需要一个个人知识管理技能，将散落在网页中的投资相关知识（估值方法论、行业洞察、公司研究）系统化采集、总结、存储和检索。知识存储在独立 git 仓库 `~/.knowledge`，与投资技能的 `custom-skills/` 分离。现有 `cs-crawl` 已提供 Firecrawl adapter 和 `pwright_scrape.py`，可直接复用。

## Goals / Non-Goals

**Goals:**
- 通过三个 CLI 命令（init/import/lint）覆盖知识管理的完整生命周期
- import 流程将"抓取"与"总结分类"分离：脚本负责抓取和文件操作，Claude 在对话中负责总结和分类
- 知识库与 git 同步，支持多设备访问
- init 后自动输出 Index 结构化数据，让 Claude 感知所有知识条目

**Non-Goals:**
- 不做全文搜索（依赖 Claude 对话上下文 + Index.md 定位）
- 不做 Web UI
- 不做自动定时抓取
- 不做知识条目之间的自动关联推荐

## Decisions

### 1. 脚本只做抓取+文件操作，Claude 做总结+分类

**选择**：km_import.py 只负责抓取 URL 内容并输出 JSON，不调用 LLM。Claude 在对话中完成总结和分类后，再次调用脚本的 `store` 子命令写文件。

**替代方案**：脚本内置 LLM 调用做总结分类。

**理由**：避免脚本依赖 API key；Claude 已在对话中，总结质量更高；脚本更简单可测。

### 2. Index.md 为纯 Markdown，非数据库

**选择**：Index.md 按 category 分 `##` 标题，每条一行 `- [标题](path) — url`。

**替代方案**：JSON/YAML 索引文件。

**理由**：人类可读可编辑；Claude 直接读取理解；lint 脚本用正则即可解析。

### 3. 知识条目用 YAML frontmatter 存元数据

**选择**：每个 md 文件头部 `---` 包裹 url/imported/category 字段。

**替代方案**：元数据只存 Index.md。

**理由**：文件自包含，即使脱离 Index 也能溯源；lint 可交叉校验。

### 4. 聚类目录预定义 + 动态扩展

**选择**：初始默认目录从 Index.md 的 `##` 标题读取（空 Index 时用 `investing`/`programming`/`science`/`life`/`_unsorted`）。Claude 分类时可新建目录，下次 init 自动感知。

**替代方案**：固定目录不允许扩展。

**理由**：知识领域会自然增长，锁死分类不现实。

### 5. push 失败只报错不回滚

**选择**：commit 后 push 失败，保留本地 commit，输出错误信息提示手动 push。

**替代方案**：push 失败时 git reset 回滚 commit。

**理由**：网络问题是暂时的，本地数据不应因此丢失；手动 push 成本极低。

## Risks / Trade-offs

- [Firecrawl/pwright 均失败] → import 无法完成，需用户手动粘贴内容 → 脚本应提供 `store` 子命令支持从 stdin 读取内容
- [Index.md 格式被手动编辑破坏] → lint 解析失败 → lint 应容错，跳过无法解析的行并报告
- [远程仓库不存在] → init clone 失败 → 给出明确错误信息和创建仓库的提示
- [知识条目量增长后 Index.md 过大] → Claude 上下文窗口压力 → 当前阶段不优化，观察实际规模再决策