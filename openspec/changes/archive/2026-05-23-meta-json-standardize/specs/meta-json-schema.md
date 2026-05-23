# Spec: _meta.json unified schema

## Schema

每个 skill 的 `_meta.json` MUST 包含以下字段：

```json
{
  "name": "<skill-name>",
  "version": "<semver>",
  "dependencies": ["<optional-dep>"],
  "derivedFrom": null
}
```

- `name` (required) — skill 目录名
- `version` (required) — 语义化版本，MUST 与 SKILL.md version 一致
- `dependencies` (optional) — 依赖的 skill 名称数组，默认 `[]`
- `derivedFrom` (optional) — 衍生来源的 skill 名，默认 `null`
