# Assist Manager 工作流参考

> 注意: TODO 管理已迁移至 `todo` 独立技能；文章抓取/消化已删除。

## 周报生成

```bash
python3 scripts/docgen.py weekly
python3 scripts/docgen.py weekly --date 2026-05-16
```

## 日报生成

```bash
python3 scripts/docgen.py daily
python3 scripts/docgen.py daily --date 2026-05-16
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

## 文档命名规范

- 需求文档：`需求/<功能名>_需求文档.md`
- 汇报材料：`团队/<主题>_汇报.md`
- 月总结：`团队/2026年X月总结.md`
- 面试题：`面试/resume/面试题_<姓名>.md`

## 目录维护规则

1. **面试/resume/**: 已归档候选人移动到 `面试/archived/`
2. **团队/**: 过期汇报材料（超过 6 个月）考虑归档
