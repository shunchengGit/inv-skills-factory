"""统一代理检测与管理模块。

供所有需要代理的技能脚本调用，消除各脚本中重复的代理检测逻辑。

提供两种代理应用方式：
1. setup_proxy_env() — 设 os.environ（给 yfinance/curl_cffi 用）
2. apply_proxy_to_session() — 设 session.proxies（给 requests 用）

用法:
  sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "_shared"))
  from proxy import detect_proxy, setup_proxy_env, clear_proxy_env, restore_proxy_env
  from proxy import apply_proxy_to_session
"""

import os
import socket
import sys

_PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
_CLASH_PORTS = (7890, 7891, 7897)

_saved_proxy_env: dict[str, str] = {}


def detect_proxy() -> str | None:
    """检测可用代理：优先环境变量，其次默认 Clash 端口。

    检测顺序：
    1. HTTPS_PROXY / HTTP_PROXY / https_proxy / http_proxy 环境变量
    2. 本地 Clash 端口扫描 (7890, 7891, 7897)
    3. 均不可用则返回 None
    """
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or \
            os.environ.get("https_proxy") or os.environ.get("http_proxy")
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


def apply_proxy_to_session(session, proxy: str | None = None) -> None:
    """为 requests.Session 设置代理。

    Args:
        session: requests.Session 实例。
        proxy: 代理地址。None 则自动检测。检测不到时不修改 session。
    """
    proxy_url = proxy or detect_proxy()
    if proxy_url:
        session.proxies["http"] = proxy_url
        session.proxies["https"] = proxy_url


def clear_proxy_env() -> None:
    """临时清除代理环境变量，避免国内数据源绕远路。

    在 akshare 等国内数据源获取前调用，完成后由 restore_proxy_env 恢复。
    """
    global _saved_proxy_env
    _saved_proxy_env = {
        k: os.environ.pop(k)
        for k in _PROXY_ENV_KEYS
        if k in os.environ
    }


def restore_proxy_env() -> None:
    """恢复之前清除的代理环境变量。"""
    global _saved_proxy_env
    if _saved_proxy_env:
        os.environ.update(_saved_proxy_env)
        _saved_proxy_env = {}