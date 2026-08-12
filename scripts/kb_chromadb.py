#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChromaDB 本地向量知识库后端

特性:
- 无需云端账号，完全本地运行
- 使用 sentence-transformers 本地嵌入模型 (默认 BAAI/bge-large-zh-v1.5)
- 支持 Markdown / PDF / TXT / Word 文件上传
- 文档自动分块(chunk) + 向量化 + 存储
- 语义搜索(非关键词匹配)，更智能
- 数据持久化到本地磁盘

依赖:
    pip install chromadb sentence-transformers PyPDF2

嵌入模型说明:
    - 默认: BAAI/bge-large-zh-v1.5 (~1.3GB, 中文优化, 1024维)
    - 轻量: sentence-transformers/all-MiniLM-L6-v2 (~90MB, 多语言, 384维)
    - 首次使用时自动从 HuggingFace 下载模型并缓存到本地
    - 切换模型后需删除旧 chroma_db 目录重新索引 (向量维度不同)

使用方式:
    from kb_chromadb import ChromaDBBackend
    backend = ChromaDBBackend({
        "persist_directory": "./chroma_db",
        "collection_name": "bid_assistant_kb",
        "embedding_model": "BAAI/bge-large-zh-v1.5",
    })
    backend.init()
    backend.upload("废标条款模式库_种子版.md")
    results = backend.search("资质不符废标")
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

from kb_backend import KBBackend


class ChromaDBBackend(KBBackend):
    """ChromaDB 本地向量知识库后端"""

    backend_name = "chromadb"

    def __init__(self, config: dict, full_config: dict = None):
        """
        Args:
            config: chromadb 配置字典
            full_config: 完整配置（用于查找种子文件路径等）
        """
        self.persist_dir = Path(config.get(
            "persist_directory",
            str(Path(__file__).parent / "chroma_db")
        ))
        self.collection_name = config.get("collection_name", "bid_assistant_kb")
        self.embedding_model = config.get("embedding_model", "BAAI/bge-large-zh-v1.5")
        self.chunk_size = config.get("chunk_size", 500)
        self.chunk_overlap = config.get("chunk_overlap", 50)

        self._client = None
        self._collection = None
        self._file_index_path = self.persist_dir / "file_index.json"
        self._file_index = {}

        # 完整配置（用于查找种子文件等）
        self.full_config = full_config or {}

    def _get_client(self):
        """懒加载 ChromaDB 客户端"""
        if self._client is None:
            import chromadb
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        return self._client

    def _get_embedding_function(self):
        """根据配置创建 ChromaDB 嵌入函数
        
        使用 sentence-transformers 作为后端，支持 HuggingFace 上的任意模型。
        首次调用时自动下载模型并缓存到 ~/.cache/huggingface/hub/
        
        Returns:
            ChromaDB EmbeddingFunction 实例
        """
        from chromadb.utils import embedding_functions

        model_name = self.embedding_model

        # 自动补全 HuggingFace 模型路径
        # 用户可能写 "bge-large-zh-v1.5" 或 "all-MiniLM-L6-v2" 等简写
        if "/" not in model_name:
            model_map = {
                "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
                "all-MiniLM-L12-v2": "sentence-transformers/all-MiniLM-L12-v2",
                "paraphrase-multilingual-MiniLM-L12-v2": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
                "bge-base-zh-v1.5": "BAAI/bge-base-zh-v1.5",
                "bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5",
                "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
                "m3e-base": "moka-ai/m3e-base",
                "m3e-large": "moka-ai/m3e-large",
            }
            model_name = model_map.get(model_name, f"sentence-transformers/{model_name}")

        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )

    def _get_collection(self):
        """懒加载 Collection
        
        根据配置的 embedding_model 创建嵌入函数并传入 Collection。
        注意: 切换嵌入模型后，向量维度会变化（如 384→1024），
        需删除旧 chroma_db 目录后重新索引。
        """
        if self._collection is None:
            client = self._get_client()
            embedding_function = self._get_embedding_function()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=embedding_function,
                metadata={"description": "标书智能体知识库"}
            )
        return self._collection

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

    def init(self) -> dict:
        """初始化 ChromaDB 后端"""
        try:
            # 检查依赖
            import chromadb
            import sentence_transformers
        except ImportError as e:
            missing = []
            try:
                import chromadb
            except ImportError:
                missing.append("chromadb")
            try:
                import sentence_transformers
            except ImportError:
                missing.append("sentence-transformers")
            return {
                "success": False,
                "message": f"缺少依赖: {' '.join(missing)}，请运行: pip install {' '.join(missing)}"
            }

        try:
            # 创建持久化目录
            self.persist_dir.mkdir(parents=True, exist_ok=True)

            # 初始化集合（会触发嵌入函数创建和模型下载）
            try:
                client = self._get_client()
                self._get_collection()
            except Exception as e:
                # 常见: 切换嵌入模型后向量维度不匹配
                err_msg = str(e)
                if "dimension" in err_msg.lower() or "embedding" in err_msg.lower():
                    return {
                        "success": False,
                        "message": (
                            f"嵌入模型切换导致维度不匹配: {e}\n"
                            f"请删除旧向量库目录后重新初始化:\n"
                            f"  rm -rf {self.persist_dir}\n"
                            f"  python kb_init.py --backend chromadb"
                        )
                    }
                raise

            # 加载文件索引
            self._load_file_index()

            file_count = len(self._file_index)
            chunk_count = self._collection.count() if self._collection else 0

            return {
                "success": True,
                "message": f"ChromaDB 初始化成功 | 目录: {self.persist_dir} | "
                           f"嵌入模型: {self.embedding_model} | "
                           f"文件数: {file_count} | 文档块: {chunk_count}"
            }
        except Exception as e:
            return {"success": False, "message": f"初始化失败: {e}"}

    def is_ready(self) -> bool:
        """检查后端是否就绪"""
        try:
            self._get_collection()
            return True
        except Exception:
            return False

    def _extract_text(self, file_path: str) -> str:
        """从文件中提取文本内容
        
        支持: .md, .txt, .pdf
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix in (".md", ".txt"):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        elif suffix == ".pdf":
            from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            texts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
            return "\n\n".join(texts)

        elif suffix in (".docx", ".doc"):
            try:
                from docx import Document
                doc = Document(str(path))
                return "\n\n".join([para.text for para in doc.paragraphs if para.text])
            except ImportError:
                return f"[需要安装 python-docx 才能解析 Word 文件: {path.name}]"

        else:
            # 尝试以文本方式读取
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return ""

    def _chunk_text(self, text: str) -> list:
        """将文本分块
        
        策略:
        1. 按段落(双换行)分割
        2. 超长段落按 chunk_size 字符分割
        3. 相邻块之间有 chunk_overlap 字符重叠
        """
        if not text.strip():
            return []

        # 按段落分割
        paragraphs = text.split("\n\n")
        
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果段落本身就很长，需要进一步分割
            if len(para) > self.chunk_size:
                # 先保存当前累积的块
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""

                # 分割长段落
                for i in range(0, len(para), self.chunk_size - self.chunk_overlap):
                    chunk = para[i:i + self.chunk_size]
                    if len(chunk) > 50:  # 过滤太短的块
                        chunks.append(chunk)
            else:
                # 短段落，尝试合并
                if len(current_chunk) + len(para) + 2 > self.chunk_size:
                    # 当前块已满，保存并开始新块
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = para
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para

        # 保存最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def upload(self, file_path: str, metadata: dict = None) -> dict:
        """上传文件到 ChromaDB
        
        流程: 提取文本 → 分块 → 嵌入 → 存储
        """
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "message": f"文件不存在: {file_path}"}

        try:
            collection = self._get_collection()
            self._load_file_index()

            # 检查是否已上传过
            file_hash = self._compute_file_hash(path)
            file_key = path.name

            if file_key in self._file_index:
                old_hash = self._file_index[file_key].get("hash")
                if old_hash == file_hash:
                    return {"success": True, "message": f"文件未变化，跳过: {file_key}", "file_id": file_key}

                # 文件有更新，先删除旧块
                self._delete_file_chunks(file_key)

            # 提取文本
            text = self._extract_text(str(path))
            if not text.strip():
                return {"success": False, "message": f"无法从文件中提取文本: {file_key}"}

            # 分块
            chunks = self._chunk_text(text)

            if not chunks:
                return {"success": False, "message": f"文本分块结果为空: {file_key}"}

            # 准备元数据
            meta = metadata or {}
            category = meta.get("category", "未分类")
            tags = meta.get("tags", [])

            # 生成唯一ID和元数据
            ids = []
            documents = []
            metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_key}_{i:04d}_{file_hash[:8]}"
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({
                    "source": file_key,
                    "file_path": str(path),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "category": category,
                    "tags": ",".join(tags) if tags else "",
                    "file_hash": file_hash,
                    "uploaded_at": datetime.now().isoformat(),
                })

            # 批量写入 ChromaDB
            batch_size = 100
            for start in range(0, len(ids), batch_size):
                end = start + batch_size
                collection.upsert(
                    ids=ids[start:end],
                    documents=documents[start:end],
                    metadatas=metadatas[start:end],
                )

            # 更新文件索引
            self._file_index[file_key] = {
                "hash": file_hash,
                "path": str(path),
                "size": path.stat().st_size,
                "chunks": len(chunks),
                "category": category,
                "tags": tags,
                "uploaded_at": datetime.now().isoformat(),
            }
            self._save_file_index()

            return {
                "success": True,
                "message": f"上传成功: {file_key} | 分块: {len(chunks)} | 类别: {category}",
                "file_id": file_key,
            }

        except Exception as e:
            return {"success": False, "message": f"上传失败: {e}"}

    def search(self, query: str, limit: int = 5) -> list:
        """语义搜索知识库"""
        try:
            collection = self._get_collection()
            results = collection.query(
                query_texts=[query],
                n_results=limit,
            )

            # 格式化结果
            output = []
            if results and results.get("documents"):
                docs = results["documents"][0]
                metas = results.get("metadatas", [[]])[0]
                dists = results.get("distances", [[]])[0]

                for i, doc in enumerate(docs):
                    meta = metas[i] if i < len(metas) else {}
                    dist = dists[i] if i < len(dists) else 0
                    # ChromaDB 返回的是距离(distance)，越小越相似
                    # 转换为相似度分数: 1 - distance (clamp 0~1)
                    score = max(0, 1 - dist)
                    output.append({
                        "content": doc,
                        "source": meta.get("source", "未知"),
                        "score": round(score, 4),
                        "metadata": meta,
                    })

            return output

        except Exception as e:
            print(f"搜索失败: {e}")
            return []

    def list_knowledge(self) -> list:
        """列出知识库中的所有文件"""
        self._load_file_index()
        
        result = []
        for name, info in self._file_index.items():
            result.append({
                "name": name,
                "size": info.get("size", 0),
                "status": "已索引",
                "added_at": info.get("uploaded_at", ""),
                "chunks": info.get("chunks", 0),
                "category": info.get("category", "未分类"),
                "hash": info.get("hash", "")[:8],
            })

        return result

    def delete(self, file_id: str) -> dict:
        """删除知识库中的文件"""
        try:
            self._load_file_index()
            
            if file_id not in self._file_index:
                return {"success": False, "message": f"文件不存在: {file_id}"}

            self._delete_file_chunks(file_id)

            del self._file_index[file_id]
            self._save_file_index()

            return {"success": True, "message": f"已删除: {file_id}"}

        except Exception as e:
            return {"success": False, "message": f"删除失败: {e}"}

    def _delete_file_chunks(self, file_name: str):
        """删除指定文件的所有文档块"""
        collection = self._get_collection()
        
        # 获取该文件的所有 chunk ID
        try:
            results = collection.get(
                where={"source": file_name}
            )
            if results and results.get("ids"):
                collection.delete(ids=results["ids"])
        except Exception:
            pass  # 文件可能还没有 chunk

    def _compute_file_hash(self, path: Path) -> str:
        """计算文件 MD5 哈希"""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_info(self) -> dict:
        """获取后端详细信息"""
        info = super().get_info()
        self._load_file_index()
        
        chunk_count = 0
        try:
            collection = self._get_collection()
            chunk_count = collection.count()
        except Exception:
            pass

        info.update({
            "persist_directory": str(self.persist_dir),
            "collection_name": self.collection_name,
            "embedding_model": self.embedding_model,
            "file_count": len(self._file_index),
            "chunk_count": chunk_count,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        })
        return info

    def import_seed_files(self, seed_dir: str = None, seed_files: list = None) -> dict:
        """批量导入种子文件
        
        Args:
            seed_dir: 种子文件目录
            seed_files: 种子文件名列表（如果未提供则扫描目录）
        
        Returns:
            {"total": int, "success": int, "failed": int, "details": list}
        """
        # 从配置中获取种子文件目录和列表
        if seed_dir is None:
            base_path = self.full_config.get("base_path", "./kb_data")
            cloud_seed = self.full_config.get("cloud_seed_dir", "01_云端知识库/种子文件")
            seed_dir = str(Path(base_path) / cloud_seed)

        if seed_files is None:
            seed_files = self.full_config.get("seed_files", [])

        seed_path = Path(seed_dir)
        if not seed_path.exists():
            return {"total": 0, "success": 0, "failed": 0, "details": [{"error": f"种子目录不存在: {seed_dir}"}]}

        # 如果未提供文件列表，扫描目录
        if not seed_files:
            seed_files = [f.name for f in seed_path.glob("*.md")]

        # 类别映射（根据文件名自动判断）
        category_map = {
            "废标条款": "废标条款识别",
            "法规": "招投标法律法规",
            "标准": "行业技术标准",
            "报价": "报价与商务法规",
            "商务": "报价与商务法规",
            "资质": "资质等效替代",
        }

        total = len(seed_files)
        success_count = 0
        failed_count = 0
        details = []

        for fname in seed_files:
            fpath = seed_path / fname
            if not fpath.exists():
                # 尝试在脚本目录上级找
                script_seed = Path(__file__).parent.parent / "seeds" / fname
                if script_seed.exists():
                    fpath = script_seed
                else:
                    details.append({"file": fname, "success": False, "error": "文件不存在"})
                    failed_count += 1
                    continue

            # 自动分类
            category = "未分类"
            for keyword, cat in category_map.items():
                if keyword in fname:
                    category = cat
                    break

            result = self.upload(str(fpath), metadata={"category": category})
            details.append({"file": fname, "success": result["success"], "message": result["message"], "category": category})

            if result["success"]:
                success_count += 1
            else:
                failed_count += 1

        return {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "details": details,
        }


if __name__ == "__main__":
    # 自测
    import sys

    print("=== ChromaDB 后端自测 ===\n")

    backend = ChromaDBBackend({
        "persist_directory": str(Path(__file__).parent / "chroma_db"),
        "collection_name": "bid_assistant_kb",
        "embedding_model": "BAAI/bge-large-zh-v1.5",
        "chunk_size": 500,
        "chunk_overlap": 50,
    })

    # 初始化
    result = backend.init()
    print(f"初始化: {result}")

    if not result["success"]:
        print("\n请先安装依赖:")
        print("  pip install chromadb sentence-transformers PyPDF2")
        sys.exit(1)

    # 尝试导入种子文件
    print("\n--- 导入种子文件 ---")
    seed_dir = str(Path(__file__).parent.parent / "seeds")
    if Path(seed_dir).exists():
        import_result = backend.import_seed_files(seed_dir=seed_dir)
        print(f"导入结果: 成功 {import_result['success']}/{import_result['total']}")
        for d in import_result["details"]:
            status = "✅" if d["success"] else "❌"
            print(f"  {status} {d['file']} — {d.get('category', '')} — {d.get('message', d.get('error', ''))}")
    else:
        print(f"种子目录不存在: {seed_dir}")
        print("请先运行 kb_init.py 创建目录结构")

    # 列出知识库
    print("\n--- 知识库文件列表 ---")
    files = backend.list_knowledge()
    for f in files:
        print(f"  {f['name']} | {f['chunks']} 块 | {f['category']} | {f['hash']}")

    # 搜索测试
    print("\n--- 搜索测试 ---")
    for query in ["废标条款 资质不符", "等保2.0 网络安全", "报价 低于成本价", "资质替代 CMMI"]:
        results = backend.search(query, limit=2)
        print(f"\n搜索: {query}")
        for r in results:
            print(f"  [{r['score']:.2f}] {r['source']}: {r['content'][:80]}...")

    # 后端信息
    print(f"\n--- 后端信息 ---")
    print(json.dumps(backend.get_info(), ensure_ascii=False, indent=2))
