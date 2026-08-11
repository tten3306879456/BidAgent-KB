#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ima 云端知识库后端

工作模式:
  1. WorkBuddy 内运行: 通过 ima-mcp 工具操作（create_media/add_knowledge/search_knowledge等）
  2. 独立运行(有限支持): 通过 COS SDK 上传文件，搜索需配合 WorkBuddy

注意:
  - ima 后端的 search 操作需要 MCP 工具支持
  - 独立 Python 脚本只能完成 upload，search 需在 WorkBuddy 对话中由智能体执行
  - 建议配合 ChromaDB 后端使用（双后端模式）

配置(.env 或 kb_config.json):
  IMA_PUBLIC_KB_ID=xxx   # 公共知识库ID(法规标准，社区共享)
  IMA_PRIVATE_KB_ID=xxx  # 私有知识库ID(用户自建)
"""

import os
import json
from pathlib import Path
from datetime import datetime

from kb_backend import KBBackend


class ImaBackend(KBBackend):
    """ima 云端知识库后端"""

    backend_name = "ima"

    def __init__(self, config: dict, full_config: dict = None):
        """
        Args:
            config: ima 配置字典
                - public_kb_id: 公共知识库ID
                - private_kb_id: 私有知识库ID
            full_config: 完整配置
        """
        self.public_kb_id = config.get("public_kb_id", "")
        self.private_kb_id = config.get("private_kb_id", "")
        
        # 优先使用私有库，如果没有则用公共库
        self.kb_id = self.private_kb_id or self.public_kb_id

        self.full_config = full_config or {}
        self._file_index = {}
        self._file_index_path = Path(__file__).parent / "ima_file_index.json"

    def init(self) -> dict:
        """初始化 ima 后端"""
        if not self.kb_id:
            return {
                "success": False,
                "message": (
                    "未配置 ima 知识库 ID。请:\n"
                    "  1. 访问 https://ima.qq.com 创建知识库\n"
                    "  2. 在 .env 文件中设置 IMA_PRIVATE_KB_ID\n"
                    "  3. 或在 kb_config.json 的 backend.ima.private_kb_id 中填入\n"
                    "  4. 重新运行 kb_setup.py"
                )
            }

        # 加载本地文件索引
        self._load_file_index()

        return {
            "success": True,
            "message": (
                f"ima 后端就绪 | 知识库ID: {self.kb_id}\n"
                f"  公共库: {self.public_kb_id or '未配置'}\n"
                f"  私有库: {self.private_kb_id or '未配置'}\n"
                f"  已跟踪文件: {len(self._file_index)}\n"
                f"  注: 搜索/上传需在 WorkBuddy 中通过 MCP 工具执行"
            )
        }

    def is_ready(self) -> bool:
        """检查后端是否就绪"""
        return bool(self.kb_id)

    def search(self, query: str, limit: int = 5) -> list:
        """搜索知识库
        
        注意: 此方法需要 MCP 工具支持。在独立 Python 脚本中无法直接调用。
        在 WorkBuddy 中，智能体会使用 mcp__ima-mcp__search_knowledge 工具。
        
        如果需要独立搜索，请使用 ChromaDB 后端。
        """
        # 输出搜索指令，供 WorkBuddy 智能体使用
        print(f"[ima] 搜索指令: search_knowledge(query='{query}', knowledge_base_id='{self.kb_id}')")
        print(f"[ima] 请在 WorkBuddy 对话中执行此搜索")
        
        return [{
            "content": f"[ima 后端提示] 搜索 '{query}' 需在 WorkBuddy 中通过 MCP 工具执行",
            "source": "ima_backend",
            "score": 0,
            "metadata": {
                "kb_id": self.kb_id,
                "query": query,
                "mcp_tool": "mcp__ima-mcp__search_knowledge",
            }
        }]

    def upload(self, file_path: str, metadata: dict = None) -> dict:
        """上传文件到 ima 知识库
        
        流程: create_media → COS上传 → add_knowledge
        
        在独立 Python 脚本中可完成 COS 上传部分。
        create_media 和 add_knowledge 步骤需要 MCP 工具。
        """
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "message": f"文件不存在: {file_path}"}

        if not self.kb_id:
            return {"success": False, "message": "未配置 ima 知识库 ID"}

        # 生成上传指令供 WorkBuddy 智能体使用
        file_size = path.stat().st_size
        upload_instructions = {
            "file_path": str(path),
            "file_name": path.name,
            "file_size": file_size,
            "file_ext": path.suffix.lstrip("."),
            "content_type": self._get_content_type(path),
            "knowledge_base_id": self.kb_id,
            "metadata": metadata or {},
            "steps": [
                {
                    "step": 1,
                    "tool": "mcp__ima-mcp__create_media",
                    "params": {
                        "knowledge_base_id": self.kb_id,
                        "file_name": path.name,
                        "file_ext": path.suffix.lstrip("."),
                        "content_type": self._get_content_type(path),
                        "file_size": file_size,
                    }
                },
                {
                    "step": 2,
                    "tool": "COS SDK 上传",
                    "params": "使用 create_media 返回的凭证，通过 cos-python-sdk-v5 上传文件"
                },
                {
                    "step": 3,
                    "tool": "mcp__ima-mcp__add_knowledge",
                    "params": {
                        "knowledge_base_id": self.kb_id,
                        "media_id": "（步骤1返回的 media_id）"
                    }
                }
            ]
        }

        # 更新本地文件索引
        self._load_file_index()
        self._file_index[path.name] = {
            "path": str(path),
            "size": file_size,
            "kb_id": self.kb_id,
            "metadata": metadata or {},
            "upload_instructions": upload_instructions,
            "uploaded_at": datetime.now().isoformat(),
        }
        self._save_file_index()

        return {
            "success": True,
            "message": (
                f"文件已准备好上传: {path.name} ({file_size} bytes)\n"
                f"  知识库ID: {self.kb_id}\n"
                f"  上传步骤已记录到 ima_file_index.json\n"
                f"  请在 WorkBuddy 对话中执行上传（智能体会自动读取指令）"
            ),
            "file_id": path.name,
            "upload_instructions": upload_instructions,
        }

    def list_knowledge(self) -> list:
        """列出知识库文件
        
        注意: 实际列表需要 MCP 工具 (get_knowledge_list)。
        此方法返回本地索引中的文件。
        """
        self._load_file_index()
        result = []
        for name, info in self._file_index.items():
            result.append({
                "name": name,
                "size": info.get("size", 0),
                "status": "已记录(待确认ima状态)",
                "added_at": info.get("uploaded_at", ""),
                "kb_id": info.get("kb_id", ""),
            })
        return result

    def import_seed_files(self, seed_dir: str = None, seed_files: list = None) -> dict:
        """批量导入种子文件（生成上传指令）"""
        if seed_dir is None:
            base_path = self.full_config.get("base_path", "D:/KB_manager")
            cloud_seed = self.full_config.get("cloud_seed_dir", "01_云端知识库/种子文件")
            seed_dir = str(Path(base_path) / cloud_seed)

        if seed_files is None:
            seed_files = self.full_config.get("seed_files", [])

        seed_path = Path(seed_dir)
        if not seed_path.exists():
            seed_path = Path(__file__).parent.parent / "知识库种子内容"

        total = len(seed_files)
        success_count = 0
        details = []

        for fname in seed_files:
            fpath = seed_path / fname
            if not fpath.exists():
                details.append({"file": fname, "success": False, "error": "文件不存在"})
                continue

            result = self.upload(str(fpath))
            details.append({
                "file": fname,
                "success": result["success"],
                "message": result["message"],
            })
            if result["success"]:
                success_count += 1

        return {
            "total": total,
            "success": success_count,
            "failed": total - success_count,
            "details": details,
        }

    def _get_content_type(self, path: Path) -> str:
        """根据扩展名获取 Content-Type"""
        ct_map = {
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }
        return ct_map.get(path.suffix.lower(), "application/octet-stream")

    def _load_file_index(self):
        """加载文件索引"""
        if self._file_index_path.exists():
            with open(self._file_index_path, "r", encoding="utf-8") as f:
                self._file_index = json.load(f)
        else:
            self._file_index = {}

    def _save_file_index(self):
        """保存文件索引"""
        self._file_index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file_index_path, "w", encoding="utf-8") as f:
            json.dump(self._file_index, f, ensure_ascii=False, indent=2)

    def get_info(self) -> dict:
        info = super().get_info()
        info.update({
            "public_kb_id": self.public_kb_id,
            "private_kb_id": self.private_kb_id,
            "active_kb_id": self.kb_id,
            "web_url": "https://ima.qq.com",
            "tracked_files": len(self._file_index),
        })
        return info


if __name__ == "__main__":
    print("=== ima 后端自测 ===\n")

    # 测试无配置的情况
    backend = ImaBackend({"public_kb_id": "", "private_kb_id": ""})
    result = backend.init()
    print(f"无配置初始化: {result['message'][:100]}")

    # 测试有配置的情况
    backend2 = ImaBackend({
        "public_kb_id": "test_public_001",
        "private_kb_id": "test_private_002",
    })
    result2 = backend2.init()
    print(f"\n有配置初始化: {result2['message']}")
