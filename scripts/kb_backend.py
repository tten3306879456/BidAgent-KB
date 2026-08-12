#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KB 后端抽象层 — 统一知识库接口
支持 ima 云端后端和 ChromaDB 本地向量库后端

使用方式:
    from kb_backend import create_backend
    kb = create_backend(config)
    results = kb.search("废标条款 资质不符")
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import json


class KBBackend(ABC):
    """知识库后端抽象基类"""

    backend_name: str = "abstract"

    @abstractmethod
    def init(self) -> dict:
        """初始化后端（创建知识库/目录/集合等）
        Returns: {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list:
        """搜索知识库
        Args:
            query: 搜索关键词
            limit: 返回结果数量上限
        Returns: [{"content": str, "source": str, "score": float, "metadata": dict}]
        """
        pass

    @abstractmethod
    def upload(self, file_path: str, metadata: dict = None) -> dict:
        """上传文件到知识库
        Args:
            file_path: 文件路径
            metadata: 额外元数据 {"category": str, "tags": list}
        Returns: {"success": bool, "message": str, "file_id": str}
        """
        pass

    @abstractmethod
    def list_knowledge(self) -> list:
        """列出知识库中的所有文件
        Returns: [{"name": str, "size": int, "status": str, "added_at": str}]
        """
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """检查后端是否就绪可用"""
        pass

    def import_url(self, url: str, metadata: dict = None) -> dict:
        """导入网页URL到知识库（ima后端支持，ChromaDB默认不支持）
        Returns: {"success": bool, "message": str}
        """
        return {"success": False, "message": f"{self.backend_name} 后端不支持URL导入"}

    def delete(self, file_id: str) -> dict:
        """删除知识库中的文件（部分后端支持）
        Returns: {"success": bool, "message": str}
        """
        return {"success": False, "message": f"{self.backend_name} 后端不支持删除"}

    def get_info(self) -> dict:
        """获取后端信息"""
        return {
            "backend": self.backend_name,
            "ready": self.is_ready(),
        }


def load_config(config_path: str = None) -> dict:
    """加载知识库配置
    
    查找顺序:
    1. 指定的 config_path
    2. 项目根目录的 kb_config.json（完整配置）
    3. 脚本同目录下的 kb_config.json（setup_wizard 生成的最小配置）
    4. 环境变量 KB_CONFIG_PATH 指定的路径
    5. ./kb_data/kb_config.json
    """
    import os

    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    
    # 优先从项目根目录加载（完整配置）
    project_root = Path(__file__).parent.parent
    candidates.append(project_root / "kb_config.json")
    
    script_dir = Path(__file__).parent
    candidates.append(script_dir / "kb_config.json")
    
    env_path = os.environ.get("KB_CONFIG_PATH")
    if env_path:
        candidates.append(Path(env_path))
    
    candidates.append(Path("./kb_data/kb_config.json"))

    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)

    # 返回默认配置
    return {
        "backend": {
            "type": "local_search",
            "local_search": {
                "context_chars": 200,
                "max_results": 10,
                "description": "轻量级本地全文检索，零依赖"
            },
        }
    }


def create_backend(config: dict = None, config_path: str = None) -> KBBackend:
    """根据配置创建后端实例（工厂方法）
    
    Args:
        config: 配置字典（如果提供则直接使用）
        config_path: 配置文件路径（如果config未提供，则从此路径加载）
    
    Returns:
        KBBackend 实例
    
    Raises:
        ValueError: 不支持的后端类型
    """
    if config is None:
        config = load_config(config_path)

    backend_cfg = config.get("backend", {})
    backend_type = backend_cfg.get("type", "chromadb")

    if backend_type == "local_search":
        from kb_local_search import LocalSearchBackend
        local_cfg = backend_cfg.get("local_search", {})
        return LocalSearchBackend(local_cfg, config)

    elif backend_type == "chromadb":
        from kb_chromadb import ChromaDBBackend
        chroma_cfg = backend_cfg.get("chromadb", {})
        return ChromaDBBackend(chroma_cfg, config)

    elif backend_type == "ima":
        from kb_ima import ImaBackend
        ima_cfg = backend_cfg.get("ima", {})
        return ImaBackend(ima_cfg, config)

    elif backend_type == "both":
        # 双后端模式：ima云端 + local_search本地
        from kb_local_search import LocalSearchBackend
        from kb_ima import ImaBackend
        ima_cfg = backend_cfg.get("ima", {})
        local_cfg = backend_cfg.get("local_search", {})
        # v2.0: 优先 ima（检查 shared_kbs 而非 private_kb_id/public_kb_id），本地作为 fallback
        if ima_cfg.get("shared_kbs") or ima_cfg.get("private_kb_id") or ima_cfg.get("public_kb_id"):
            return ImaBackend(ima_cfg, config)
        else:
            return LocalSearchBackend(local_cfg, config)

    else:
        raise ValueError(f"不支持的后端类型: {backend_type}，请使用 'local_search', 'chromadb', 'ima' 或 'both'")


if __name__ == "__main__":
    # 自测
    print("=== KB 后端抽象层自测 ===\n")
    
    config = load_config()
    backend_type = config.get("backend", {}).get("type", "未配置")
    print(f"配置文件中的后端类型: {backend_type}")
    
    try:
        kb = create_backend(config)
        print(f"后端创建成功: {kb.backend_name}")
        print(f"就绪状态: {kb.is_ready()}")
        info = kb.get_info()
        print(f"后端信息: {json.dumps(info, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"后端创建失败: {e}")
        print("\n提示: 如果是 ChromaDB 后端，请先安装依赖: pip install chromadb sentence-transformers")
