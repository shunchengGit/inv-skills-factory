#!/usr/bin/env python3
"""
Hermes Hook: using-custom-skills
会话开始时注入自定义技能系统上下文
"""

import os
import json

SKILL_FILE = os.path.expanduser(
    "~/.SkillsStore/custom-skills/general/using-custom-skills/SKILL.md"
)


def handle(event_type: str, context: dict) -> dict:
    """会话开始时注入技能系统上下文"""

    skill_content = ""
    if os.path.exists(SKILL_FILE):
        with open(SKILL_FILE, "r", encoding="utf-8") as f:
            skill_content = f.read()

    if not skill_content:
        return {
            "status": "skipped",
            "reason": "SKILL.md not found"
        }

    # 构建注入上下文
    injected_context = f"""你有自定义技能系统可用。在每次对话开始时，先检查是否有技能适用。

{skill_content}
"""

    return {
        "status": "injected",
        "additional_context": injected_context,
        "source": "using-custom-skills-hook"
    }
