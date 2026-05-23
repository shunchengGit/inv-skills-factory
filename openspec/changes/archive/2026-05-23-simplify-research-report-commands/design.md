## Context

`research_pdf.py` 当前 6 个子命令。删除零使用的 `inspect`/`dedup`，`index` 合并到 `list`，过期清理融入 `organize`。

## Goals / Non-Goals

**Goals:**
- 删除 `inspect`、`dedup`、`lint` 独立子命令
- `list` 索引缺失时自动建
- `organize` 末尾自动：清理过期 → git add -A → git commit → git push

**Non-Goals:**
- 不改动 `extract` 行为

## Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 过期清理时机 | organize 归档完成后 | 集成到工作流，少一个步骤 |
| 清理参数 | 内置在 organize 中，无独立开关 | 每次归档自动清理，保持库整洁 |
| Git 操作 | `git add -A && git commit -m "..." && git push` | 研报库本身就是 git 仓库 |
| 行业保留期 | 12 个月 | 行业趋势变化慢 |
| 个股保留期 | 6 个月 | 估值/盈利预测更新快 |

### 日期与类型判断：LLM 负责

不写正则。脚本列举研报库所有 PDF 及其文件夹路径，输出 JSON 列表。Claude（LLM）逐条判断：从文件名提取日期、根据文件夹名判断行业/个股、计算是否过期。脚本根据 Claude 的判定结果执行删除。

```
优点:
  - 文件名格式不受限（Apr-2026-report.pdf、report_final_20260423 都能懂）
  - 行业/个股分类可处理例外（目录名不匹配时 LLM 可根据内容常识补充）
  - 零维护成本（新增格式无需改代码）
```

### 日期与类型判断：Agent 负责

不写正则。脚本列举研报库所有 PDF 及其文件夹路径，输出 JSON 列表。Agent（Claude / OpenClaw / Hermes / WorkBuddy 等）逐条判断：从任意文件名提取日期、根据文件夹名判断行业/个股、计算是否过期。脚本根据判定结果执行删除。

```
organize --execute
  │
  ├── [脚本]  1. 扫描 Downloads → 归档（移动+去重）
  ├── [脚本]  2. 列出研报库所有 PDF → 输出 JSON: [{path, folder}, ...]
  ├── [Agent] 3. 逐条判断：提取日期 → 行业/个股 → 是否过期
  ├── [脚本]  4. 删除标记为过期的文件
  ├── [脚本]  5. 重建索引
  └── [脚本]  6. git add -A && git commit && git push
```

## organize 新流程

```
organize --source ~/Downloads --root ~/股票研报 --execute
  │
  ├── 1. 扫描来源目录 PDF
  ├── 2. 识别标的 → 归档到对应文件夹（已有去重逻辑保持不变）
  ├── 3. 汇总归档结果
  ├── 4. 清理过期研报（行业>12月 / 个股>6月）
  ├── 5. 重建索引（research-index.json）
  ├── 6. git add -A && git commit && git push
  └── 7. 输出完整汇总
```

## Post-Change Commands

```
前: organize / list / extract / index / inspect / dedup  (6个)
后: organize / list / extract                            (3个)
```
