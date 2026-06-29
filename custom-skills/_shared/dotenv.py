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
from typing import Optional


def _find_env_file() -> Optional[Path]:
    seen: set[Path] = set()
    starts = [Path.cwd().resolve(), Path(__file__).resolve().parent]

    for start in starts:
        for candidate in [start, *start.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)

            env_file = candidate / ".env"
            if env_file.exists():
                return env_file

    return None


def load() -> None:
    """加载项目根 .env，已存在的环境变量不覆盖。"""
    env_file = _find_env_file()
    if not env_file:
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
