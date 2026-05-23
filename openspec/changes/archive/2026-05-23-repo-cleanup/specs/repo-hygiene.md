# Spec: repository hygiene

## Requirement
仓库 MUST 排除以下文件/目录，不纳入版本控制：
- `.venv/` — Python 虚拟环境
- `.DS_Store` — macOS 系统文件
- `__pycache__/` — Python 字节码缓存
- `*.pyc` — Python 字节码文件
