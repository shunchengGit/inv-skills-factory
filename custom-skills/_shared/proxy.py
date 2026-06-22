"""统一代理检测与管理模块。

提供代理检测、环境变量设置两类能力。
供 invest 技能脚本通过 `_shared` 路径引用。

用法:
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "_shared"))
  from proxy import detect_proxy, setup_proxy_env
"""

from __future__ import annotations

import os
import socket
import sys

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


def setup_proxy_env(override: str | None = None) -> bool:
    """为 yfinance/curl_cffi 设置代理环境变量。

    yfinance/curl_cffi 从 os.environ 读取代理配置。
    使用 setdefault 避免覆盖已有环境变量设置。

    Args:
        override: 手动指定代理地址，覆盖自动检测结果。

    Returns:
        True 表示代理已设置，False 表示未检测到可用代理。
    """
    proxy = override or detect_proxy()
    if proxy:
        os.environ.setdefault("HTTPS_PROXY", proxy)
        os.environ.setdefault("HTTP_PROXY", proxy)
        return True
    print("⚠️ 未检测到代理（HTTPS_PROXY/HTTP_PROXY 未设置，且本地 Clash 端口 7890/7891/7897 均未监听）", file=sys.stderr)
    print("   美股/港股通过 Yahoo Finance 获取数据，国内网络直连大概率被限流。", file=sys.stderr)
    print("   请先启动 Clash 或手动设置: export HTTPS_PROXY=http://127.0.0.1:7890", file=sys.stderr)
    return False
