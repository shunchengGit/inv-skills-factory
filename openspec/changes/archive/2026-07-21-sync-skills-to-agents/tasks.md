## 1. 目录与配置

- [x] 1.1 创建仓库根目录 `scripts/` 文件夹
- [x] 1.2 创建 `scripts/agent_targets.json` 示例配置文件

## 2. 同步脚本核心

- [x] 2.1 实现配置读取：解析 `agent_targets.json`，展开 `~`，筛选 `enabled: true`
- [x] 2.2 实现技能发现：扫描 `custom-skills/`，筛选含 `SKILL.md` 的子目录
- [x] 2.3 实现同步逻辑：对每个 Agent × 技能组合，执行软链接创建/更新/跳过/重命名
- [x] 2.4 实现 dry-run 模式：`--dry-run` 参数，仅输出预览不执行变更
- [x] 2.5 实现操作日志与汇总输出

## 3. 验证

- [x] 3.1 实际运行脚本验证 Claude Desktop 技能目录同步
