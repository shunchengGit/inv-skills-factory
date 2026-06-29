# 异常处理与 lint 修复

## lint 修复工作流（LLM 驱动）

当 `km_lint --fix` 后仍有孤立条目（`no_cross_refs > 0`）时，按以下步骤修复：

### 步骤 1：读取 lint 结果获取孤立条目列表
```bash
cd ~/.inv-knowledge && python3 km_lint.py 2>&1 | python3 -c "
import json, sys
data = json.load(sys.stdin)
for e in data.get('isolated_entries', []):
    print(f\"- {e['path']}: {e['title']}\")
"
```

### 步骤 2：为每个孤立条目搜索相关条目
- 读取所有条目的 frontmatter（title, tags）
- 基于标签重叠和标题关键词计算相似度
- 为每个孤立条目找出 top 3 最相关的已有条目

### 步骤 3：批量写入关联
- 在孤立条目的 `## 关联` 段添加指向相关条目的 markdown 链接
- 格式：`- [标题](实际 slug 文件名) — 关联原因`（使用真实 slug 文件名）
- 关联原因需具体说明为什么相关（同机构/同主题/同行业等）

### 步骤 4：清理死链
- 运行 `km_lint --fix` 自动清理指向不存在文件的死链
- 若仍有死链，手动检查关联段中的 `[](path)` 路径是否对应真实文件名

### 步骤 5：验证修复
- 再次运行 `km_lint --fix`，确认 `no_cross_refs: 0`
- 检查 `summary` 中其他问题项是否归零

## 常见 lint 问题速查

| 问题 | 原因 | 修复方式 |
|------|------|---------|
| `no_cross_refs` | 条目无交叉引用 | LLM 按上述工作流批量建关联 |
| `dead_links` | 关联指向的文件不存在 | `--fix` 自动清理；检查 slugify 后的文件名是否一致 |
| `empty_key_points` | `## 关键要点` 下无有效列表项 | 确保使用 `1. **标题**` 或 `- 内容` 格式 |
| `okf_errors` | frontmatter 缺少必需字段 | 补全 type/title/description/timestamp/resource/source_type |

| 检查项 | --fix |
|--------|:---:|
| OKF 合规（resource, source_type 等） | ❌ |
| 死链 / 孤立文件 / 图谱过期 | ✅ |
| 缺失 resource / 重建 index.md / 重建 by-tag/ | ✅ |
| 交叉引用密度（只读检查，关联由 LLM 导入时建立） | ❌ |
| 资源配对 / URL 可达 / 重复检测 / 标签治理 / 时效预警 / 内容质量 | ❌ |

## 常见异常处理

| 场景 | 表现 | 处理 |
|------|------|------|
| 知识库不存在 | `请先运行 km_init.py` | LLM 用 bash：`git clone <INV_KNOWLEDGE_REPO_URL> ~/.inv-knowledge` + `mkdir -p entries res` |
| km_import res: 文件不存在 | `# 文件不存在` | 确认路径 |
| km_import res: 缺少 --target | `请指定 --target` | 先读 `res/` 确认已有文件夹 |
| km_import res: PDF 损坏/扫描件 | `跳过无法打开` / 文本为空 | 跳过或告知用户 |
| km_import res: 目标已存在 | MD5 相同→跳过，不同→加后缀 | 自动处理 |
| 抓取 URL 失败 | firecrawl_scrape MCP 返回空/反爬 | LLM 换 `waitFor`/`proxy`，或手动粘贴正文 store |
| LLM 搜索无结果 | grep/index 无命中 | 缩短关键词；读 `entries/by-tag/{tag}.md` 浏览 |
| km_import store: 重复入库 | `疑似重复入库` | 告知用户，如需更新先删旧条目 |
| km_import store: 内容太短 | `content 过短` | 检查输入是否截断 |
| km_import store: --description 自动提取错误 | 从 frontmatter 误取 `title: xxx` | 始终显式传 `--description`，不依赖 `_auto_description` |
| km_import store: 双重 frontmatter / shell `$` 转义 / 被安全拦截 | 写入失败或格式错乱 | 避免 `--content-file`；description 含 `$` 用单引号；被拦截时 `write_file` 直写 + 主会话 `km_lint --fix` |
| subagent 倾倒 PDF 原文 | 条目 >200 行，含 `--- page N ---` 标记 | 删除后重新派发，明确“25-50 行 MAX，禁止 PDF 原文” |
| 标签含斜杠(`I/O`) | `by-tag/I/O-2026.md` 创建失败 | tags 禁止使用 `/ \ : * ? " < > |`，改成 `IO-2026` |
| 条目 type 不合法 | `type: Research Report` | OKF 合法 type 仅 5 种：`Analysis/Article/Reference/Synthesis/Note` |
| 同标的研报大量重复 | 每家券商一条独立条目导致膨胀 | 合并为“标的+主题”综合条目 |
| git push 超时/失败 | 超时或失败提示 | 文件已写入本地，不阻塞流程，稍后手动 push |
| 路径含空格 | macOS 下载常见 | shell 用引号包裹或用 `\` 转义 |

## km_lint --fix 自动化修复内容

`km_lint.py --fix --skip-url-check` 自动处理：
- 清除死链、修复孤立文件、补全缺失 resource
- 重建 `entries/index.md` 和 `entries/by-tag/` 标签索引
- 重建知识图谱
- 修复后再次 lint 验证

> 交叉关联**不再自动写入**（确定性词袋规则已移除，质量差）。关联由 LLM 导入时手动建立，`km_lint` 仅做密度检查（`no_cross_refs` 计数）。导入 5-10 条后跑一次 `--fix` 重建索引/标签/图谱即可。
