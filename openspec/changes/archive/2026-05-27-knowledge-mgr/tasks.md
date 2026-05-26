## 1. 技能脚手架

- [x] 1.1 创建 `custom-skills/knowledge-mgr/` 目录结构（scripts/、SKILL.md、_meta.json）
- [x] 1.2 编写 SKILL.md（YAML frontmatter + 三个命令说明 + 用法示例 + 依赖声明）
- [x] 1.3 编写 _meta.json（name/version/description/commands/scripts/dependencies）

## 2. km_init.py

- [x] 2.1 实现 git clone/pull 逻辑（~/.knowledge 不存在→clone，存在且同仓库→pull，非 git→报错）
- [x] 2.2 实现 Index.md 解析和结构化 JSON 输出（categories + total_entries）
- [x] 2.3 实现 Index.md 不存在时创建空模板
- [x] 2.4 实现异常处理（网络/SSH/仓库不存在）和 JSON 错误输出

## 3. km_import.py

- [x] 3.1 实现 `fetch` 子命令：Firecrawl scrape 优先 → pwright_scrape 兜底，输出 JSON
- [x] 3.2 实现 `store` 子命令：写 md 文件（YAML frontmatter + 正文），自动创建分类目录
- [x] 3.3 实现 slug 生成（标题→kebab-case）和 _unsorted 兜底
- [x] 3.4 实现 Index.md 更新（追加条目到对应 category 的 `##` 下，无则新建 `##`）
- [x] 3.5 实现 git 同步（add + commit + push），push 失败只报错不回滚

## 4. km_lint.py

- [x] 4.1 实现 Index.md 引用完整性检查（path 对应文件是否存在）
- [x] 4.2 实现 URL 可达性检查（HEAD 请求，10s 超时）
- [x] 4.3 实现孤立文件检测（md 文件未出现在 Index.md 中）
- [x] 4.4 实现 JSON 格式结果输出（dead_links/dead_urls/missing_urls/orphans/total_issues）

## 5. 集成测试

- [x] 5.1 测试 km_init.py：首次 clone、已有仓库 pull、非 git 目录报错
- [x] 5.2 测试 km_import.py fetch：Firecrawl 成功、pwright 兜底、两者均失败
- [x] 5.3 测试 km_import.py store：正常存储、Index.md 更新、git commit+push
- [x] 5.4 测试 km_lint.py：死链检测、孤立文件、URL 不可达