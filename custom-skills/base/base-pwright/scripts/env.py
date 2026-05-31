"""项目根 .env 文件加载。

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "base" / "base-pwright" / "scripts"))
  from env import load_dotenv
  load_dotenv()
"""

import os
from pathlib import Path


def _find_project_root() -> Path:
    """从当前文件向上查找包含 .env 的项目根目录。"""
    p = Path.cwd().resolve()
    for _ in range(6):
        if (p / ".env").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd().resolve()


def load_dotenv(env_file: Path | None = None) -> None:
    """加载 .env 文件到 os.environ。已存在的环境变量不会被覆盖。"""
    if env_file is None:
        env_file = _find_project_root() / ".env"

    if not env_file.exists():
        return

    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = val
