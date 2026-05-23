## 1. 脚本修改

- [x] 1.1 删除 `cmd_inspect`、`cmd_dedup`、`cmd_lint` 函数及其 argparse subparser
- [x] 1.2 从 argparse 移除 `index` 子命令（保留 `cmd_index` 内部函数）
- [x] 1.3 `cmd_list` — `--use-index` 且索引不存在时自动调用 `cmd_index`
- [x] 1.4 `cmd_organize` 末尾输出文件清单（供 Agent 判断过期），Agent 删除过期后重建索引
- [x] 1.5 `cmd_organize` 末尾增加 git add → commit → push（`--execute` 时，dry-run 跳过）

## 2. 文档与元数据更新

- [x] 2.1 SKILL.md：frontmatter commands 改为 3 个，更新 organize 流程说明
- [x] 2.2 `_meta.json`：commands 同步更新

## 3. 测试更新

- [x] 3.1 `tests/test_research_pdf.py`：更新测试，覆盖新的 3 命令结构
- [x] 3.2 运行全部测试 24/24 通过
