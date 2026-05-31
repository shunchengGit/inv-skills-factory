"""代理检测 — 优先环境变量，其次本地 Clash 端口扫描。

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
  from proxy import detect_proxy
"""

import os
import socket

_CLASH_PORTS = (7890, 7891, 7897)


def detect_proxy() -> str | None:
    """检测可用代理：优先环境变量，其次本地 Clash 端口扫描。"""
    proxy = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
    )
    if proxy:
        return proxy
    for port in _CLASH_PORTS:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return f"http://127.0.0.1:{port}"
        except (ConnectionRefusedError, OSError):
            pass
    return None
