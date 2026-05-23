# Proposal: repo-cleanup

## Summary
清理仓库中的垃圾文件，添加 `.gitignore` 防止再次提交。

## Scope
- 新建 `.gitignore`，排除 `.venv/`、`.DS_Store`、`__pycache__/`、`*.pyc`
- 删除 `cs-stock/.venv/` 虚拟环境目录（200+ 文件）
- 删除所有 `.DS_Store` 文件（2 个）
- 删除所有 `__pycache__/` 目录（8 个）
