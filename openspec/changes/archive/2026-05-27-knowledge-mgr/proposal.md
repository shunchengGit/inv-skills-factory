## Why

投资分析技能依赖大量跨领域知识（估值方法论、行业洞察、公司研究），这些知识分散在网页文章中且难以检索。需要一个技能来系统化地采集、总结、存储和检索这些知识，与现有投资技能形成闭环。

## What Changes

- 新建 `knowledge-mgr` 技能，提供三个命令：`/km_init`、`/km_import`、`/km_lint`
- init：从远程仓库 `git@github.com:shunchengGit/knowledge.git` 拉取到 `~/.knowledge`，完成后输出 Index.md 结构化数据供 LLM 感知
- import：单条 URL 抓取（Firecrawl 优先 → pwright_scrape 兜底）→ Claude 总结+分类 → 写 md + 更新 Index.md → git commit + push
- lint：检查 Index.md 死链、孤立文件、frontmatter 一致性
- 知识条目格式：YAML frontmatter（url, imported, category）+ 正文（标题、摘要、关键要点）
- 聚类存储：按 category 分目录，未归类放 `_unsorted/`

## Capabilities

### New Capabilities
- `km-repo-init`: 远程仓库拉取与本地同步（clone/pull/异常处理/Index 输出）
- `km-url-import`: URL 抓取→总结→分类→存储→Index 更新→git 同步
- `km-index-lint`: Index.md 死链检查、孤立文件检测、一致性校验

### Modified Capabilities

（无现有 spec 需修改）

## Impact

- 新增 skill 目录 `custom-skills/knowledge-mgr/`（3 个 Python 脚本 + SKILL.md + _meta.json）
- 依赖 `cs-crawl` 的 Firecrawl adapter 和 `pwright_scrape.py`
- 依赖 `_shared/proxy.py` 代理检测
- 远程仓库 `git@github.com:shunchengGit/knowledge.git` 需存在且可访问
- 不影响现有投资技能，知识条目可被其他技能引用（如 value-investing-valuation 的"增量信息补充"环节）