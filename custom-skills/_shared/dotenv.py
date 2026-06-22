"""加载项目根 .env 文件到 os.environ。

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "_shared"))
  from dotenv import load
  load()
"""

import os
from pathlib import Path


def load() -> None:
    """加载 SkillsStore/.env，已存在的环境变量不覆盖。"""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, val)
