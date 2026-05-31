#!/usr/bin/env python3
"""
Save email draft to Tencent Enterprise Mail (exmail) via IMAP APPEND.

Usage:
    python3 save_draft.py --from "程舜 <chengs@tuwan.com>" \\
                          --to "hhh@tuwan.com" \\
                          --cc "qupq@tuwan.com,wangfz@tuwan.com" \\
                          --subject "程舜 5.22 周报" \\
                          --html-file /tmp/email_body.html \\
                          --text-file /tmp/email_body.txt \\
                          --email chengs@tuwan.com \\
                          --auth-code <AUTH_CODE>

Note: exmail send_email API cannot save drafts. This script uses IMAP APPEND
      to save drafts to the Drafts folder.
"""

import argparse
import imaplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# 加载项目根 .env
_env_file = Path(__file__).resolve().parents[4] / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        if _line.strip() and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))


def save_draft(from_addr, to_addr, cc_addr, subject, html_content, text_content,
               email_account, auth_code):
    """Save email draft via IMAP APPEND to exmail Drafts folder."""
    imap = imaplib.IMAP4_SSL("imap.exmail.qq.com", 993)
    imap.login(email_account, auth_code)

    # Delete existing drafts
    imap.select("Drafts")
    typ, data = imap.search(None, "ALL")
    msg_ids = data[0].split() if data[0] else []
    for mid in msg_ids:
        imap.store(mid, "+FLAGS", "\\Deleted")
    imap.expunge()

    # Build email
    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to_addr
    if cc_addr:
        msg["Cc"] = cc_addr
    msg["Subject"] = subject

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # Save as draft
    typ, data = imap.append("Drafts", "\\Draft", None, msg.as_bytes())
    imap.logout()

    if typ == "OK":
        print(f"✅ Draft saved: {subject}")
    else:
        print(f"❌ Draft save failed: {data}")
        return False
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save email draft to exmail via IMAP")
    parser.add_argument("--from", dest="from_addr", required=True, help="From address")
    parser.add_argument("--to", dest="to_addr", required=True, help="To address")
    parser.add_argument("--cc", dest="cc_addr", default="", help="CC addresses (comma-separated)")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--html-file", required=True, help="Path to HTML body file")
    parser.add_argument("--text-file", required=True, help="Path to plain text body file")
    parser.add_argument("--email", required=True, help="IMAP login email")
    parser.add_argument("--auth-code", required=True, help="IMAP authorization code")

    args = parser.parse_args()

    with open(args.html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    with open(args.text_file, "r", encoding="utf-8") as f:
        text_content = f.read()

    success = save_draft(
        args.from_addr, args.to_addr, args.cc_addr, args.subject,
        html_content, text_content, args.email, args.auth_code
    )
    exit(0 if success else 1)
