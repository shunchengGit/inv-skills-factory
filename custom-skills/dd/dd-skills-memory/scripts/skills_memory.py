#!/usr/bin/env python3
"""Skills Memory — 纯通用存储服务，与技能无关。

提供按技能隔离的文档原子 CRUD 操作。
后端可配置：dingtalk、local。

用法:
  from skills_memory import SkillsMemory

  sm = SkillsMemory()
  sm.read_doc("dd-work-log", "2026-06")
  sm.update_doc("dd-work-log", "2026-06", "# 新内容\n")
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

# 加载项目根目录的 .env 文件
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_PROJECT_ROOT / "lib"))
from dotenv import load as _load_dotenv
_load_dotenv()

# ─── 抽象存储后端 ──────────────────────────────────────────


class StorageBackend(ABC):
    """存储后端抽象基类。"""

    @abstractmethod
    def find_doc(self, skill_name: str, doc_name: str) -> dict:
        """查找文档。"""
        pass

    @abstractmethod
    def create_doc(self, skill_name: str, doc_name: str, content: str) -> dict:
        """创建文档。"""
        pass

    @abstractmethod
    def read_doc(self, skill_name: str, doc_id: str) -> dict:
        """读取文档内容。"""
        pass

    @abstractmethod
    def update_doc(self, skill_name: str, doc_id: str, content: str) -> dict:
        """更新文档内容。"""
        pass

    @abstractmethod
    def delete_doc(self, skill_name: str, doc_id: str) -> dict:
        """删除文档。"""
        pass

    @abstractmethod
    def list_docs(self, skill_name: str) -> dict:
        """列出所有文档。"""
        pass


# ─── 钉钉知识库存储后端 ────────────────────────────────────


class DingTalkBackend(StorageBackend):
    """钉钉知识库文档存储后端。"""

    _WORKSPACE_ID: str | None = None
    _SKILL_FOLDER_IDS: dict[str, str] = {}

    def __init__(self, folder_name: str = "[勿动]SkillsMemory"):
        self.folder_name = folder_name

    @classmethod
    def _get_workspace_id(cls) -> str:
        if cls._WORKSPACE_ID is not None:
            return cls._WORKSPACE_ID

        env_id = os.environ.get("SM_WORKSPACE_ID", "").strip()
        if env_id:
            cls._WORKSPACE_ID = env_id
            return cls._WORKSPACE_ID

        result = cls._dws(["wiki", "space", "list", "--type", "myWikiSpace"])
        if not result.get("success"):
            return ""

        spaces = result.get("wikiSpaces", [])
        if not spaces:
            return ""

        cls._WORKSPACE_ID = spaces[0]["workspaceId"]
        return cls._WORKSPACE_ID

    @staticmethod
    def _dws(args: list[str]) -> dict:
        cmd = ["dws"] + args + ["--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return {"success": False, "error": stderr or f"dws 命令失败: {' '.join(args)}"}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"success": False, "error": f"dws 返回非 JSON: {result.stdout[:200]}"}

    def _get_or_create_skill_folder(self, skill_name: str) -> dict:
        if skill_name in self._SKILL_FOLDER_IDS:
            return {"success": True, "folderId": self._SKILL_FOLDER_IDS[skill_name]}

        ws_id = self._get_workspace_id()
        if not ws_id:
            return {"success": False, "error": "无法获取知识库空间 ID"}

        # 查找根文件夹
        list_result = self._dws(["doc", "list", "--workspace", ws_id])
        if not list_result.get("success"):
            return list_result

        root_folder_id = None
        for node in list_result.get("nodes", []):
            if node.get("name") == self.folder_name and node.get("nodeType") == "folder":
                root_folder_id = node["nodeId"]
                break

        if root_folder_id is None:
            result = self._dws([
                "doc", "folder", "create",
                "--name", self.folder_name,
                "--workspace", ws_id,
            ])
            if not result.get("success"):
                return result
            root_folder_id = result["nodeId"]

        # 查找技能文件夹
        skill_list = self._dws(["doc", "list", "--folder", root_folder_id])
        if not skill_list.get("success"):
            return skill_list

        for node in skill_list.get("nodes", []):
            if node.get("name") == skill_name and node.get("nodeType") == "folder":
                self._SKILL_FOLDER_IDS[skill_name] = node["nodeId"]
                return {"success": True, "folderId": node["nodeId"]}

        # 创建技能文件夹
        result = self._dws([
            "doc", "folder", "create",
            "--name", skill_name,
            "--folder", root_folder_id,
        ])
        if not result.get("success"):
            return result

        self._SKILL_FOLDER_IDS[skill_name] = result["nodeId"]
        return {"success": True, "folderId": result["nodeId"]}

    def find_doc(self, skill_name: str, doc_name: str) -> dict:
        folder_result = self._get_or_create_skill_folder(skill_name)
        if not folder_result["success"]:
            return folder_result

        list_result = self._dws(["doc", "list", "--folder", folder_result["folderId"]])
        if not list_result.get("success"):
            return list_result

        for node in list_result.get("nodes", []):
            if node.get("name") == doc_name and node.get("nodeType") == "file":
                return {"success": True, "nodeId": node["nodeId"]}

        return {"success": True, "nodeId": None}

    def create_doc(self, skill_name: str, doc_name: str, content: str) -> dict:
        folder_result = self._get_or_create_skill_folder(skill_name)
        if not folder_result["success"]:
            return folder_result

        result = self._dws([
            "doc", "create",
            "--name", doc_name,
            "--folder", folder_result["folderId"],
            "--markdown", content,
        ])
        if not result.get("success"):
            return result

        return {"success": True, "nodeId": result["nodeId"]}

    def read_doc(self, skill_name: str, node_id: str) -> dict:
        result = self._dws(["doc", "read", "--node", node_id])
        if not result.get("success"):
            return result
        content = result.get("data", {}).get("markdown") or result.get("markdown", "")
        return {"success": True, "content": content}

    def update_doc(self, skill_name: str, node_id: str, content: str) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp_path = f.name

        try:
            result = self._dws([
                "doc", "update",
                "--node", node_id,
                "--content-file", tmp_path,
                "--mode", "overwrite",
            ])
            if result.get("success"):
                return {"success": True, "action": "overwrite"}

            return self._rebuild_doc_blocks(node_id, content)
        finally:
            os.unlink(tmp_path)

    def _rebuild_doc_blocks(self, node_id: str, content: str) -> dict:
        blocks_result = self._dws(["doc", "block", "list", "--node", node_id])
        if blocks_result.get("success"):
            blocks = blocks_result.get("blocks", [])
            for block in reversed(blocks):
                bid = block.get("blockId")
                if bid:
                    self._dws(["doc", "block", "delete", "--node", node_id, "--block-id", bid, "--yes"])

        for line in content.split("\n"):
            if line.startswith("# "):
                self._dws(["doc", "block", "insert", "--node", node_id, "--heading", line[2:], "--level", "1"])
            elif line.startswith("## "):
                self._dws(["doc", "block", "insert", "--node", node_id, "--heading", line[3:], "--level", "2"])
            elif line.strip():
                self._dws(["doc", "block", "insert", "--node", node_id, "--text", line])
            else:
                self._dws(["doc", "block", "insert", "--node", node_id, "--text", " "])

        return {"success": True, "action": "block-rebuild"}

    def delete_doc(self, skill_name: str, node_id: str) -> dict:
        result = self._dws(["doc", "delete", "--node", node_id, "--yes"])
        if not result.get("success"):
            return result
        return {"success": True, "action": "delete"}

    def list_docs(self, skill_name: str) -> dict:
        folder_result = self._get_or_create_skill_folder(skill_name)
        if not folder_result["success"]:
            return folder_result

        list_result = self._dws(["doc", "list", "--folder", folder_result["folderId"]])
        if not list_result.get("success"):
            return list_result

        docs = []
        for node in list_result.get("nodes", []):
            if node.get("nodeType") == "file":
                docs.append({"name": node.get("name"), "nodeId": node.get("nodeId")})

        return {"success": True, "docs": docs}


# ─── 钉盘存储后端 ──────────────────────────────────────────


class DingTalkDriveBackend(StorageBackend):
    """钉钉云盘（钉盘）存储后端。

    将文档存储为钉盘中的 Markdown 文件。
    存储路径: 钉盘 / [勿动]SkillsMemory /<skill_name>/<doc_name>.txt
    """

    _SPACE_ID: str | None = None
    _ROOT_FOLDER_ID: str | None = None
    _SKILL_FOLDER_IDS: dict[str, str] = {}

    def __init__(self, folder_name: str = "[勿动]SkillsMemory"):
        self.folder_name = folder_name

    @classmethod
    def _dws(cls, args: list[str]) -> dict:
        cmd = ["dws"] + args + ["--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return {"success": False, "error": stderr or f"dws 命令失败: {' '.join(args)}"}
        # 某些命令（如 drive download）成功时返回空输出
        if not result.stdout.strip():
            return {"success": True}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"success": False, "error": f"dws 返回非 JSON: {result.stdout[:200]}"}

    def _get_space_info(self) -> dict:
        """获取钉盘空间信息。"""
        if self._SPACE_ID is not None and self._ROOT_FOLDER_ID is not None:
            return {"success": True, "spaceId": self._SPACE_ID, "rootFolderId": self._ROOT_FOLDER_ID}

        # 优先从环境变量获取
        env_space = os.environ.get("SM_DRIVE_SPACE_ID", "").strip()
        env_root = os.environ.get("SM_DRIVE_ROOT_FOLDER_ID", "").strip()
        if env_space and env_root:
            self._SPACE_ID = env_space
            self._ROOT_FOLDER_ID = env_root
            return {"success": True, "spaceId": self._SPACE_ID, "rootFolderId": self._ROOT_FOLDER_ID}

        # 自动查询第一个空间
        result = self._dws(["drive", "list-spaces"])
        if not result.get("success"):
            return result

        items = result.get("result", {}).get("items", [])
        if not items:
            return {"success": False, "error": "没有可用的钉盘空间"}

        # 使用第一个空间（通常是全员文件夹）
        first = items[0]
        self._SPACE_ID = str(first["spaceId"])
        self._ROOT_FOLDER_ID = first["rootFolderId"]

        return {"success": True, "spaceId": self._SPACE_ID, "rootFolderId": self._ROOT_FOLDER_ID}

    def _get_root_folder_id(self) -> str:
        """获取或创建钉盘根文件夹 ID。"""
        if self._ROOT_FOLDER_ID is not None:
            return self._ROOT_FOLDER_ID

        space_info = self._get_space_info()
        if not space_info.get("success"):
            return ""

        # 列出根目录下的文件夹
        list_result = self._dws([
            "drive", "list",
            "--space-id", space_info["spaceId"],
            "--parent-id", space_info["rootFolderId"],
        ])
        if not list_result.get("success"):
            return ""

        for item in list_result.get("result", {}).get("items", []):
            if item.get("name") == self.folder_name and item.get("type") in ("folder", "FOLDER"):
                self._ROOT_FOLDER_ID = item["id"]
                return self._ROOT_FOLDER_ID

        # 创建根文件夹
        result = self._dws([
            "drive", "mkdir",
            "--space-id", space_info["spaceId"],
            "--parent-id", space_info["rootFolderId"],
            "--name", self.folder_name,
        ])
        if not result.get("success"):
            return ""

        self._ROOT_FOLDER_ID = result["result"]["id"]
        return self._ROOT_FOLDER_ID

    def _get_or_create_skill_folder(self, skill_name: str) -> dict:
        """获取或创建技能文件夹。"""
        if skill_name in self._SKILL_FOLDER_IDS:
            return {"success": True, "folderId": self._SKILL_FOLDER_IDS[skill_name]}

        space_info = self._get_space_info()
        if not space_info.get("success"):
            return space_info

        root_id = self._get_root_folder_id()
        if not root_id:
            return {"success": False, "error": "无法获取钉盘根文件夹 ID"}

        # 查找技能文件夹
        list_result = self._dws([
            "drive", "list",
            "--space-id", space_info["spaceId"],
            "--parent-id", root_id,
        ])
        if not list_result.get("success"):
            return list_result

        for item in list_result.get("result", {}).get("items", []):
            if item.get("name") == skill_name and item.get("type") in ("folder", "FOLDER"):
                self._SKILL_FOLDER_IDS[skill_name] = item["id"]
                return {"success": True, "folderId": item["id"]}

        # 创建技能文件夹
        result = self._dws([
            "drive", "mkdir",
            "--space-id", space_info["spaceId"],
            "--parent-id", root_id,
            "--name", skill_name,
        ])
        if not result.get("success"):
            return result

        self._SKILL_FOLDER_IDS[skill_name] = result["result"]["id"]
        return {"success": True, "folderId": result["result"]["id"]}

    def find_doc(self, skill_name: str, doc_name: str) -> dict:
        """查找文档。"""
        folder_result = self._get_or_create_skill_folder(skill_name)
        if not folder_result["success"]:
            return folder_result

        space_info = self._get_space_info()
        if not space_info.get("success"):
            return space_info

        list_result = self._dws([
            "drive", "list",
            "--space-id", space_info["spaceId"],
            "--parent-id", folder_result["folderId"],
        ])
        if not list_result.get("success"):
            return list_result

        for item in list_result.get("result", {}).get("items", []):
            if item.get("name") == f"{doc_name}.txt" and item.get("type") in ("file", "FILE"):
                return {"success": True, "nodeId": item["id"]}

        return {"success": True, "nodeId": None}

    def create_doc(self, skill_name: str, doc_name: str, content: str) -> dict:
        """创建文档。"""
        folder_result = self._get_or_create_skill_folder(skill_name)
        if not folder_result["success"]:
            return folder_result

        space_info = self._get_space_info()
        if not space_info.get("success"):
            return space_info

        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp_path = f.name

        try:
            result = self._dws([
                "drive", "upload",
                "--space-id", space_info["spaceId"],
                "--parent-id", folder_result["folderId"],
                "--file", tmp_path,
                "--name", f"{doc_name}.txt",
            ])
            if not result.get("success"):
                return result

            return {"success": True, "nodeId": result["result"]["id"]}
        finally:
            os.unlink(tmp_path)

    def read_doc(self, skill_name: str, doc_id: str) -> dict:
        """读取文档内容。"""
        import urllib.request

        space_info = self._get_space_info()
        if not space_info.get("success"):
            return space_info

        # 下载文件到临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = os.path.join(tmpdir, "doc")
            result = self._dws([
                "drive", "download",
                "--space-id", space_info["spaceId"],
                "--file-id", doc_id,
                "--output", download_path,
            ])
            # drive download 返回的是下载 URL，不是直接下载文件
            # 需要检查文件是否真的被下载了
            if not os.path.exists(download_path) or os.path.getsize(download_path) == 0:
                # 文件未下载，尝试从 result 中获取 URL 手动下载
                if result.get("success"):
                    download_url = result.get("result", {}).get("downloadUrl", "")
                    if download_url:
                        urllib.request.urlretrieve(download_url, download_path)

            if not os.path.exists(download_path) or os.path.getsize(download_path) == 0:
                return {"success": False, "error": "文件下载失败"}

            try:
                with open(download_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return {"success": True, "content": content}
            except Exception as e:
                return {"success": False, "error": f"读取文件失败: {e}"}

    def update_doc(self, skill_name: str, doc_id: str, content: str) -> dict:
        """更新文档内容（钉盘不支持直接覆盖，先删除再上传）。"""
        space_info = self._get_space_info()
        if not space_info.get("success"):
            return space_info

        # 获取文档信息
        info_result = self._dws([
            "drive", "info",
            "--space-id", space_info["spaceId"],
            "--id", doc_id,
        ])
        if not info_result.get("success"):
            return info_result

        parent_id = info_result.get("result", {}).get("parentId", "")
        doc_name = info_result.get("result", {}).get("name", "")

        if not parent_id:
            return {"success": False, "error": "无法获取文档父文件夹 ID"}

        # 删除旧文件
        delete_result = self._dws([
            "drive", "delete",
            "--space-id", space_info["spaceId"],
            "--id", doc_id,
            "--yes",
        ])
        if not delete_result.get("success"):
            return delete_result

        # 创建新文件
        return self.create_doc(skill_name, doc_name, content)

    def delete_doc(self, skill_name: str, doc_id: str) -> dict:
        """删除文档。"""
        space_info = self._get_space_info()
        if not space_info.get("success"):
            return space_info

        result = self._dws([
            "drive", "delete",
            "--space-id", space_info["spaceId"],
            "--id", doc_id,
            "--yes",
        ])
        if not result.get("success"):
            return result
        return {"success": True, "action": "delete"}

    def list_docs(self, skill_name: str) -> dict:
        """列出技能的所有文档。"""
        folder_result = self._get_or_create_skill_folder(skill_name)
        if not folder_result["success"]:
            return folder_result

        space_info = self._get_space_info()
        if not space_info.get("success"):
            return space_info

        list_result = self._dws([
            "drive", "list",
            "--space-id", space_info["spaceId"],
            "--parent-id", folder_result["folderId"],
        ])
        if not list_result.get("success"):
            return list_result

        docs = []
        for item in list_result.get("result", {}).get("items", []):
            if item.get("type") in ("file", "FILE") and item.get("name", "").endswith(".txt"):
                docs.append({
                    "name": item.get("name", "").replace(".txt", ""),
                    "nodeId": item.get("id"),
                })

        return {"success": True, "docs": docs}


# ─── 本地文件存储后端 ──────────────────────────────────────


class LocalBackend(StorageBackend):
    """本地文件系统存储后端。

    存储路径: ~/.skills-memory/<skill_name>/<doc_name>.md
    """

    BASE_DIR = Path.home() / ".skills-memory"

    def _skill_dir(self, skill_name: str) -> Path:
        return self.BASE_DIR / skill_name

    def _doc_path(self, skill_name: str, doc_name: str) -> Path:
        return self._skill_dir(skill_name) / f"{doc_name}.md"

    def find_doc(self, skill_name: str, doc_name: str) -> dict:
        doc_path = self._doc_path(skill_name, doc_name)
        if doc_path.exists():
            return {"success": True, "nodeId": doc_name}
        return {"success": True, "nodeId": None}

    def create_doc(self, skill_name: str, doc_name: str, content: str) -> dict:
        doc_path = self._doc_path(skill_name, doc_name)
        try:
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(content, encoding="utf-8")
            return {"success": True, "nodeId": doc_name}
        except Exception as e:
            return {"success": False, "error": f"创建文档失败: {e}"}

    def read_doc(self, skill_name: str, doc_id: str) -> dict:
        doc_path = self._doc_path(skill_name, doc_id)
        if not doc_path.exists():
            return {"success": False, "error": "文档不存在"}
        try:
            content = doc_path.read_text(encoding="utf-8")
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": f"读取文档失败: {e}"}

    def update_doc(self, skill_name: str, doc_id: str, content: str) -> dict:
        doc_path = self._doc_path(skill_name, doc_id)
        try:
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(content, encoding="utf-8")
            return {"success": True, "action": "overwrite"}
        except Exception as e:
            return {"success": False, "error": f"更新文档失败: {e}"}

    def delete_doc(self, skill_name: str, doc_id: str) -> dict:
        doc_path = self._doc_path(skill_name, doc_id)
        try:
            if doc_path.exists():
                doc_path.unlink()
            return {"success": True, "action": "delete"}
        except Exception as e:
            return {"success": False, "error": f"删除文档失败: {e}"}

    def list_docs(self, skill_name: str) -> dict:
        try:
            docs = []
            skill_dir = self._skill_dir(skill_name)
            if skill_dir.exists():
                for f in skill_dir.iterdir():
                    if f.is_file() and f.suffix == ".md":
                        docs.append({"name": f.stem, "nodeId": f.stem})
            return {"success": True, "docs": docs}
        except Exception as e:
            return {"success": False, "error": f"列出文档失败: {e}"}


# ─── 微云存储后端 ──────────────────────────────────────────


class WeiyunBackend(StorageBackend):
    """微云网盘存储后端。

    通过 HTTP 直接调用微云 MCP API，存储路径: /SkillsMemory/<skill_name>/<doc_name>.txt
    """

    MCP_URL = "https://www.weiyun.com/api/v3/mcpserver"
    _TOKEN: str | None = None
    _ROOT_DIR_KEY: str | None = None

    def __init__(self, folder_name: str = "[勿动]SkillsMemory"):
        self.folder_name = folder_name
        self._token = self._get_token()

    def _get_token(self) -> str:
        """获取微云 MCP Token。

        Token 获取优先级：
        1. 已缓存的 Token
        2. ~/.skills-memory/.env 文件中的 WEIYUN_MCP_TOKEN
        3. 环境变量 WEIYUN_MCP_TOKEN
        """
        if self._TOKEN is not None:
            return self._TOKEN

        # 1. 检查 ~/.skills-memory/.env 文件
        env_file = Path.home() / ".skills-memory" / ".env"
        if env_file.exists():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("WEIYUN_MCP_TOKEN="):
                            token = line[len("WEIYUN_MCP_TOKEN="):].strip().strip('"\'')
                            if token:
                                self._TOKEN = token
                                return self._TOKEN
            except Exception:
                pass

        # 2. 检查环境变量
        env_token = os.environ.get("WEIYUN_MCP_TOKEN", "").strip()
        if env_token:
            self._TOKEN = env_token
            return self._TOKEN

        return ""

    def _mcp_call(self, tool: str, args: dict) -> dict:
        """直接通过 HTTP POST 调用微云 MCP API。"""
        import http.client
        import json
        import ssl

        token = self._get_token()
        if not token:
            return {"success": False, "error": "未配置微云 MCP Token，请先执行授权流程"}

        headers = {
            "Content-Type": "application/json",
            "WyHeader": f"mcp_token={token}",
        }

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": args,
            },
            "id": 1,
        }

        # 使用 TLS 1.2（兼容微云服务器）
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            conn = http.client.HTTPSConnection("www.weiyun.com", context=ssl_context)
            conn.request(
                "POST",
                "/api/v3/mcpserver",
                body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
            )
            response = conn.getresponse()
            response_data = json.loads(response.read().decode("utf-8"))
            conn.close()

            if "error" in response_data:
                return {"success": False, "error": response_data["error"]}
            result = response_data.get("result", {})
            # MCP 返回格式可能是 content 数组，提取其中的文本
            if "content" in result and isinstance(result["content"], list):
                for item in result["content"]:
                    if item.get("type") == "text":
                        try:
                            text_data = json.loads(item.get("text", "{}"))
                            return {"success": True, "result": text_data}
                        except json.JSONDecodeError:
                            return {"success": True, "result": item.get("text", "")}
            return {"success": True, "result": result}
        except http.client.HTTPException as e:
            return {"success": False, "error": f"HTTP 错误: {e}"}
        except json.JSONDecodeError:
            return {"success": False, "error": "返回非 JSON 数据"}
        except Exception as e:
            return {"success": False, "error": f"HTTP 请求失败: {e}"}

    def _get_root_dir(self) -> dict:
        """获取或创建根目录。"""
        if self._ROOT_DIR_KEY is not None:
            return {"success": True, "dirKey": self._ROOT_DIR_KEY}

        # 列出根目录，查找 SkillsMemory 文件夹
        list_result = self._mcp_call("weiyun.list", {"dir_key": "", "get_type": 1, "limit": 50})
        if not list_result.get("success"):
            return list_result

        items = list_result.get("result", {}).get("dir_list", [])
        for item in items:
            if item.get("dir_name") == self.folder_name:
                self._ROOT_DIR_KEY = item["dir_key"]
                return {"success": True, "dirKey": self._ROOT_DIR_KEY}

        # 创建根目录
        create_result = self._mcp_call("weiyun.create_dir", {
            "pdir_key": "",
            "dir_name": self.folder_name,
        })
        if not create_result.get("success"):
            return create_result

        self._ROOT_DIR_KEY = create_result.get("result", {}).get("dir_key", "")
        return {"success": True, "dirKey": self._ROOT_DIR_KEY}

    def _get_skill_dir(self, skill_name: str) -> dict:
        """获取或创建技能目录。"""
        root_result = self._get_root_dir()
        if not root_result.get("success"):
            return root_result

        root_key = root_result["dirKey"]

        # 列出技能目录
        list_result = self._mcp_call("weiyun.list", {"dir_key": root_key, "get_type": 1, "limit": 50})
        if not list_result.get("success"):
            return list_result

        items = list_result.get("result", {}).get("dir_list", [])
        for item in items:
            if item.get("dir_name") == skill_name:
                return {"success": True, "dirKey": item["dir_key"]}

        # 创建技能目录
        create_result = self._mcp_call("weiyun.create_dir", {
            "pdir_key": root_key,
            "dir_name": skill_name,
        })
        if not create_result.get("success"):
            return create_result

        return {"success": True, "dirKey": create_result.get("result", {}).get("dir_key", "")}

    def find_doc(self, skill_name: str, doc_name: str) -> dict:
        """查找文档。"""
        dir_result = self._get_skill_dir(skill_name)
        if not dir_result.get("success"):
            return dir_result

        list_result = self._mcp_call("weiyun.list", {"dir_key": dir_result["dirKey"], "get_type": 2, "limit": 50})
        if not list_result.get("success"):
            return list_result

        for item in list_result.get("result", {}).get("file_list", []):
            if item.get("filename") == f"{doc_name}.txt":
                return {"success": True, "nodeId": item["file_id"]}

        return {"success": True, "nodeId": None}

    def create_doc(self, skill_name: str, doc_name: str, content: str) -> dict:
        """创建文档（上传到微云）。

        使用微云两阶段上传协议：预上传 → HTTP PUT 上传 → 确认上传
        """
        import hashlib
        import base64

        dir_result = self._get_skill_dir(skill_name)
        if not dir_result.get("success"):
            return dir_result

        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp_path = f.name

        try:
            # 计算文件信息
            file_size = os.path.getsize(tmp_path)
            with open(tmp_path, "rb") as f:
                file_data = f.read()
            file_sha = hashlib.sha1(file_data).hexdigest()
            file_md5 = hashlib.md5(file_data).hexdigest()

            # Step 1: 预上传（申请上传凭证）
            # 按 512KB 分块计算 SHA1
            block_size = 512 * 1024
            block_sha_list = []
            for i in range(0, len(file_data), block_size):
                chunk = file_data[i:i + block_size]
                block_sha_list.append(hashlib.sha1(chunk).hexdigest())

            # 计算 check_sha（前 1024 字节的 SHA1）
            check_data = file_data[:1024]
            check_sha = hashlib.sha1(check_data).hexdigest()

            pre_upload_args = {
                "filename": f"{doc_name}.txt",
                "file_size": file_size,
                "file_sha": file_sha,
                "block_sha_list": block_sha_list,
                "check_sha": check_sha,
                "check_data": base64.b64encode(check_data).decode("ascii"),
                "file_md5": file_md5,
                "pdir_key": dir_result["dirKey"],
            }

            pre_result = self._mcp_call("weiyun.upload", pre_upload_args)
            if not pre_result.get("success"):
                return pre_result

            # 检查是否秒传成功
            if pre_result.get("result", {}).get("file_exist"):
                # 秒传成功
                find_result = self.find_doc(skill_name, doc_name)
                return find_result

            upload_key = pre_result.get("result", {}).get("upload_key", "")
            channel_list = pre_result.get("result", {}).get("channel_list", [])
            ex = pre_result.get("result", {}).get("ex", "")

            if not upload_key or not channel_list:
                return {"success": False, "error": "预上传未返回上传通道"}

            # Step 2: HTTP PUT 上传文件内容
            for channel in channel_list:
                channel_id = channel.get("id", 0)
                offset = channel.get("offset", 0)
                length = channel.get("len", 0)

                chunk = file_data[offset:offset + length]

                # 分片上传
                upload_args = {
                    "upload_key": upload_key,
                    "channel_list": channel_list,
                    "channel_id": channel_id,
                    "ex": ex,
                    "file_data": base64.b64encode(chunk).decode("ascii"),
                    "filename": f"{doc_name}.txt",
                }

                upload_result = self._mcp_call("weiyun.upload", upload_args)
                if not upload_result.get("success"):
                    return upload_result

                # 检查上传状态
                upload_state = upload_result.get("result", {}).get("upload_state", 0)
                if upload_state == 2:
                    # 上传完成
                    break
                elif upload_state == 3:
                    # 等待其他通道完成
                    continue
                elif upload_state == 1:
                    # 需要上传下一分片
                    channel_list = upload_result.get("result", {}).get("channel_list", [])
                    ex = upload_result.get("result", {}).get("ex", "")
                    upload_key = upload_result.get("result", {}).get("upload_key", upload_key)

            # 获取上传后的文件 key
            find_result = self.find_doc(skill_name, doc_name)
            return find_result
        finally:
            os.unlink(tmp_path)

    def read_doc(self, skill_name: str, doc_id: str) -> dict:
        """读取文档内容。"""
        import urllib.request

        dir_result = self._get_skill_dir(skill_name)
        if not dir_result.get("success"):
            return dir_result

        download_result = self._mcp_call("weiyun.download", {
            "items": [{"file_id": doc_id, "pdir_key": dir_result["dirKey"]}]
        })
        if not download_result.get("success"):
            return download_result

        items = download_result.get("result", {}).get("items", [])
        if not items:
            return {"success": False, "error": "无法获取下载链接"}

        download_url = items[0].get("https_download_url", "")
        cookie = items[0].get("cookie", "")
        if not download_url:
            return {"success": False, "error": "无法获取下载链接"}

        # 下载文件内容（绕过代理，带 Cookie）
        try:
            req = urllib.request.Request(download_url)
            if cookie:
                req.add_header("Cookie", cookie)
            # 绕过系统代理
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            with opener.open(req, timeout=30) as response:
                content = response.read().decode("utf-8")
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": f"下载文件失败: {e}"}

    def update_doc(self, skill_name: str, doc_id: str, content: str) -> dict:
        """更新文档内容（微云不支持直接覆盖，先删除再上传）。"""
        dir_result = self._get_skill_dir(skill_name)
        if not dir_result.get("success"):
            return dir_result

        # 查找文档名称
        list_result = self._mcp_call("weiyun.list", {"dir_key": dir_result["dirKey"], "get_type": 2, "limit": 50})
        doc_name = None
        if list_result.get("success"):
            for item in list_result.get("result", {}).get("file_list", []):
                if item.get("file_id") == doc_id:
                    doc_name = item.get("filename", "").replace(".txt", "")
                    break
        if not doc_name:
            return {"success": False, "error": "找不到文档"}

        # 删除旧文件
        delete_result = self._mcp_call("weiyun.delete", {
            "file_list": [{"file_id": doc_id, "pdir_key": dir_result["dirKey"]}],
            "delete_completely": True,
        })
        if not delete_result.get("success"):
            return delete_result

        # 创建新文件
        return self.create_doc(skill_name, doc_name, content)

    def delete_doc(self, skill_name: str, doc_id: str) -> dict:
        """删除文档。"""
        dir_result = self._get_skill_dir(skill_name)
        if not dir_result.get("success"):
            return dir_result

        result = self._mcp_call("weiyun.delete", {
            "file_list": [{"file_id": doc_id, "pdir_key": dir_result["dirKey"]}],
            "delete_completely": True,
        })
        if not result.get("success"):
            return result
        return {"success": True, "action": "delete"}

    def list_docs(self, skill_name: str) -> dict:
        """列出技能的所有文档。"""
        dir_result = self._get_skill_dir(skill_name)
        if not dir_result.get("success"):
            return dir_result

        list_result = self._mcp_call("weiyun.list", {"dir_key": dir_result["dirKey"], "get_type": 2, "limit": 50})
        if not list_result.get("success"):
            return list_result

        docs = []
        for item in list_result.get("result", {}).get("file_list", []):
            docs.append({
                "name": item.get("filename", "").replace(".txt", ""),
                "nodeId": item.get("file_id"),
            })

        return {"success": True, "docs": docs}


# ─── SkillsMemory 类 ───────────────────────────────────────


class SkillsMemory:
    """统一存储服务。

    纯通用存储，与技能无关。只提供原子 CRUD。
    后端可配置：dingtalk（知识库）、dingtalk-drive（钉盘）、weiyun（微云）、local。

    Args:
        backend: 存储后端，"dingtalk"、"dingtalk-drive"、"weiyun" 或 "local"，默认从环境变量 SM_BACKEND 读取
        folder_name: 钉钉/微云存储根文件夹名称，默认 "[勿动]SkillsMemory"（钉钉）或 "SkillsMemory"（微云）
    """

    def __init__(self, backend: str | None = None, folder_name: str | None = None):
        if backend is None:
            backend = os.environ.get("SM_BACKEND", "dingtalk").lower()

        # 如果未指定 folder_name，根据后端使用默认值
        if folder_name is None:
            folder_name = "[勿动]SkillsMemory"

        if backend == "dingtalk":
            self._backend: StorageBackend = DingTalkBackend(folder_name=folder_name)
        elif backend == "dingtalk-drive":
            self._backend: StorageBackend = DingTalkDriveBackend(folder_name=folder_name)
        elif backend == "weiyun":
            self._backend: StorageBackend = WeiyunBackend(folder_name=folder_name)
        elif backend == "local":
            self._backend: StorageBackend = LocalBackend()
        else:
            raise ValueError(f"不支持的存储后端: {backend}，支持: dingtalk, dingtalk-drive, weiyun, local")

        self.backend = backend

    # ─── 原子 CRUD（与技能无关）───────────────────────────────

    def find_doc(self, skill_name: str, doc_name: str) -> dict:
        """查找文档。

        Returns: {"success": True, "nodeId": str | None} 或 {"success": False, "error": str}
        """
        return self._backend.find_doc(skill_name, doc_name)

    def create_doc(self, skill_name: str, doc_name: str, content: str) -> dict:
        """创建文档。

        Returns: {"success": True, "nodeId": str} 或 {"success": False, "error": str}
        """
        return self._backend.create_doc(skill_name, doc_name, content)

    def get_or_create_doc(self, skill_name: str, doc_name: str, initial_content: str = "") -> dict:
        """获取或创建文档。

        Returns: {"success": True, "nodeId": str} 或 {"success": False, "error": str}
        """
        find_result = self.find_doc(skill_name, doc_name)
        if not find_result["success"]:
            return find_result

        if find_result["nodeId"] is not None:
            return {"success": True, "nodeId": find_result["nodeId"]}

        return self.create_doc(skill_name, doc_name, initial_content)

    def read_doc(self, skill_name: str, doc_id: str) -> dict:
        """读取文档内容。

        Returns: {"success": True, "content": str} 或 {"success": False, "error": str}
        """
        return self._backend.read_doc(skill_name, doc_id)

    def update_doc(self, skill_name: str, doc_id: str, content: str) -> dict:
        """更新文档内容。"""
        return self._backend.update_doc(skill_name, doc_id, content)

    def delete_doc(self, skill_name: str, doc_id: str) -> dict:
        """删除文档。"""
        return self._backend.delete_doc(skill_name, doc_id)

    def list_docs(self, skill_name: str) -> dict:
        """列出技能的所有文档。

        Returns: {"success": True, "docs": [{"name": str, "nodeId": str}]} 或 {"success": False, "error": str}
        """
        return self._backend.list_docs(skill_name)


# ─── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Skills Memory — 统一存储服务")
    parser.add_argument("--backend", choices=["dingtalk", "dingtalk-drive", "weiyun", "local"], default=None,
                        help="存储后端，默认从环境变量 SM_BACKEND 读取")
    subparsers = parser.add_subparsers(dest="command")

    # find <skill_name> <doc_name>
    find_parser = subparsers.add_parser("find", help="查找文档")
    find_parser.add_argument("skill_name", help="技能名称")
    find_parser.add_argument("doc_name", help="文档名称")

    # create <skill_name> <doc_name> <content>
    create_parser = subparsers.add_parser("create", help="创建文档")
    create_parser.add_argument("skill_name", help="技能名称")
    create_parser.add_argument("doc_name", help="文档名称")
    create_parser.add_argument("content", help="文档内容")

    # read <skill_name> <doc_id>
    read_parser = subparsers.add_parser("read", help="读取文档内容")
    read_parser.add_argument("skill_name", help="技能名称")
    read_parser.add_argument("doc_id", help="文档 ID（钉钉为 nodeId，本地为 doc_name）")

    # write <skill_name> <doc_id> <content>
    write_parser = subparsers.add_parser("write", help="写入文档内容")
    write_parser.add_argument("skill_name", help="技能名称")
    write_parser.add_argument("doc_id", help="文档 ID")
    write_parser.add_argument("content", help="文档内容")

    # delete <skill_name> <doc_id>
    delete_parser = subparsers.add_parser("delete", help="删除文档")
    delete_parser.add_argument("skill_name", help="技能名称")
    delete_parser.add_argument("doc_id", help="文档 ID")

    # list <skill_name>
    list_parser = subparsers.add_parser("list", help="列出技能的所有文档")
    list_parser.add_argument("skill_name", help="技能名称")

    args = parser.parse_args()

    sm = SkillsMemory(backend=args.backend)

    if args.command == "find":
        result = sm.find_doc(args.skill_name, args.doc_name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "create":
        result = sm.create_doc(args.skill_name, args.doc_name, args.content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "read":
        result = sm.read_doc(args.skill_name, args.doc_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "write":
        result = sm.update_doc(args.skill_name, args.doc_id, args.content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "delete":
        result = sm.delete_doc(args.skill_name, args.doc_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "list":
        result = sm.list_docs(args.skill_name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
