# Design: meta-json-standardize

## 统一 Schema

```json
{
  "name": "<skill-name>",
  "version": "<semver>",
  "dependencies": ["<dep-skill-name>"],
  "derivedFrom": "<source-skill-name>"
}
```

- `name`: skill 标识名
- `version`: 语义化版本号（与 SKILL.md frontmatter 一致）
- `dependencies`: 依赖的 skill 列表（可选，默认为空数组）
- `derivedFrom`: 来源 skill（可选，默认为 null）

## 变更清单

| Skill | 操作 |
|---|---|
| cs-stock | 从 schema A 转换 |
| fuyao-leading-indicators | 从 schema A 转换 |
| porter-five-forces-analysis | 保持 schema B，移除 description |
| quality-growth-qarp | 新建 |
| stock-research-report-analysis | 版本 1.5.0 → 1.6.0 |
| tencent-leading-indicators | 版本 1.0.0 → 1.1.0 |
| value-investing-valuation | 保持 schema B，移除 description |
