"""统一代理检测与管理模块（重导出层）。

核心逻辑已迁移至 lib/proxy.py，本文件保持向后兼容。
供 invest 分类下的脚本继续使用原有 import 路径。

用法:
  sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "_shared"))
  from proxy import detect_proxy, setup_proxy_env
  from proxy import apply_proxy_to_session
"""

import os
import sys
from pathlib import Path

# 从 lib/proxy.py 导入核心检测逻辑
_scripts_dir = Path(__file__).resolve().parents[3] / "lib"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))
from proxy import detect_proxy  # noqa: E402, F401


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
