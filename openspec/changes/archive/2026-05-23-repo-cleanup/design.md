# Design: repo-cleanup

## Approach
纯文件清理，无架构影响。

## Changes
1. **新建** `.gitignore` — 标准 Python/macOS/git 排除规则
2. **删除** 垃圾文件/目录 — `.venv`、`.DS_Store`、`__pycache__`
