---
name: base-skill-loader
description: 当开始任何对话时加载，建立如何发现和调用自定义技能的规则，要求在任何响应前先检查是否有相关技能适用
---

<SUBAGENT-STOP>
如果被派遣为子代理执行特定任务，跳过此技能。
</SUBAGENT-STOP>

<EXTREMELY-IMPORTANT>
如果你认为有哪怕 1% 的可能性某个技能适用于当前任务，你必须立即调用该技能。

如果技能适用于你的任务，你没有选择，必须使用它。

这是不可协商的，不是可选的，你不能用理性化来逃避。
</EXTREMELY-IMPORTANT>

## 指令优先级

自定义技能覆盖默认的系统提示行为，但**用户指令始终优先**：

1. **用户显式指令**（系统指令文件、直接请求）—— 最高优先级
2. **自定义技能** —— 覆盖默认行为
3. **默认系统提示** —— 最低优先级

如果用户说"不要用某个技能"，即使该技能适用，也遵循用户指令。

## 技能发现规则

**在做出任何响应或采取行动前，先调用相关技能。**

即使只有 1% 的可能性某个技能适用，也应该调用它。如果调用后发现不适用，可以忽略。

```
用户消息 → "是否有技能可能适用？" → 是 → 读取该技能的 SKILL.md
              ↓ 否
         直接响应
```

## 技能索引

部署后所有技能在同一目录下，按名称直接调用。

| 技能 | 触发场景 |
|------|---------|
| **gen-daily-planner** | 安排日程、整合日历和待办、每日/每周计划 |
| **gen-dingtalk** | 操作钉钉（消息、日历、待办、审批、考勤、文档等） |
| **gen-dingtalk-personal-daily** | 在个人钉钉文档中更新每日工作日志 |
| **gen-dingtalk-group-report** | 按月分析钉钉群聊消息并生成报告 |
| **gen-dingtalk-personal-weekly-mail** | 从钉钉周报生成邮件草稿存入企业微信邮箱 |
| **gen-dingtalk-team-weekly-review** | 从钉钉知识库读取并总结团队周报 |
| **gen-interviewer** | 生成面试题、管理候选人、记录面试反馈 |
| **gen-knowledge-curator** | 收集/整理/检索知识、网页采集、LLM总结 |
| **gen-mail-agent** | 发送/查看/管理邮件、SMTP/IMAP操作 |
| **gen-todo-tracker** | 查看/添加/完成待办任务、任务列表管理 |
| **inv-stock-data** | 查询股票/ETF数据（A股、港股、美股） |
| **inv-web-crawler** | 搜索网页、抓取页面数据 |
| **inv-valuation-engine** | 评估股票估值、判断低估/高估 |
| **inv-qarp-strategy** | QARP策略选股、买卖决策 |
| **inv-porter-five-forces** | 行业竞争格局分析、企业护城河评估 |
| **inv-research-analyzer** | 分析券商研报PDF |
| **inv-tencent-indicators** | 追踪腾讯前置指标 |
| **inv-fuyao-indicators** | 追踪福耀玻璃前置指标 |

## 本地数据优先

涉及公司、行业、主题等领域的查询或分析时，**先通过相关技能检查本地已有的数据**（`inv-research-analyzer`、`gen-knowledge-curator`），确认是否已存在相关资料，再决定是否需要外部搜索。不要跳过本地直接查外部。

## 技能优先级

当多个技能可能适用时，按以下顺序：

1. **流程技能优先**（gen-daily-planner、gen-todo-tracker）— 决定 HOW
2. **数据技能其次**（inv-stock-data、inv-web-crawler）— 获取信息
3. **分析技能最后**（inv-valuation-engine、inv-porter-five-forces）— 分析决策

"查一下腾讯股票" → inv-stock-data 先获取数据，再分析
"安排今天的工作" → gen-daily-planner 整合日历和待办

## 防理性化清单

| 错误想法 | 纠正 |
|---------|------|
| "这只是个简单问题，不需要技能" | 简单问题也需要正确的工具 |
| "我直接做更快" | 无序行动浪费时间，技能保证质量 |
| "我记得这个技能怎么用" | 技能会演进，读当前版本 |
| "这个不需要技能" | 如果技能存在且场景匹配，就用它 |

## 技能调用规范

### 调用方式

技能目录已通过软链接部署到 `~/.<agent>/skills/`。根据用户意图匹配技能名称，读取对应目录下的 `SKILL.md` 文件获取指令。

### 调用时机

**必须调用：**
- 用户提到技能相关功能（"查一下股票"、"安排日程"）
- 任务涉及技能覆盖领域（数据分析、邮件管理、知识整理）
- 不确定如何处理时（技能可能提供指导）

**可选调用：**
- 纯闲聊对话
- 明确的技能无关请求

### 调用后处理

1. **加载技能** → 读取 `SKILL.md` 内容
2. **遵循指令** → 严格按照技能文档执行
3. **报告状态** → "正在使用 [skill-name] 技能来处理..."

## 技能依赖关系

```
inv-stock-data（数据层）────────────────────────────┐
  ↑                                                │
  ├── inv-valuation-engine（估值引擎）              │
  │     ↑                                          │
  │     └── inv-qarp-strategy（操作决策）           │
  ├── inv-porter-five-forces（五力分析）            │
  └── (其他技能通过 CLI 子进程调用)                  │

inv-tencent-indicators / inv-fuyao-indicators（前置指标，独立脚本）
inv-research-analyzer（研报分析，独立脚本）

gen-dingtalk（钉钉底层能力）────────────────────────┐
  ↑                                                │
  ├── gen-dingtalk-personal-daily（个人工作日志）    │
  ├── gen-dingtalk-group-report（群聊分析报告）     │
  ├── gen-dingtalk-personal-weekly-mail（周报邮件） │
  └── gen-dingtalk-team-weekly-review（周报总结）   │
```

## 用户指令

用户指令说 WHAT，不是 HOW。"分析一下腾讯"不代表跳过 inv-stock-data 技能，"安排今天"不代表跳过 gen-daily-planner 技能。

**指令 ≠ 跳过技能。**
