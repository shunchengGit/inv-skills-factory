## ADDED Requirements

### Requirement: 子命令注册仅含 3 个命令

`research_pdf.py` SHALL 仅对外暴露 3 个子命令：`list`、`extract`、`organize`。`inspect`、`dedup`、`lint`、`index` 子命令 SHALL NOT 作为独立 CLI 入口。

#### Scenario: 子命令列表

- **WHEN** 用户运行 `research_pdf.py --help`
- **THEN** 显示的可用子命令仅包含 `list`、`extract`、`organize`

#### Scenario: inspect 被移除

- **WHEN** 用户运行 `research_pdf.py inspect`
- **THEN** 系统 SHALL 输出错误信息并退出，退出码非零

#### Scenario: dedup 被移除

- **WHEN** 用户运行 `research_pdf.py dedup`
- **THEN** 系统 SHALL 输出错误信息并退出，退出码非零

### Requirement: list 自动建索引

`list` 子命令在指定 `--use-index` 且 `research-index.json` 不存在时，SHALL 自动生成索引后再执行查询。

#### Scenario: 首次 list 自动建索引

- **WHEN** 用户运行 `research_pdf.py list --code 0700 --use-index` 且索引文件不存在
- **THEN** 系统 SHALL 自动扫描目录生成索引，然后正常返回查询结果

#### Scenario: 索引已存在时直接查询

- **WHEN** 用户运行 `research_pdf.py list --code 0700 --use-index` 且索引文件已存在
- **THEN** 系统 SHALL 直接使用索引查询，不重新扫描

### Requirement: organize 输出文件清单

`organize --execute` 在归档完成后 SHALL 输出研报库全部 PDF 的文件清单（JSON 格式，含 path/folder/filename），供 Agent 判断过期。

#### Scenario: execute 后输出清单

- **WHEN** 用户运行 `organize --execute`
- **THEN** 系统 SHALL 在归档完成后输出 JSON 格式的文件清单

### Requirement: organize 自动 git 提交

`organize --execute` 在文件清单输出后 SHALL 对研报库执行 `git add -A && git commit && git push`。

#### Scenario: 有变更时提交推送

- **WHEN** 研报库有文件变更
- **THEN** 系统 SHALL 执行 git add/commit/push

#### Scenario: 无变更时跳过

- **WHEN** `git status --porcelain` 无输出
- **THEN** 系统 SHALL 跳过 git 操作，输出"无变更，跳过提交"

#### Scenario: dry-run 不执行 git

- **WHEN** 传入 `--dry-run`
- **THEN** 系统 SHALL NOT 执行任何 git 命令
