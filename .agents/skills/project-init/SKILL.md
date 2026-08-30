---
name: project-init
description: 项目初始化：引导配置 .env 环境变量并拉取 git 仓库。用于新环境搭建、首次克隆项目后、env 配置不完整时。
trigger:
  - 项目初始化
  - 初始化环境
  - 搭建环境
  - 首次配置
  - env 配置
  - 拉取知识库
  - git clone
  - init project
commands:
  - /init_project - 引导配置 .env 并拉取知识库/研报库 git 仓库
---

# project-init：项目初始化

## 核心目标

引导用户完成 Skills 工厂的首次配置：确认/填写 `.env` 变量 → 拉取知识库和研报库 git 仓库。

## 执行流程

### 1. 检查 .env

读取项目根目录的 `.env`。如果不存在，引导用户从 `.env.example` 复制：

```
cp .env.example .env
```

然后逐项检查以下关键变量是否已配置（值为空或仍是注释状态视为未配置）：

| 变量 | 默认值 | 用途 |
|------|--------|------|
| `INV_KNOWLEDGE_REPO_URL` | `git@github.com:shunchengGit/inv-knowledge.git` | 知识库远程仓库 |
| `INV_KNOWLEDGE_ROOT` | `~/.inv-knowledge` | 知识库本地目录 |
| `DEPLOY_SKILLS_DIR` | `inv-skills` | 部署目标子目录名 |

**交互规则**：对每个变量，如果用户已填写（非空、非注释），跳过。如果未填写，询问用户是否使用默认值或输入自定义值。不要一次性列出所有变量让用户填——逐个引导，逐个确认。

### 2. 检查 SSH 连通性

```bash
ssh -T git@github.com 2>&1
```

如果返回 "Permission denied" 而不是 "successfully authenticated"：
- 提示用户配置 SSH key：`ssh-keygen -t ed25519 -C "your_email@example.com"` → 添加到 GitHub
- SSH 不通则后续 clone 会失败，必须先解决

### 3. 拉取知识库

```bash
python3 custom-skills/inv-knowledge-curator/scripts/km_init.py
```

- 成功 → 显示条目统计
- 失败 → 根据错误信息给出提示（SSH key、仓库不存在、网络等）

### 4. 拉取研报库

```bash
python3 .Codex/skills/project-init/scripts/init_report.py
```

- 逻辑与 km_init 相同：先 clone 再 pull，已存在则验证 remote 一致性
- 成功 → 显示 Index.md 统计
- 失败 → 给出提示

### 5. 汇总

初始化完成后输出汇总：

```
✅ 初始化完成
  .env:         已配置 (5/5 变量)
  知识库:       ~/.inv-knowledge (XX 个条目)
  研报库（res/）: ~/.inv-knowledge/res (XX 个文件夹)
  SSH:          OK
```

## 注意事项

- 不要重复配置已有的变量，只处理缺失的
- SSH 不通时不跳过，必须解决后再拉仓库
- 知识库和研报库独立——一个失败不影响另一个
- 已存在的本地目录不会覆盖，只做 git pull
