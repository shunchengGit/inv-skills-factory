# 已知常量与 dws 命令清单

## 已知常量

| 名称 | 值 | 说明 |
|------|----|------|
| 客服问题反馈群 convId | `cidGu2NRRnnLvzO014c19vtVg==` | 客服问题反馈群 |

## dws 命令清单

| 用途 | 命令 |
|------|------|
| 拉取单群消息 | `dws chat message list --group <convId> --time <cursor> --forward=false --limit 50 --format json` |
| 拉取全量消息(短期) | `dws chat message list-all --start <start> --end <end> --cursor <cursor> --limit 50 --format json` |
| 检查 dws 版本 | `dws version --format json` |
| 检查登录状态 | `dws auth status --format json` |
