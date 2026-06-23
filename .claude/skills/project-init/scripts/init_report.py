#!/usr/bin/env python3
"""初始化研报库：委托给 km_init.py（研报已合并到知识库统一仓库）。

用法:
  uv run .claude/skills/project-init/scripts/init_report.py
"""

import os
import sys
from pathlib import Path

# 现在研报 PDF 存储在知识库仓库的 res/ 子目录中
# 直接委托给 km_init.py
_skills_dir = Path(__file__).resolve().parents[4] / "custom-skills"
_km_init = _skills_dir / "inv-knowledge-curator" / "scripts" / "km_init.py"

if _km_init.exists():
    sys.path.insert(0, str(_km_init.parent))
    sys.path.insert(0, str(_skills_dir / "_shared"))
    from km_init import main
    main()
else:
    import json
    print(json.dumps({
        "success": False,
        "error": "知识库初始化脚本不存在，请确认仓库已正确拉取",
    }, ensure_ascii=False, indent=2))
    sys.exit(1)
