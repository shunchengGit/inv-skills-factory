# Assist Manager 工作流参考

## 每日工作流（Morning Routine）

1. **读取今日 TODO**
   ```bash
   python3 scripts/todo.py today
   ```

2. **检查高优任务**
   - 查看 `TODO/TODO.md` 的"高优"部分
   - 确认是否有阻塞项

3. **快速整理**
   - 生成日报草稿：`python3 scripts/docgen.py daily`
   - 归档昨日已完成的任务
   - 添加今日新任务

4. **每日必排（雷打不动）**
   - 13:30-14:00 招聘简历获取
   - 14:00-14:30 产品体验和竞品体验
   - 14:30-15:00 AI 研究学习

5. **TODO 约束**
   - 每天最多 2 件 TODO（每日必排不算 TODO）
   - `[提醒]` 前缀、TB 任务更新、会议室名不算工作任务

## 每周工作流（Weekly Review）

1. **生成周报草稿**
   ```bash
   python3 scripts/docgen.py weekly
   ```

2. **整理收藏**
   ```bash
   python3 scripts/docgen.py digest --limit 10
   ```

3. **归档 TODO**
   ```bash
   python3 scripts/todo.py archive
   ```

## 招聘流程

### 收到简历
1. 简历放入 `面试/resume/`
2. 生成面试题：
   ```bash
   python3 scripts/interview.py generate <姓名> --level senior
   python3 scripts/interview.py generate <姓名> --level mid  # 默认
   ```

### 面试后
1. 填写面试题文件中的评分和反馈
2. 或使用命令：
   ```bash
   python3 scripts/interview.py feedback <姓名> --score 45 --rating A
   ```

### 候选人追踪表

| 姓名 | 岗位 | 状态 | 评分 | 评级 | 日期 |
|------|------|------|------|------|------|
| 王斌 | Android | 已面试 | 45 | A | 2026-05-10 |
| ... | ... | ... | ... | ... | ... |

## 文档命名规范

- 需求文档：`需求/<功能名>_需求文档.md`
- 汇报材料：`团队/<主题>_汇报.md`
- 月总结：`团队/2026年X月总结.md`
- 面试题：`面试/resume/面试题_<姓名>.md`

## 目录维护规则

1. **TODO/**: 保留最近 30 天的每日文件，旧文件归档
2. **ddcursor/**: 每月至少消化 5 篇，已消化的移动或标记
3. **面试/resume/**: 已归档候选人移动到 `面试/archived/`
4. **团队/**: 过期汇报材料（超过 6 个月）考虑归档
