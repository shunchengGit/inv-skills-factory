# Assist Manager 工作流参考

> 注意: TODO 管理已迁移至 `todo` 技能；面试管理已迁移至 `interview` 技能。

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

## 文档命名规范

- 需求文档：`需求/<功能名>_需求文档.md`
- 汇报材料：`团队/<主题>_汇报.md`
- 月总结：`团队/2026年X月总结.md`

## 目录维护规则

- **团队/**: 过期汇报材料（超过 6 个月）考虑归档
