---
name: base-pwright
description: Playwright 无头浏览器抓取基础能力，供其他技能调用
version: 1.0.0
commands: []
---

# base-pwright：Playwright 抓取基础模块

提供 JS 渲染页面抓取的核心能力：浏览器启动、智能正文提取、html2text 转换。

## 公开接口

| 函数 | 用途 |
|------|------|
| `scrape_url(url)` | 一站式抓取 → Markdown |
| `extract_text(url)` | 一站式抓取 → 纯文本 |
| `launch_browser()` | 启动浏览器，返回 (pw, browser, context, page) |

## 在脚本中使用

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "base" / "base-pwright" / "scripts"))
from pwright import scrape_url, extract_text, launch_browser

# 简单抓取
result = scrape_url("https://example.com")
print(result["markdown"])

# 自定义浏览器操作
pw, browser, context, page = launch_browser()
page.goto("https://example.com")
# ... 自定义操作 ...
browser.close()
pw.stop()
```
