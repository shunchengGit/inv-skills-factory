---
name: assist
description: >-
  管理 Assist 工作知识库和个人日程。
  当用户说"我今天要做什么""帮我安排日程""生成日报/周报""整理本周工作""看看待办""添加一个任务""标记完成""归档任务""今天有什么会""客户端周会""面试题怎么出""列出候选人""给XX出面试题""记录面试反馈""候选人评估""抓取这篇文章""整理文章""待消化文章""产品需求怎么写""团队汇报材料""AI学习资料放哪""文章抓取""我的工作目录"时，使用本技能。
  Capabilities: TODO tracking, daily/weekly reports, interview question generation, candidate management, article scraping and summarization, document generation, schedule management.
metadata:
  openclaw:
    emoji: 📋
---

# Assist Manager

管理 `/Users/chengshun/Assist` 工作知识库。

## 目录结构

```
Assist/
├── TODO/           # 每日待办 + 总任务清单
├── 团队/           # 汇报材料、技术方案
├── 需求/           # 产品需求文档
├── 面试/           # 候选人简历 + 面试题
└── AI学习/         # AI 工程化学习资料

技能内部 .claw/raw/  # 抓取中转（临时）
```

## 核心能力

### 1. TODO 管理

**读取今日待办：**
```bash
python3 scripts/todo.py today
```

**添加任务：**
```bash
python3 scripts/todo.py add "任务内容" --priority high
```

**完成任务：**
```bash
python3 scripts/todo.py done "任务关键词"
```

**归档已完成：**
```bash
python3 scripts/todo.py archive
```

### 2. 面试管理

**列出候选人：**
```bash
python3 scripts/interview.py list
```

**生成面试题：**
```bash
python3 scripts/interview.py generate <候选人名> --level senior
python3 scripts/interview.py generate <候选人名> --level mid  # 默认
```

**记录面试反馈：**
```bash
python3 scripts/interview.py feedback <候选人名> --score 45 --rating A
```

### 3. 文章总结存储

**诚实声明：** `save` 命令不会 fallback。Playwright 抓不到就直说失败。

```bash
# 从 URL 抓取（需要 Playwright）
python3 scripts/article.py save <URL> --tags "RN,架构" --note "参考"
```
- 成功：生成草稿 → 状态 📝 待总结
- 失败：**直说失败**，不导入任何已有内容

**安装 Playwright（一次性）：**
```bash
pip3 install playwright
playwright install chromium
```

```bash
# 列出待总结
python3 scripts/article.py list-pending

# 标记已总结
python3 scripts/article.py mark-summarized <文件名>

# 查看索引统计
python3 scripts/article.py index
```

**工作流：**
1. `save <URL>` → Playwright 抓取 → 生成草稿（状态 📝 待总结）
2. 读取草稿 → 进行 AI 总结
3. `mark-summarized` → 标记为 ✅ 已总结

### 4. 文档生成

**生成日报：**
```bash
python3 scripts/docgen.py daily
python3 scripts/docgen.py daily --date 2026-05-16
```

**生成周报：**
```bash
python3 scripts/docgen.py weekly
python3 scripts/docgen.py weekly --date 2026-05-16
```

**整理待消化文章：**
```bash
python3 scripts/docgen.py digest --limit 5
```

## 工作流

### 每日启动
1. 读取今日 TODO（`todo.py today`）
2. 如无当日文件 → 按「每日固定 + 每周固定 + TODO规则」生成日程
3. 检查高优任务进展，回复用户今日计划

### 每周五 09:00 整理周报
1. 归档已完成任务（`todo.py archive`）
2. 生成周报草稿（`docgen.py weekly`）
3. 提醒未消化收藏

### 招聘流程
1. 收到简历 → 放入 `面试/resume/`
2. 生成面试题 → 存为 `面试题_<姓名>.md`
3. 面试后 → 记录反馈
4. 归档 → 移动到 `面试/archived/`

## 日程公约

### 每日固定（4 项）

| 事项 | 时间 |
|------|------|
| 招聘简历获取 | 13:30-14:00 |
| 产品体验和竞品体验 | 14:00-14:30 |
| AI 研究学习 | 14:30-15:00 |
| 今日总结 | 18:30-19:00 |

### 每周固定（7 项）

| 事项 | 时间 | 频率 | 类型 |
|------|------|------|------|
| APM 数据观察 | 09:00-10:00 | 周二 | 工作 |
| 业务数据观察 | 10:00-11:00 | 周二 | 工作 |
| 周会 | 10:00-10:30 | 周一、三 | 会议 |
| 产品需求 Review | 09:00-10:30 | 周四 | 工作 |
| 客户端周会 | 17:00-18:00 | 周四 | 会议 |
| 整理周报 | 09:00-10:00 | 周五 | 工作 |
| 技术部周会 | 11:00-12:00 | 周五 | 会议 |

**一周节奏：**

| 周一 | 周二 | 周三 | 周四 | 周五 |
|------|------|------|------|------|
| 10:00 周会 | 09:00 APM数据 | 10:00 周会 | 09:00 产品需求Review | 09:00 整理周报 |
| | 10:00 业务数据 | | 17:00 客户端周会 | 11:00 技术部周会 |

### TODO 规则

1. 每天最多 2 件 TODO（每日固定项不算 TODO）
2. 每日固定 + TODO 自动纳入日报"今日计划"
3. 当日 TODO 不足 2 件时，自动从「重要不紧急」补充至 2 件
4. 已固化为每日/每周代办的事项，不在「重要不紧急」中重复出现
5. 固定会议优先占位，日程不得与其冲突

### 过滤规则

- 日历中 `[提醒]` 前缀的条目不是工作任务，跳过
- TB 任务更新类日历项不算工作任务
- 火星基地、战争学院、幻想学院等是会议室名称，仅用于定位会议地点

## 评估框架

候选人按年限分级评估：
- **Senior (10+年):** 学习能力 + 毅力（2维度，50/50）
- **Mid (2-3年):** 智力 + 学习能力 + 毅力（3维度，35/35/30）

评分：每题1-5分，总分60分
- A (45-60): 强烈推荐
- B (36-44): 推荐
- C (27-35): 待定
- D (<27): 不推荐

## 依赖

- Python 3.8+
- TODO/面试/文档：标准库 only，无第三方依赖
- 文章抓取（可选）：需 Playwright (`pip3 install playwright && playwright install chromium`)，脚本已内置

## 参考

- 详细工作流见 [references/workflow.md](references/workflow.md)
