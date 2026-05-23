## Why

研报技能目前 6 个子命令，其中 `inspect`/`dedup` 零使用，`index` 需要手动调用。研报库缺少过期清理，且归档流程（下载 PDF → 整理入库 → 清理过期 → 提交 git）分散在多个步骤。

## What Changes

- **移除** `inspect`：肉眼即可判断扫描件
- **移除** `dedup`：`organize` 归档时已做去重
- **移除** `lint` 独立子命令，能力融入 `organize`
- **合并** `index` 到 `list`：首次 `list` 自动建索引
- **organize 增强**：归档完成 → 清理过期研报（行业 12 月/个股 6 月）→ `git commit` + `git push` 研报库

## Capabilities

### Modified Capabilities

- `stock-research-report-analysis`: 命令从 6 个精简为 3 个（`list`/`extract`/`organize`）。`organize` 增加过期清理 + git 自动提交推送。

## Impact

- `scripts/research_pdf.py`：删除 `cmd_inspect`/`cmd_dedup`/`cmd_lint`；`cmd_organize` 末尾增加过期清理和 git 提交逻辑
- `SKILL.md`、`_meta.json`、测试文件同步更新
