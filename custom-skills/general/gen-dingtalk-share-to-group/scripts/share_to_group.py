#!/usr/bin/env python3
"""
Search DingTalk group and send message.

Usage:
    python3 share_to_group.py --keyword "群名关键词" --title "消息标题" --text "消息正文"
    python3 share_to_group.py --group-id "cidxxxxx" --title "消息标题" --text "消息正文" --at-all
"""

import argparse
import json
import subprocess
import sys


def run_dws(args_list):
    """Run dws command with UTF-8 env and return parsed JSON."""
    env = {"LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"}
    result = subprocess.run(
        args_list,
        capture_output=True,
        env={**subprocess.os.environ, **env}
    )
    return json.loads(result.stdout.decode("utf-8"))


def search_group(keyword):
    """Search group by keyword, return list of (name, openConversationId, memberCount)."""
    data = run_dws(["dws", "chat", "search", "--keyword", keyword, "--format", "json"])
    if not data.get("success"):
        return []
    groups = data.get("result", {}).get("groups", [])
    return [
        (g.get("name"), g.get("openConversationId"), g.get("memberCount", 0))
        for g in groups
    ]


def send_message(group_id, title, text, at_all=False):
    """Send message to group."""
    cmd = [
        "dws", "chat", "message", "send",
        "--group", group_id,
        "--title", title,
        "--text", text,
        "--format", "json"
    ]
    if at_all:
        cmd.append("--at-all")
    return run_dws(cmd)


def main():
    parser = argparse.ArgumentParser(description="Search DingTalk group and send message")
    parser.add_argument("--keyword", help="Keyword to search group")
    parser.add_argument("--group-id", help="Direct group openConversationId (skip search)")
    parser.add_argument("--title", required=True, help="Message title")
    parser.add_argument("--text", required=True, help="Message text (Markdown supported)")
    parser.add_argument("--at-all", action="store_true", help="@所有人")
    args = parser.parse_args()

    group_id = args.group_id

    if not group_id:
        if not args.keyword:
            print("Error: --keyword or --group-id required", file=sys.stderr)
            sys.exit(1)
        groups = search_group(args.keyword)
        if not groups:
            print("No group found", file=sys.stderr)
            sys.exit(1)
        print("Found groups:")
        for i, (name, gid, members) in enumerate(groups[:5]):
            print(f"  [{i}] {name} ({members} members) -> {gid}")
        print("Please specify --group-id to send message")
        sys.exit(0)

    result = send_message(group_id, args.title, args.text, args.at_all)
    if result.get("success"):
        print(f"✅ Message sent: {args.title}")
    else:
        print(f"❌ Failed: {result}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
