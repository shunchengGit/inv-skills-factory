#!/usr/bin/env python3
"""通过讯飞星火大模型识别图片内容。

用法:
    python recognize.py <图片路径或URL>

示例:
    python recognize.py /path/to/image.jpg
    python recognize.py https://example.com/image.png
"""

import base64
import json
import mimetypes
import os
import sys
import urllib.request
from pathlib import Path

import requests


def load_env() -> None:
    """加载项目根目录的 .env 文件。"""
    env_file = Path(__file__).resolve().parents[4] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, val)


def is_url(path_or_url: str) -> bool:
    return path_or_url.startswith(("http://", "https://"))


def download_image(url: str) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def image_to_base64(path_or_url: str) -> tuple[str, str]:
    """将图片转为 base64 字符串，返回 (base64_data, mime_type)。"""
    if is_url(path_or_url):
        data = download_image(path_or_url)
        mime_type, _ = mimetypes.guess_type(path_or_url)
        mime_type = mime_type or "image/jpeg"
    else:
        path = Path(path_or_url)
        if not path.exists():
            print(f"错误: 文件不存在: {path_or_url}", file=sys.stderr)
            sys.exit(1)
        data = path.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(path))
        mime_type = mime_type or "image/jpeg"

    b64 = base64.b64encode(data).decode("utf-8")
    return b64, mime_type


def recognize_image(path_or_url: str) -> str:
    """调用讯飞星火大模型识别图片，返回描述文本。"""
    load_env()

    api_key = os.environ.get("XOPKIMIK26_API_KEY")
    if not api_key:
        print("错误: 未设置 XOPKIMIK26_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    base_url = "https://maas-coding-api.cn-huabei-1.xf-yun.com/v2"
    model = "xopkimik26"

    image_b64, mime_type = image_to_base64(path_or_url)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                {"type": "text", "text": "请详细描述这张图片的内容。"},
            ],
        }
    ]

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            print(f"错误: API 返回空内容\n响应: {json.dumps(data, ensure_ascii=False, indent=2)}", file=sys.stderr)
            sys.exit(1)
        return content
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, IndexError) as e:
        print(f"解析响应失败: {e}\n原始响应: {resp.text}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print(f"用法: python {sys.argv[0]} <图片路径或URL>", file=sys.stderr)
        sys.exit(1)

    path_or_url = sys.argv[1]
    result = recognize_image(path_or_url)
    print(result)


if __name__ == "__main__":
    main()
