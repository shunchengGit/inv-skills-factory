# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库定位

这是 Skills 的源码与部署仓库，不是单体应用。`custom-skills/` 是业务技能的事实来源；部署脚本将技能软链接到 Hermes / WorkBuddy，因此已部署技能的源文件修改会立即生效。

仓库没有根级 `pyproject.toml`、锁文件、统一安装流程或 build 命令。大多数可执行脚本使用 PEP 723 内联依赖并通过 `uv run` 启动，不要假设可以运行 `uv sync`。

## 验证与测试

修改任何业务技能（`SKILL.md`、脚本或 references）后运行仓库级 linter：

```bash
python3 .claude/skills/skill-linter/scripts/lint_skills.py
```

linter 检查 frontmatter、目录命名、文档长度、引用深度、路径、软链接兼容性以及已部署入口脚本的 `--help`；它不是业务测试套件。入口运行检查依赖 `~/.hermes/skills/inv-skills/` 中已有部署，未部署时会跳过部分检查。

目前唯一的自动化单元测试位于 `inv-knowledge-curator`，使用标准库 `unittest`。其 `requirements.txt` 未包含源码实际需要的 PyYAML，因此测试命令需显式补齐依赖：

```bash
# 运行该技能的全部测试
uv run --with pyyaml --with pymupdf --with requests \
  python -m unittest discover \
  -s custom-skills/inv-knowledge-curator/tests -v

# 运行一个测试方法
uv run --with pyyaml --with pymupdf --with requests \
  python custom-skills/inv-knowledge-curator/tests/test_high_priority.py \
  TempKnowledgeTest.test_frontmatter_special_characters_round_trip -v
```

其他技能没有统一测试入口。验证具体脚本时先阅读对应 `SKILL.md`，再用 `uv run` 执行；例如：

```bash
uv run custom-skills/inv-stock-data/scripts/cs_stock_info.py snapshot 600519 --output json
uv run custom-skills/inv-valuation-engine/scripts/valuation_snapshot.py AAPL --output json
```

网络型命令可能依赖代理或外部服务，不能代替确定性测试。

## 部署

部署目标由 `.claude/skills/skill-deployer/scripts/deploy.json` 定义，目前为 Hermes 与 WorkBuddy。部署前须在 `.env` 显式设置部署子目录；脚本没有代码层默认值：

```dotenv
DEPLOY_SKILLS_DIR=inv-skills
```

```bash
# 仅显示目标，不修改部署目录
python3 .claude/skills/skill-deployer/scripts/sync.py --agent hermes --dry-run

# 部署一个或全部目标
python3 .claude/skills/skill-deployer/scripts/sync.py --agent hermes
python3 .claude/skills/skill-deployer/scripts/sync.py --agent all
```

修改既有技能内容后通常无需重新部署，只需 lint。首次部署、新增/删除技能、修复链接或变更目标配置后才需 sync。sync 会增删目标目录中的链接；`--force` 还可能替换非空真实目录，使用前先检查目标。即使是 `--list`，缺少 `DEPLOY_SKILLS_DIR` 时也会交互询问并写入 `.env`。

## 高层架构

### 源码、共享层与 harness

- `custom-skills/<skill-name>/`：可部署的业务技能，保持扁平一级结构；目录必须包含 `SKILL.md`。
- `custom-skills/_shared/`：跨技能复用的 dotenv、代理、git 等基础工具，不放投资业务逻辑。
- `.claude/skills/` 与 `.claude/commands/`：维护本仓库的 harness 能力，不作为业务技能部署。
- `openspec/`：变更规格与记录。`openspec/config.yaml` 中仍有旧的分类目录、`_meta.json` 和已删除技能描述；当前目录结构以实际文件系统和 deployer 的扫描逻辑为准。

新增技能目录名使用 `{前缀}-{语义名}` 的 kebab-case 格式，例如 `inv-example`。脚本经软链接执行，因此凡由 `__file__` 推导路径的代码必须先使用 `Path(__file__).resolve()`（或等价的 `abspath`）。

### 投资分析分层

```text
inv-stock-data（唯一行情/财务数据层）
  ├─ inv-valuation-engine（估值计算与评分规则）
  │    └─ inv-qarp-strategy（操作决策）
  ├─ inv-porter-five-forces（行业分析）
  └─ inv-portfolio-tracker（持仓管理）

inv-knowledge-curator（知识库唯一写入边界）
  ├─ inv-valuation-engine
  ├─ inv-qarp-strategy
  ├─ inv-topic-researcher
  └─ inv-porter-five-forces

inv-topic-researcher（信息采集框架）
  └─ inv-portfolio-tracker
```

关键边界：

- `inv-stock-data` 是行情和财务数据的统一入口。上层投资技能不得绕过它直接新增 AkShare / yfinance 调用。
- `inv-valuation-engine/references/scoring-rules.md` 是估值阈值的权威来源；QARP 调用估值引擎，不复制评分规则。
- `inv-portfolio-tracker` 持有组合流程和持仓主数据，但价格仍来自 `inv-stock-data`。
- `inv-hk-ipo-analysis` 是相对独立的港股 IPO 分析流程，不进入上述个股估值链。

### 知识库单写入者模型

`inv-knowledge-curator` 管理外部知识库（默认 `~/.inv-knowledge`）：`entries/` 存放 OKF Markdown 条目，`res/` 存放原始 PDF/资源，索引由确定性脚本重建；检索、关联、统计和综合交给 LLM。

除 curator 自身外，下游技能对知识库只能只读：

- 使用 `/km_search` 检索。
- 使用 `km_import read --file <res/下的PDF路径> --pages edges` 读取原始 PDF；这是无 git push、无索引重建副作用的唯一入口。
- 不得调用 `km_import store`、`km_import res`、`km_lint --fix` 或其他写库操作。研究技能只能提出待入库内容，由 curator 主流程统一写入。

### 数据源与代理边界

美股/港股的 Yahoo 请求需要代理；A 股/ETF 请求应清除代理。不要在同一批处理混用两类市场。连续 Yahoo 请求需限流，优先使用技能提供的合并命令；脚本返回的 `notes` 和 `error` 是数据质量契约，不能忽略或以猜测补齐缺失值。具体规则以 `custom-skills/inv-stock-data/SKILL.md` 为准。

## 环境变量

| 变量 | 用途 | 约定值 |
|---|---|---|
| `INV_KNOWLEDGE_REPO_URL` | 外部知识库 Git 远程 | 默认 `git@github.com:shunchengGit/inv-knowledge.git` |
| `INV_KNOWLEDGE_ROOT` | 外部知识库本地目录 | 默认 `~/.inv-knowledge` |
| `DEPLOY_SKILLS_DIR` | Agent 技能部署子目录 | 须显式配置，通常为 `inv-skills` |

研报已合并到知识库的 `res/`；`INV_REPORT_REPO_URL` 与 `RESEARCH_PDF_ROOT` 是废弃变量。`.env.example` 仍残留这两个旧变量，不应据此恢复双仓库模型。
