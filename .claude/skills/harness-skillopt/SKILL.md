---
name: harness-skillopt
description: 使用 SkillOpt 框架对技能进行优化评估，自动改进 SKILL.md
---

当用户要求优化/评估技能或为技能生成评估环境时，调用脚本执行。

## 触发条件

- 用户要求优化某个技能（"优化 dd-knowledge"、"跑一下技能评估"）
- 用户要求为技能生成 eval/ 目录（"给 dd-git-workflow 生成评估环境"）
- 用户要求评估技能质量或准确率

## 流程一：生成 eval/

当技能尚无 `eval/` 目录时，先生成评估环境脚手架：

1. **确认目标技能**：获取技能路径
2. **选择评估器类型**：
   - `command_match`（默认）— CLI 命令类技能，严格 5 维度匹配（脚本路径 1pt + URL 精确 1pt + 必需标志 1pt + 无多余标志 0.5pt + 参数值精确 1.5pt = 5pt，em >= 4.5）
   - `json_schema` — 结构化 JSON 输出技能
   - `contains_all` — 检查清单/评审类技能，检查输出是否包含所有要点
   - `exact_match` — 确定性生成技能，完全字符串匹配
3. **生成脚手架**：调用 `generate_eval.py`
4. **提示后续步骤**：告知用户需完善 evaluator、编写训练数据

```bash
GEN="python3 $(dirname "$0")/scripts/generate_eval.py"

# 生成 eval 脚手架（默认 command_match 评估器）
$GEN --skill harnesses/common/skills/dd-knowledge

# 指定评估器类型
$GEN --skill harnesses/common/skills/dd-git-workflow --eval-type contains_all

# 强制覆盖已有 eval/
$GEN --skill harnesses/common/skills/dd-knowledge --force

# 预览
$GEN --skill harnesses/common/skills/dd-knowledge --dry-run
```

生成后用户需手动：
1. 完善 `eval/evaluator.py` 中的评估逻辑（或保持严格默认模板）
2. 在 `eval/dataset/generate_training_data.py` 中编写训练数据（含 hard 陷阱题，id 以 `hard-` 开头）
3. 运行 `generate_training_data.py` 生成 items.json

### 严格评估建议

`command_match` 默认模板已包含 5 维度严格评估，确保优化有足够空间：

| 维度 | 分值 | 说明 |
|------|------|------|
| 脚本路径 | 1pt | 命令中包含正确脚本名 |
| URL 精确匹配 | 1pt | URL 值（normalize 后）完全一致 |
| 必需标志齐全 | 1pt | 所有 expected flags 都出现在 predicted 中 |
| 无多余标志 | 0.5pt | 没有不在 expected 中的 flag |
| 参数值精确 | 1.5pt | --timeout 90 写成 90 而非 120；--wait-ms 10000 不能写成 1000 |

em 阈值：score >= 4.5/5 才算 hard=1。数值参数容错 ±10% 得半分；choice 参数值合法但不匹配得 0.3 分。

### hard 陷阱题设计

训练数据中应包含 `hard-` 前缀的陷阱题，确保 test/val 有区分度。分层拆分会将 hard 题均匀分配到 train/val/test。

设计方向：
- **语义陷阱**：用户说"不需要登录" = `--no-ensure-login`，不是不加标志
- **默认值陷阱**：用户说"无头模式" = 默认行为，不加 `--headed`
- **单位转换**：用户说"等 3 秒" = `--wait-ms 3000`，不是 `--timeout 3`
- **易混淆参数**：`--manual-wait-s`（登录前等待）vs `--login-wait-s`（登录后等待）；`--save-storage`（保存登录态）vs `--storage-state`（指定登录态文件）
- **隐含环境**：用户说"Docker/CI" = 必须加 `--no-ensure-login`

### 流程一(B)：LLM 自动生成训练数据

当技能已有 `eval/` 脚手架但数据集不足时，可用 LLM 自动生成多样化的训练数据。借鉴 wxa-skills-eval 的 entity_pool → gen_intent 思路：

1. **通用实体提取**（无 LLM）：解析 SKILL.md 的命令表/参数空间/任务类型/约束规则
2. **批量 LLM 生成**：每批 10-15 条，并行覆盖所有任务类型
3. **验证去重**：自动校验字段完整性、去重、ID 归一化
4. **拆分保存**：train/val/test 写入 `eval/dataset/`

```bash
AUTO="python3 $(dirname "$0")/scripts/auto_generate_dataset.py"

# 生成 60 条测试用例（自动适配技能类型）
$AUTO --skill harnesses/common/skills/dd-knowledge

# 指定数量和批次大小
$AUTO --skill harnesses/common/skills/dd-knowledge --num-items 40 --batch-size 10

# 预览提取的实体维度（--dry-run 不调 LLM）
$AUTO --skill harnesses/common/skills/dd-knowledge --dry-run

# 追加到已有数据集
$AUTO --skill harnesses/common/skills/dd-knowledge --resume
```

**通用设计**：不绑定任何特定技能。从 SKILL.md 中自动提取：
- 命令接口（markdown 表格 / 代码块 / 内联代码）
- 任务类型（路由表 / "何时使用" / 命令分类）
- 约束规则（编号列表 / NEVER 段 / 强制限制）

适用 `dd-knowledge`、`dd-git-workflow`、`dd-prd-claw` 等任何结构化 SKILL.md。

## 流程二：执行优化

当技能已有 `eval/` 目录时，执行 SkillOpt 训练：

1. **确认目标技能**：获取技能路径
2. **前置检查**：`eval/adapter.py` 存在、SkillOpt 子仓库就绪
3. **执行优化**：调用 `optimize_skill.py`
4. **报告结果**：输出优化摘要（baseline vs best 准确率、训练步数、耗时）
5. **确认变更**：告知用户 SKILL.md 已被直接替换，`_meta.json` 已更新

```bash
SKOPT="python3 $(dirname "$0")/scripts/optimize_skill.py"

# 优化技能
$SKOPT --skill harnesses/common/skills/dd-knowledge

# 仅评估当前 SKILL.md，不训练（快速迭代/CI 验证）
$SKOPT --skill harnesses/common/skills/dd-knowledge --eval-only

# 指定评估 split（test/val/train/all，默认 test）
$SKOPT --skill harnesses/common/skills/dd-knowledge --eval-only --split val

# 预览（不执行）
$SKOPT --skill harnesses/common/skills/dd-knowledge --dry-run
$SKOPT --skill harnesses/common/skills/dd-knowledge --eval-only --dry-run

# 覆盖训练参数
$SKOPT --skill harnesses/common/skills/dd-knowledge --cfg-options num_epochs=2 train.batch_size=20
```

`--eval-only` 输出：
- 总体 hard / soft 准确率
- 按 task_type 拆分的 hard / soft（识别哪类任务掉点）
- 单条 results.jsonl（在 `SkillOpt/outputs/eval_<skill>_<ts>/`）

## 约束

- 只优化含 `eval/` 目录的技能，无评估环境的技能不可优化
- 优化完成后 SKILL.md 被直接替换，无需人工审核
- SkillOpt 输出保存在 `SkillOpt/outputs/` 下，不提交 git
- 一次只优化一个技能
