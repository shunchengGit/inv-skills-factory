#!/usr/bin/env python3
"""
邮件管理脚本 — SMTP/IMAP 直连。

凭据：
  环境变量 TL_MAIL_USER / TL_MAIL_PASS，写入 ~/.zshrc。
  首次运行无环境变量时交互提示输入并自动追加。

默认服务器：
  SMTP: smtp.exmail.qq.com:465 (SSL)
  IMAP: imap.exmail.qq.com:993 (SSL)

用法：
  uv run mail.py send --to xx --subject "Hi" --body "..."
  uv run mail.py list --days 7 --limit 10
  uv run mail.py read --id "123"
  uv run mail.py draft --to xx --subject "Draft" --body "..."
  uv run mail.py delete --id "123"
  uv run mail.py flag --id "123" --seen
  uv run mail.py move --id "123" --to "Sent Messages"
  uv run mail.py folders
"""

import argparse
import imaplib
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timedelta
from email.header import decode_header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

# 加载项目根 .env（已存在的环境变量不覆盖）
_env_file = Path(__file__).resolve().parents[4] / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        if _line.strip() and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))

DEFAULT_SMTP_HOST = "smtp.exmail.qq.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_IMAP_HOST = "imap.exmail.qq.com"
DEFAULT_IMAP_PORT = 993

RECIPIENT_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

# ── zshrc 管理 ──────────────────────────────────────────────

ZSHRC_PATH = Path.home() / ".zshrc"
ENV_USER = "TL_MAIL_USER"
ENV_PASS = "TL_MAIL_PASS"


def ensure_env_in_zshrc():
    """如果 ~/.zshrc 中没有 TL_MAIL_* 变量，交互式提示输入并写入。"""
    existing = ZSHRC_PATH.read_text() if ZSHRC_PATH.exists() else ""
    has_user = f"export {ENV_USER}=" in existing
    has_pass = f"export {ENV_PASS}=" in existing

    if has_user and has_pass:
        return

    print("未检测到邮件凭据配置，请设置以下环境变量：", file=sys.stderr)
    new_lines = []

    if not has_user:
        user = input("  发件邮箱: ").strip()
        new_lines.append(f'export {ENV_USER}="{user}"')

    if not has_pass:
        password = input("  授权码: ").strip()
        new_lines.append(f'export {ENV_PASS}="{password}"')

    if new_lines:
        confirm = input(f"\n将以下内容追加到 ~/.zshrc？\n" + "\n".join(new_lines) + "\n[y/N]: ")
        if confirm.lower() in ("y", "yes"):
            with open(ZSHRC_PATH, "a") as f:
                f.write("\n# mail skill email credentials\n")
                for line in new_lines:
                    f.write(line + "\n")
            print(f"已写入 {ZSHRC_PATH}，请运行 source ~/.zshrc 使其生效", file=sys.stderr)
        else:
            print("已取消。请手动设置 TL_MAIL_USER 和 TL_MAIL_PASS 环境变量后重试。", file=sys.stderr)
            sys.exit(1)


def resolve_credentials():
    user = os.environ.get(ENV_USER)
    password = os.environ.get(ENV_PASS)

    if not user or not password:
        ensure_env_in_zshrc()
        # 重读环境变量（新写入的需要 source 后才能读到）
        user = os.environ.get(ENV_USER)
        password = os.environ.get(ENV_PASS)
        if not user or not password:
            print(
                json.dumps({
                    "success": False,
                    "message": "凭据已写入 ~/.zshrc，请运行 source ~/.zshrc 后重试"
                }),
                file=sys.stderr,
            )
            sys.exit(1)

    return user, password


# ── 工具函数 ─────────────────────────────────────────────────

def parse_recipients(text: Optional[str]) -> list:
    if not text:
        return []
    return RECIPIENT_RE.findall(text)


def decode_str(s):
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def build_message(
    sender: str,
    to: list,
    cc: list,
    bcc: list,
    subject: str,
    body: Optional[str],
    body_html: Optional[str],
    attachments: list,
):
    msg = MIMEMultipart()
    msg["From"] = sender
    if to:
        msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject

    if body_html and body:
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body, "plain", "utf-8"))
        alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)
    elif body_html:
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)
    elif body:
        msg.attach(MIMEText(body, "plain", "utf-8"))

    for filepath in attachments:
        path = Path(filepath)
        if not path.is_file():
            print(json.dumps({"success": False, "message": f"附件不存在: {filepath}"}), file=sys.stderr)
            sys.exit(1)
        part = MIMEApplication(path.read_bytes(), name=path.name)
        part.add_header("Content-Disposition", f"attachment; filename={path.name}")
        msg.attach(part)

    return msg


# ── IMAP 连接 ────────────────────────────────────────────────

def imap_connect(host: str, port: int, user: str, password: str):
    imap = imaplib.IMAP4_SSL(host, port, timeout=30)
    imap.login(user, password)
    return imap


# ── 子命令: send ─────────────────────────────────────────────

def cmd_send(args):
    user, _ = resolve_credentials()

    to = parse_recipients(args.to)
    cc = parse_recipients(args.cc)
    bcc = parse_recipients(args.bcc)

    if not to and not cc and not bcc:
        print(json.dumps({"success": False, "message": "没有有效的收件人地址"}), file=sys.stderr)
        sys.exit(1)

    body = args.body
    body_html = args.body_html
    if args.body_file:
        import pathlib
        body_content = pathlib.Path(args.body_file).read_text(encoding='utf-8')
        if body_html or (body_content.strip().startswith('<!') or body_content.strip().startswith('<')):
            body_html = body_content
        else:
            body = body_content

    msg = build_message(
        sender=user,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=args.subject,
        body=body,
        body_html=body_html,
        attachments=args.attachments,
    )

    all_recipients = (
        parse_recipients(msg["To"])
        + parse_recipients(msg["Cc"])
        + parse_recipients(msg["Bcc"])
    )

    use_tls = args.use_tls or (args.smtp_port == 587 and args.smtp_host != DEFAULT_SMTP_HOST)

    if use_tls:
        smtp = smtplib.SMTP(args.smtp_host, args.smtp_port, timeout=30)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
    else:
        smtp = smtplib.SMTP_SSL(args.smtp_host, args.smtp_port, timeout=30)

    try:
        _, password = resolve_credentials()
        smtp.login(user, password)
        smtp.sendmail(user, all_recipients, msg.as_bytes())
    finally:
        smtp.quit()

    print(json.dumps({
        "success": True,
        "message": "邮件已发送",
        "details": {
            "to": parse_recipients(msg["To"]),
            "cc": parse_recipients(msg["Cc"]),
            "bcc": parse_recipients(msg["Bcc"]),
            "subject": msg["Subject"],
            "attachments": [p.get_filename() for p in msg.iter_attachments() if p.get_filename()],
        },
    }, ensure_ascii=False, indent=2))


# ── 子命令: list ─────────────────────────────────────────────

def cmd_list(args):
    user, password = resolve_credentials()
    imap = imap_connect(args.imap_host, args.imap_port, user, password)
    try:
        imap.select(f'"{args.folder}"' if " " in args.folder else args.folder)

        since = (datetime.now() - timedelta(days=args.days)).strftime("%d-%b-%Y")
        search_criteria = f"(SINCE {since})"
        if args.from_addr:
            search_criteria = f'(SINCE {since} FROM "{args.from_addr}")'

        typ, data = imap.search(None, search_criteria)
        mids = data[0].split()
        if not mids:
            print(json.dumps({"success": True, "folder": args.folder, "count": 0, "messages": []}, ensure_ascii=False))
            return

        mids = mids[-args.limit:]

        messages = []
        for mid in reversed(mids):
            typ, msg_data = imap.fetch(mid, "(FLAGS BODY[HEADER.FIELDS (SUBJECT FROM TO DATE)])")
            flags_str = imap._get_untagged_response("FLAGS") if hasattr(imap, "_get_untagged_response") else ""
            # 从 fetch 结果中解析 flags
            flags = b""
            for item in msg_data:
                if isinstance(item, tuple):
                    flags = item[0]
                    break

            header_text = ""
            for item in msg_data:
                if isinstance(item, tuple) and len(item) > 1:
                    header_text = item[1].decode("utf-8", errors="replace") if isinstance(item[1], bytes) else str(item[1])
                    break

            seen = b"\\Seen" in flags
            flagged = b"\\Flagged" in flags

            # 解析头部字段
            subject = ""
            from_addr = ""
            to_addr = ""
            date = ""
            for line in header_text.split("\r\n"):
                if line.startswith("Subject: ") or line.startswith("SUBJECT: "):
                    subject = decode_str(line.split(": ", 1)[1] if ": " in line else "")
                elif line.startswith("From: ") or line.startswith("FROM: "):
                    from_addr = decode_str(line.split(": ", 1)[1] if ": " in line else "")
                elif line.startswith("To: ") or line.startswith("TO: "):
                    to_addr = decode_str(line.split(": ", 1)[1] if ": " in line else "")
                elif line.startswith("Date: ") or line.startswith("DATE: "):
                    date = line.split(": ", 1)[1] if ": " in line else ""

            messages.append({
                "id": mid.decode() if isinstance(mid, bytes) else str(mid),
                "subject": subject,
                "from": from_addr,
                "to": to_addr,
                "date": date,
                "seen": seen,
                "flagged": flagged,
            })

        print(json.dumps({
            "success": True,
            "folder": args.folder,
            "count": len(messages),
            "messages": messages,
        }, ensure_ascii=False, indent=2))
    finally:
        imap.logout()


# ── 子命令: read ─────────────────────────────────────────────

def cmd_read(args):
    user, password = resolve_credentials()
    imap = imap_connect(args.imap_host, args.imap_port, user, password)
    try:
        imap.select(f'"{args.folder}"' if " " in args.folder else args.folder)
        mid = args.id.encode() if isinstance(args.id, str) else args.id

        typ, msg_data = imap.fetch(mid, "(RFC822)")
        raw = None
        for item in msg_data:
            if isinstance(item, tuple) and len(item) > 1:
                raw = item[1]
                break

        if not raw:
            print(json.dumps({"success": False, "message": "邮件不存在"}, ensure_ascii=False))
            sys.exit(1)

        import email
        msg = email.message_from_bytes(raw, policy=email.policy.default)
        subject = str(msg.get("Subject", ""))
        from_addr = str(msg.get("From", ""))
        to_addr = str(msg.get("To", ""))
        date = str(msg.get("Date", ""))
        cc = str(msg.get("Cc", ""))
        bcc = str(msg.get("Bcc", ""))

        text_body = ""
        html_body = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                disposition = part.get("Content-Disposition", "")
                if "attachment" in disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append(decode_str(filename))
                elif ct == "text/plain" and not text_body:
                    charset = part.get_content_charset() or "utf-8"
                    text_body = part.get_payload(decode=True).decode(charset, errors="replace")
                elif ct == "text/html" and not html_body:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = part.get_payload(decode=True).decode(charset, errors="replace")
        else:
            charset = msg.get_content_charset() or "utf-8"
            ct = msg.get_content_type()
            if ct == "text/html":
                html_body = msg.get_payload(decode=True).decode(charset, errors="replace")
            else:
                text_body = msg.get_payload(decode=True).decode(charset, errors="replace")

        print(json.dumps({
            "success": True,
            "id": args.id,
            "subject": subject,
            "from": from_addr,
            "to": to_addr,
            "cc": cc,
            "bcc": bcc,
            "date": date,
            "text_body": text_body,
            "html_body": html_body,
            "attachments": attachments,
        }, ensure_ascii=False, indent=2))
    finally:
        imap.logout()


# ── 子命令: draft ────────────────────────────────────────────

def cmd_draft(args):
    user, password = resolve_credentials()
    imap = imap_connect(args.imap_host, args.imap_port, user, password)

    to = parse_recipients(args.to) if args.to else []
    cc = parse_recipients(args.cc)
    bcc = parse_recipients(args.bcc)

    body = args.body
    body_html = args.body_html
    if args.body_file:
        import pathlib
        body_content = pathlib.Path(args.body_file).read_text(encoding='utf-8')
        if body_html or (body_content.strip().startswith('<!') or body_content.strip().startswith('<')):
            body_html = body_content
        else:
            body = body_content

    msg = build_message(
        sender=user,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=args.subject or "(无主题)",
        body=body,
        body_html=body_html,
        attachments=args.attachments or [],
    )

    try:
        if args.replace:
            imap.select('"Drafts"' if args.folder == "Drafts" else args.folder)
            typ, data = imap.search(None, "ALL")
            if data[0]:
                for mid in data[0].split():
                    imap.store(mid, "+FLAGS", "\\Deleted")
                imap.expunge()

        imap.select('"Drafts"' if args.folder == "Drafts" else args.folder)
        imap.append(args.folder, "\\Draft", None, msg.as_bytes())

        print(json.dumps({
            "success": True,
            "message": "草稿已保存",
            "details": {
                "to": to,
                "cc": cc,
                "bcc": bcc,
                "subject": args.subject,
            },
        }, ensure_ascii=False, indent=2))
    finally:
        imap.logout()


# ── 子命令: delete ───────────────────────────────────────────

def cmd_delete(args):
    user, password = resolve_credentials()
    imap = imap_connect(args.imap_host, args.imap_port, user, password)
    try:
        imap.select(f'"{args.folder}"' if " " in args.folder else args.folder)
        mid = args.id.encode() if isinstance(args.id, str) else args.id
        imap.store(mid, "+FLAGS", "\\Deleted")
        imap.expunge()
        print(json.dumps({
            "success": True,
            "message": f"邮件 {args.id} 已从 {args.folder} 删除",
        }, ensure_ascii=False, indent=2))
    finally:
        imap.logout()


# ── 子命令: flag ─────────────────────────────────────────────

def cmd_flag(args):
    user, password = resolve_credentials()
    imap = imap_connect(args.imap_host, args.imap_port, user, password)
    try:
        imap.select(f'"{args.folder}"' if " " in args.folder else args.folder)
        mid = args.id.encode() if isinstance(args.id, str) else args.id
        changes = []
        if args.seen:
            imap.store(mid, "+FLAGS", "\\Seen")
            changes.append("已读")
        if args.unseen:
            imap.store(mid, "-FLAGS", "\\Seen")
            changes.append("未读")
        if args.flagged:
            imap.store(mid, "+FLAGS", "\\Flagged")
            changes.append("星标")
        if args.unflagged:
            imap.store(mid, "-FLAGS", "\\Flagged")
            changes.append("取消星标")
        print(json.dumps({
            "success": True,
            "message": f"邮件 {args.id} 已标记: {', '.join(changes)}",
        }, ensure_ascii=False, indent=2))
    finally:
        imap.logout()


# ── 子命令: move ─────────────────────────────────────────────

def cmd_move(args):
    user, password = resolve_credentials()
    imap = imap_connect(args.imap_host, args.imap_port, user, password)
    try:
        imap.select(f'"{args.source}"' if " " in args.source else args.source)
        mid = args.id.encode() if isinstance(args.id, str) else args.id
        # COPY to destination, then delete from source
        result = imap.copy(mid, f'"{args.to}"' if " " in args.to else args.to)
        if result[0] == "OK":
            imap.store(mid, "+FLAGS", "\\Deleted")
            imap.expunge()
            print(json.dumps({
                "success": True,
                "message": f"邮件 {args.id} 已从 {args.source} 移动到 {args.to}",
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"success": False, "message": f"移动失败: {result}"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
    finally:
        imap.logout()


# ── 子命令: folders ──────────────────────────────────────────

def cmd_folders(args):
    user, password = resolve_credentials()
    imap = imap_connect(args.imap_host, args.imap_port, user, password)
    try:
        typ, data = imap.list()
        folders = []
        for item in data:
            if isinstance(item, bytes):
                line = item.decode("utf-8", errors="replace")
                # 格式: '(\\HasNoChildren) "/" "INBOX"'
                match = re.search(r'\(([^)]*)\)\s+"([^"]*)"\s+"([^"]+)"', line)
                if match:
                    flags_str, sep, name = match.groups()
                    flags = [f.strip() for f in flags_str.split() if f.strip()]
                    folders.append({"name": name, "flags": flags})
        print(json.dumps({"success": True, "folders": folders}, ensure_ascii=False, indent=2))
    finally:
        imap.logout()


# ── 主入口 ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="邮件管理")
    sub = parser.add_subparsers(dest="command", required=True)

    # send
    p = sub.add_parser("send", help="发送邮件")
    p.add_argument("--to", required=True, help="收件人，多个用逗号分隔")
    p.add_argument("--cc", help="抄送")
    p.add_argument("--bcc", help="密送")
    p.add_argument("--subject", required=True, help="邮件主题")
    p.add_argument("--body", help="纯文本正文")
    p.add_argument("--body-html", help="HTML 正文")
    p.add_argument("--body-file", help="从文件读取正文内容")
    p.add_argument("--attachments", nargs="*", default=[], help="附件路径")
    p.add_argument("--smtp-host", default=DEFAULT_SMTP_HOST)
    p.add_argument("--smtp-port", type=int, default=DEFAULT_SMTP_PORT)
    p.add_argument("--use-tls", action="store_true")

    # list
    p = sub.add_parser("list", help="列出邮件")
    p.add_argument("--folder", default="INBOX", help="文件夹 (默认 INBOX)")
    p.add_argument("--days", type=int, default=7, help="最近 N 天 (默认 7)")
    p.add_argument("--limit", type=int, default=10, help="最多返回数 (默认 10)")
    p.add_argument("--from", dest="from_addr", help="按发件人过滤")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.add_argument("--imap-host", default=DEFAULT_IMAP_HOST)
    p.add_argument("--imap-port", type=int, default=DEFAULT_IMAP_PORT)

    # read
    p = sub.add_parser("read", help="读取邮件正文")
    p.add_argument("--id", required=True, help="邮件 ID")
    p.add_argument("--folder", default="INBOX")
    p.add_argument("--imap-host", default=DEFAULT_IMAP_HOST)
    p.add_argument("--imap-port", type=int, default=DEFAULT_IMAP_PORT)

    # draft
    p = sub.add_parser("draft", help="保存草稿")
    p.add_argument("--to", help="收件人")
    p.add_argument("--cc", help="抄送")
    p.add_argument("--bcc", help="密送")
    p.add_argument("--subject", help="主题")
    p.add_argument("--body", help="纯文本正文")
    p.add_argument("--body-html", help="HTML 正文")
    p.add_argument("--body-file", help="从文件读取正文内容")
    p.add_argument("--attachments", nargs="*", default=[], help="附件路径")
    p.add_argument("--folder", default="Drafts")
    p.add_argument("--replace", action="store_true", help="替换已有草稿")
    p.add_argument("--imap-host", default=DEFAULT_IMAP_HOST)
    p.add_argument("--imap-port", type=int, default=DEFAULT_IMAP_PORT)

    # delete
    p = sub.add_parser("delete", help="删除邮件")
    p.add_argument("--id", required=True, help="邮件 ID")
    p.add_argument("--folder", default="INBOX")
    p.add_argument("--imap-host", default=DEFAULT_IMAP_HOST)
    p.add_argument("--imap-port", type=int, default=DEFAULT_IMAP_PORT)

    # flag
    p = sub.add_parser("flag", help="标记邮件")
    p.add_argument("--id", required=True, help="邮件 ID")
    p.add_argument("--seen", action="store_true")
    p.add_argument("--unseen", action="store_true")
    p.add_argument("--flagged", action="store_true")
    p.add_argument("--unflagged", action="store_true")
    p.add_argument("--folder", default="INBOX")
    p.add_argument("--imap-host", default=DEFAULT_IMAP_HOST)
    p.add_argument("--imap-port", type=int, default=DEFAULT_IMAP_PORT)

    # move
    p = sub.add_parser("move", help="移动邮件")
    p.add_argument("--id", required=True, help="邮件 ID")
    p.add_argument("--to", required=True, dest="to_folder", help="目标文件夹")
    p.add_argument("--source", default="INBOX", help="源文件夹 (默认 INBOX)")
    p.add_argument("--imap-host", default=DEFAULT_IMAP_HOST)
    p.add_argument("--imap-port", type=int, default=DEFAULT_IMAP_PORT)

    # folders
    p = sub.add_parser("folders", help="列出所有文件夹")
    p.add_argument("--imap-host", default=DEFAULT_IMAP_HOST)
    p.add_argument("--imap-port", type=int, default=DEFAULT_IMAP_PORT)

    args = parser.parse_args()

    if args.command == "send":
        # send 需要额外检查
        if not args.body and not args.body_html and not args.body_file:
            print(json.dumps({"success": False, "message": "必须提供 --body 或 --body-html 或 --body-file"}), file=sys.stderr)
            sys.exit(1)
        cmd_send(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "read":
        cmd_read(args)
    elif args.command == "draft":
        cmd_draft(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "flag":
        cmd_flag(args)
    elif args.command == "move":
        cmd_move(args)
    elif args.command == "folders":
        cmd_folders(args)


if __name__ == "__main__":
    main()
