---
name: base-image-recognizer
description: 通过讯飞星火大模型识别图片内容，支持传入图片路径或图片URL，返回图片的文字描述
---

## 功能

调用讯飞星火大模型 API 对图片进行识别和描述。

## 配置

环境变量（写入 `.env`）：

```
XOPKIMIK26_API_KEY=your-api-key-here
```

## 使用方式

### 1. Python 脚本直接调用

```python
import subprocess

result = subprocess.run(
    ["python", "~/.hermes/skills/base-image-recognizer/scripts/recognize.py", "/path/to/image.jpg"],
    capture_output=True, text=True
)
print(result.stdout)
```

### 2. 命令行调用

```bash
python ~/.hermes/skills/base-image-recognizer/scripts/recognize.py /path/to/image.jpg
```

支持本地图片路径或图片URL。

## 输出

返回图片的文字描述，直接输出到 stdout。
