#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ima 云端知识库后端 (v2.1 — 支持 6 座共享知识库)

工作模式:
  1. WorkBuddy 内运行: 通过 ima-mcp 工具操作（create_media/add_knowledge/search_knowledge等）
  2. 独立运行(有限支持): 通过 COS SDK 上传文件，搜索需配合 WorkBuddy

注意:
  - ima 后端的 search 操作需要 MCP 工具支持
  - 独立 Python 脚本只能完成 upload，search 需在 WorkBuddy 对话中由智能体执行
  - 建议配合 ChromaDB 后端使用（双后端模式）

配置(kb_config.json):
  backend.ima.shared_kbs = {
    "标书法规库": "7493174142445773",
    "标书案例库": "7493174285050353",
    "投标文件编辑模板库": "7493174465429392",
    "核工业标书知识库": "7493159651146811",
    "软件开发标书知识库": "7493159953137267",
    "设备采购知识库": "7493501189104652"
  }
  backend.ima.public_kb_id  = ""  (兼容旧配置，不再主要使用)
  backend.ima.private_kb_id = ""  (兼容旧配置，不再主要使用)
"""

import os
import json
from pathlib import Path
from datetime import datetime

from kb_backend import KBBackend


class ImaBackend(KBBackend):
    """ima 云端知识库后端 (v2.1 — 6 座共享知识库多 KB 路由)"""

    backend_name = "ima"

    def __init__(self, config: dict, full_config: dict = None):
        """
        Args:
            config: ima 配置字典
                - shared_kbs: dict[str, str]  共享知识库名称→ID 映射
                - public_kb_id: str           (兼容旧配置)
                - private_kb_id: str          (兼容旧配置)
            full_config: 完整配置（用于读取 shared_content.categories 做文件→KB 映射）
        """
        # 6 座共享知识库: {名称: KB_ID}
        self.shared_kbs: dict = config.get("shared_kbs", {})

        # 兼容旧配置
        self.public_kb_id = config.get("public_kb_id", "")
        self.private_kb_id = config.get("private_kb_id", "")

        # 默认 KB: 取 shared_kbs 第一个（或私有库兼容）
        self.default_kb_id = (
            list(self.shared_kbs.values())[0] if self.shared_kbs
            else self.private_kb_id or self.public_kb_id
        )

        # 反向映射: KB_ID → 名称
        self.kb_id_to_name = {v: k for k, v in self.shared_kbs.items()}

        # 文件 → KB 映射表（从 shared_content.categories 构建）
        self.file_to_kb: dict = {}
        self.full_config = full_config or {}
        self._build_file_to_kb_map()

        self._file_index = {}
        self._file_index_path = Path(__file__).parent / "ima_file_index.json"

    def _build_file_to_kb_map(self):
        """从 config.shared_content.categories 构建 {文件名: (kb_name, kb_id)} 映射"""
        categories = self.full_config.get("shared_content", {}).get("categories", {})
        for cat_id, cat in categories.items():
            kb_name = cat.get("name", cat_id)
            kb_id = cat.get("kb_id", "")
            for f in cat.get("files", []):
                self.file_to_kb[f] = (kb_name, kb_id)

    # --------------------------------------------------------
    # KB 路由辅助
    # --------------------------------------------------------
    def resolve_kb(self, kb_name: str = None, file_name: str = None) -> str:
        """解析出目标 KB ID

        优先级:
          1. kb_name 直接匹配 shared_kbs 名称或 ID
          2. file_name 在 file_to_kb 映射中查找
          3. self.default_kb_id
        """
        if kb_name:
            # 是名称？
            if kb_name in self.shared_kbs:
                return self.shared_kbs[kb_name]
            # 是 ID？
            if kb_name in self.kb_id_to_name:
                return kb_name

        if file_name and file_name in self.file_to_kb:
            return self.file_to_kb[file_name][1]

        return self.default_kb_id

    # --------------------------------------------------------
    # KBBackend 抽象方法实现
    # --------------------------------------------------------
    def init(self) -> dict:
        """初始化 ima 后端"""
        if not self.shared_kbs and not self.default_kb_id:
            return {
                "success": False,
                "message": (
                    "未配置 ima 共享知识库。请:\n"
                    "  1. 访问 https://ima.qq.com 创建知识库\n"
                    "  2. 在 kb_config.json 的 backend.ima.shared_kbs 中填入各 KB ID\n"
                    "  3. 重新运行 kb_setup.py"
                )
            }

        self._load_file_index()

        # 构建库列表
        kb_lines = []
        for name, kb_id in self.shared_kbs.items():
            tracked = sum(1 for v in self._file_index.values() if v.get("kb_id") == kb_id)
            kb_lines.append(f"    {name}: {kb_id} ({tracked} 文件)")
        kb_list_str = "\n".join(kb_lines) if kb_lines else "    (无共享库配置)"

        return {
            "success": True,
            "message": (
                f"ima 后端就绪 (v2.0 多 KB 路由)\n"
                f"  共享知识库 ({len(self.shared_kbs)} 座):\n"
                f"{kb_list_str}\n"
                f"  默认 KB: {self.default_kb_id or '未配置'}\n"
                f"  已跟踪文件: {len(self._file_index)}\n"
                f"  文件→KB 映射: {len(self.file_to_kb)} 条\n"
                f"  注: 搜索/上传需在 WorkBuddy 中通过 MCP 工具执行"
            )
        }

    def is_ready(self) -> bool:
        """检查后端是否就绪"""
        return bool(self.shared_kbs or self.default_kb_id)

    def search(self, query: str, limit: int = 5, kb_name: str = None) -> list:
        """搜索知识库

        Args:
            query: 搜索关键词
            limit: 返回结果数量上限
            kb_name: 指定知识库名称（如 "标书法规库"），None=搜索所有库

        注意: 此方法需要 MCP 工具支持。在独立 Python 脚本中无法直接调用。
        在 WorkBuddy 中，智能体会使用 mcp__ima-mcp__search_knowledge 工具。
        """
        if kb_name and kb_name in self.shared_kbs:
            kb_id = self.shared_kbs[kb_name]
            print(f"[ima] 搜索指令: search_knowledge(query='{query}', knowledge_base_id='{kb_id}')")
            print(f"[ima] 目标库: {kb_name} ({kb_id})")
        elif self.shared_kbs:
            # 搜索所有库
            print(f"[ima] 搜索指令（全库）: 对以下 {len(self.shared_kbs)} 座 KB 分别执行 search_knowledge:")
            for name, kb_id in self.shared_kbs.items():
                print(f"    {name}: search_knowledge(query='{query}', knowledge_base_id='{kb_id}')")
            kb_id = list(self.shared_kbs.values())
        else:
            kb_id = self.default_kb_id
            print(f"[ima] 搜索指令: search_knowledge(query='{query}', knowledge_base_id='{kb_id}')")

        print(f"[ima] 请在 WorkBuddy 对话中执行此搜索")

        return [{
            "content": f"[ima 后端提示] 搜索 '{query}' 需在 WorkBuddy 中通过 MCP 工具执行",
            "source": "ima_backend",
            "score": 0,
            "metadata": {
                "kb_id": kb_id,
                "kb_name": kb_name,
                "query": query,
                "mcp_tool": "mcp__ima-mcp__search_knowledge",
            }
        }]

    def upload(self, file_path: str, metadata: dict = None, kb_name: str = None) -> dict:
        """上传文件到 ima 知识库

        流程: create_media → COS上传 → add_knowledge

        Args:
            file_path: 文件路径
            metadata: 额外元数据
            kb_name: 目标知识库名称（如 "标书法规库"），None=自动从文件名映射
        """
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "message": f"文件不存在: {file_path}"}

        # 路由到正确的 KB
        kb_id = self.resolve_kb(kb_name, path.name)
        if not kb_id:
            return {"success": False, "message": "无法确定目标知识库 ID，请指定 kb_name 或检查配置"}

        kb_display = self.kb_id_to_name.get(kb_id, "未知")

        file_size = path.stat().st_size
        upload_instructions = {
            "file_path": str(path),
            "file_name": path.name,
            "file_size": file_size,
            "file_ext": path.suffix.lstrip("."),
            "content_type": self._get_content_type(path),
            "knowledge_base_id": kb_id,
            "kb_name": kb_display,
            "metadata": metadata or {},
            "steps": [
                {
                    "step": 1,
                    "tool": "mcp__ima-mcp__create_media",
                    "params": {
                        "knowledge_base_id": kb_id,
                        "file_name": path.name,
                        "file_ext": path.suffix.lstrip("."),
                        "content_type": self._get_content_type(path),
                        "file_size": file_size,
                    }
                },
                {
                    "step": 2,
                    "tool": "COS SDK 上传",
                    "params": "使用 create_media 返回的凭证，通过 cos-python-sdk-v5 或 cos_upload.py 上传文件"
                },
                {
                    "step": 3,
                    "tool": "mcp__ima-mcp__add_knowledge",
                    "params": {
                        "knowledge_base_id": kb_id,
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
            "kb_id": kb_id,
            "kb_name": kb_display,
            "metadata": metadata or {},
            "upload_instructions": upload_instructions,
            "uploaded_at": datetime.now().isoformat(),
        }
        self._save_file_index()

        return {
            "success": True,
            "message": (
                f"文件已准备好上传: {path.name} ({file_size} bytes)\n"
                f"  目标知识库: {kb_display} ({kb_id})\n"
                f"  上传步骤已记录到 ima_file_index.json\n"
                f"  请在 WorkBuddy 对话中执行上传（智能体会自动读取指令）"
            ),
            "file_id": path.name,
            "kb_id": kb_id,
            "kb_name": kb_display,
            "upload_instructions": upload_instructions,
        }

    def list_knowledge(self, kb_name: str = None) -> list:
        """列出知识库文件

        Args:
            kb_name: 指定知识库名称，None=列出所有库的文件

        注意: 实际列表需要 MCP 工具 (get_knowledge_list)。
        此方法返回本地索引中的文件。
        """
        self._load_file_index()
        result = []
        for name, info in self._file_index.items():
            if kb_name and info.get("kb_name") != kb_name:
                continue
            result.append({
                "name": name,
                "size": info.get("size", 0),
                "status": "已记录(待确认ima状态)",
                "added_at": info.get("uploaded_at", ""),
                "kb_id": info.get("kb_id", ""),
                "kb_name": info.get("kb_name", ""),
            })
        return result

    def import_seed_files(self, seed_dir: str = None, seed_files: list = None) -> dict:
        """批量导入种子文件（按文件名自动路由到对应 KB）"""
        if seed_dir is None:
            seed_dir = str(Path(__file__).parent.parent / "seeds")

        if seed_files is None:
            seed_files = self.full_config.get("seed_files", [])

        seed_path = Path(seed_dir)
        if not seed_path.exists():
            # 尝试其他路径
            alt = Path(__file__).parent.parent / "seeds"
            if alt.exists():
                seed_path = alt
            else:
                seed_path = Path(__file__).parent.parent / "seeds"

        total = len(seed_files)
        success_count = 0
        details = []

        for fname in seed_files:
            fpath = seed_path / fname
            if not fpath.exists():
                details.append({"file": fname, "success": False, "error": "文件不存在"})
                continue

            # 自动路由
            kb_name = self.file_to_kb.get(fname, (None, None))[0]
            result = self.upload(str(fpath), kb_name=kb_name)
            details.append({
                "file": fname,
                "success": result["success"],
                "kb_name": result.get("kb_name", ""),
                "kb_id": result.get("kb_id", ""),
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

    # --------------------------------------------------------
    # 工具方法
    # --------------------------------------------------------
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
            "shared_kbs": self.shared_kbs,
            "shared_kb_count": len(self.shared_kbs),
            "default_kb_id": self.default_kb_id,
            "public_kb_id": self.public_kb_id,
            "private_kb_id": self.private_kb_id,
            "file_to_kb_mappings": len(self.file_to_kb),
            "web_url": "https://ima.qq.com",
            "tracked_files": len(self._file_index),
        })
        return info


if __name__ == "__main__":
    print("=== ima 后端 v2.1 自测 ===\n")

    # 测试无配置的情况
    backend = ImaBackend({"shared_kbs": {}, "public_kb_id": "", "private_kb_id": ""})
    result = backend.init()
    print(f"无配置初始化: {result['message'][:100]}")

    # 测试有配置的情况
    backend2 = ImaBackend({
        "shared_kbs": {
            "标书法规库": "7493174142445773",
            "标书案例库": "7493174285050353",
            "投标文件编辑模板库": "7493174465429392",
            "核工业标书知识库": "7493159651146811",
            "软件开发标书知识库": "7493159953137267",
            "设备采购知识库": "7493501189104652",
        },
        "public_kb_id": "",
        "private_kb_id": "",
    }, full_config={
        "shared_content": {
            "categories": {
                "legal_regulations": {
                    "name": "标书法规库",
                    "kb_id": "7493174142445773",
                    "files": ["标书核心法规汇编_v1.0.md"],
                }
            }
        }
    })
    result2 = backend2.init()
    print(f"\n有配置初始化:\n{result2['message']}")

    # 测试路由
    print(f"\n路由测试:")
    print(f"  resolve_kb(kb_name='标书法规库') = {backend2.resolve_kb(kb_name='标书法规库')}")
    print(f"  resolve_kb(file_name='标书核心法规汇编_v1.0.md') = {backend2.resolve_kb(file_name='标书核心法规汇编_v1.0.md')}")
    print(f"  resolve_kb() = {backend2.resolve_kb()}")
