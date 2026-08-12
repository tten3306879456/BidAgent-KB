#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KB 本地文件检索后端 — 轻量级，零依赖

使用 Python 内置 re 模块实现全文检索，无需安装任何外部依赖。
支持 MD/TXT 文件直接索引，PDF/Word 需要可选安装 PyPDF2/python-docx。

特点:
  - 零安装：只需要 Python 标准库
  - 零下载：不需要模型文件
  - 零配置：自动扫描种子目录
  - 关键词高亮 + 摘要预览
  - 文件变更检测（MD5哈希）

使用方式:
    from kb_local_search import LocalSearchBackend
    kb = LocalSearchBackend({}, full_config)
    kb.init()
    results = kb.search("废标条款 资质不符")
"""

import re
import os
import hashlib
import json
from pathlib import Path
from datetime import datetime

# 尝试导入 PDF 读取库（可选）
try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

# 尝试导入 Word 读取库（可选）
try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


class LocalSearchBackend:
    """本地文件全文检索后端（轻量级）"""

    backend_name = "local_search"

    def __init__(self, backend_cfg: dict, full_config: dict = None):
        self.full_config = full_config or {}
        self.backend_cfg = backend_cfg or {}

        # 根目录：优先用 backend 配置，其次用 full_config 的 base_path
        base_path = self.full_config.get("base_path", "")
        cloud_seed_dir = self.full_config.get("cloud_seed_dir", "01_云端知识库/种子文件").replace("\\", "/")

        if base_path:
            self.index_dir = Path(base_path) / cloud_seed_dir
        else:
            # base_path 为空时，回退到项目根目录的 seeds/
            project_seeds = Path(__file__).parent.parent / "seeds"
            if project_seeds.exists():
                self.index_dir = project_seeds
            else:
                self.index_dir = Path("./kb_data") / cloud_seed_dir

        # 索引文件
        if base_path:
            index_file_dir = Path(base_path) / self.full_config.get("cloud_log_dir", "01_云端知识库/同步日志").replace("\\", "/")
        else:
            index_file_dir = Path(__file__).parent.parent / "kb_data" / self.full_config.get("cloud_log_dir", "01_云端知识库/同步日志").replace("\\", "/")
        self.index_file = index_file_dir / "local_search_index.json"
        index_file_dir.mkdir(parents=True, exist_ok=True)

        # 文件内容缓存
        self._content_cache = {}  # {file_name: {"content": str, "hash": str, "mtime": float}}
        self._loaded = False

        # 支持的文件扩展名
        self.supported_exts = self.backend_cfg.get(
            "supported_extensions",
            [".md", ".txt", ".markdown"]
        )
        # 如果安装了 PDF/Word 库，也支持
        if HAS_PYPDF2:
            self.supported_exts.append(".pdf")
        if HAS_DOCX:
            self.supported_exts.append(".docx")

        # 跳过的文件
        self.skip_files = set(self.full_config.get("skip_files", []))

        # 搜索配置
        self.context_chars = self.backend_cfg.get("context_chars", 200)
        self.max_results = self.backend_cfg.get("max_results", 10)

    def init(self) -> dict:
        """初始化：扫描目录，加载文件内容"""
        try:
            if not self.index_dir.exists():
                self.index_dir.mkdir(parents=True, exist_ok=True)
                return {
                    "success": True,
                    "message": f"已创建知识库目录: {self.index_dir}\n请将 .md 种子文件放入此目录后重新运行。"
                }

            self._load_all_files()
            file_count = len(self._content_cache)
            return {
                "success": True,
                "message": f"本地检索后端就绪，已索引 {file_count} 个文件，支持 {', '.join(self.supported_exts)} 格式"
            }
        except Exception as e:
            return {"success": False, "message": f"初始化失败: {e}"}

    def _load_all_files(self):
        """加载目录下所有支持的文件"""
        self._content_cache.clear()

        if not self.index_dir.exists():
            return

        for file_path in self.index_dir.iterdir():
            if not file_path.is_file():
                continue
            if file_path.name in self.skip_files:
                continue
            if file_path.suffix.lower() not in self.supported_exts:
                continue

            content = self._extract_text(file_path)
            if content:
                file_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
                self._content_cache[file_path.name] = {
                    "content": content,
                    "hash": file_hash,
                    "path": str(file_path),
                    "size": len(content),
                    "mtime": file_path.stat().st_mtime,
                }

        self._loaded = True
        self._save_index()

    def _extract_text(self, file_path: Path) -> str:
        """从文件中提取纯文本"""
        ext = file_path.suffix.lower()

        try:
            if ext in (".md", ".txt", ".markdown"):
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()

            elif ext == ".pdf" and HAS_PYPDF2:
                reader = PdfReader(str(file_path))
                texts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        texts.append(text)
                return "\n\n".join(texts)

            elif ext == ".docx" and HAS_DOCX:
                doc = docx.Document(str(file_path))
                return "\n".join([para.text for para in doc.paragraphs if para.text])

        except Exception as e:
            print(f"  [WARN] 读取 {file_path.name} 失败: {e}")

        return ""

    def _save_index(self):
        """保存文件索引（元数据，不含内容）"""
        index_data = {
            "updated_at": datetime.now().isoformat(),
            "file_count": len(self._content_cache),
            "files": {}
        }
        for name, data in self._content_cache.items():
            index_data["files"][name] = {
                "hash": data["hash"],
                "size": data["size"],
                "path": data["path"],
            }

        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

    def search(self, query: str, limit: int = 5) -> list:
        """全文检索：支持多关键词，按命中数排序"""
        if not self._loaded:
            self._load_all_files()

        # 分词：中文按空格分，英文按空格分
        keywords = [kw.strip() for kw in re.split(r'[\s,，、;；]+', query) if kw.strip()]
        if not keywords:
            return []

        results = []

        for file_name, file_data in self._content_cache.items():
            content = file_data["content"]
            if not content:
                continue

            # 统计每个关键词的命中次数
            hit_count = 0
            first_hit_pos = -1
            highlights = []

            for kw in keywords:
                # 转义正则特殊字符
                pattern = re.escape(kw)
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                hit_count += len(matches)
                if matches and first_hit_pos < 0:
                    first_hit_pos = matches[0].start()
                    highlights.append(kw)

            if hit_count == 0:
                continue

            # 计算分数：命中次数 * 权重
            score = min(hit_count / (len(keywords) * 3), 1.0)  # 归一化到 0~1

            # 提取上下文摘要
            snippet = self._extract_snippet(content, keywords, self.context_chars)

            results.append({
                "content": snippet,
                "source": file_name,
                "score": round(score, 2),
                "metadata": {
                    "hit_count": hit_count,
                    "matched_keywords": highlights,
                    "file_size": file_data["size"],
                }
            })

        # 按命中数排序
        results.sort(key=lambda x: x["metadata"]["hit_count"], reverse=True)

        return results[:limit]

    def _extract_snippet(self, content: str, keywords: list, context_chars: int) -> str:
        """提取命中关键词周围的上下文"""
        first_pos = -1
        for kw in keywords:
            match = re.search(re.escape(kw), content, re.IGNORECASE)
            if match:
                first_pos = match.start()
                break

        if first_pos < 0:
            return content[:context_chars] + "..."

        start = max(0, first_pos - context_chars // 2)
        end = min(len(content), first_pos + context_chars // 2 + len(keywords[0]))

        snippet = content[start:end]

        # 高亮关键词
        for kw in keywords:
            snippet = re.sub(
                f'({re.escape(kw)})',
                r'【\1】',
                snippet,
                flags=re.IGNORECASE
            )

        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""
        return f"{prefix}{snippet}{suffix}"

    def upload(self, file_path: str, metadata: dict = None) -> dict:
        """将文件复制到知识库目录"""
        src = Path(file_path)
        if not src.exists():
            return {"success": False, "message": f"文件不存在: {file_path}"}

        dst = self.index_dir / src.name
        try:
            import shutil
            shutil.copy2(str(src), str(dst))
            # 重新加载
            self._load_all_files()
            return {
                "success": True,
                "message": f"已添加到本地知识库: {src.name}",
                "file_id": src.name
            }
        except Exception as e:
            return {"success": False, "message": f"添加失败: {e}"}

    def list_knowledge(self) -> list:
        """列出知识库中的所有文件"""
        if not self._loaded:
            self._load_all_files()

        result = []
        for name, data in self._content_cache.items():
            result.append({
                "name": name,
                "size": data["size"],
                "status": "已索引",
                "added_at": datetime.fromtimestamp(data["mtime"]).strftime("%Y-%m-%d %H:%M"),
            })
        return result

    def is_ready(self) -> bool:
        """检查后端是否就绪"""
        return self._loaded and len(self._content_cache) > 0

    def import_seed_files(self) -> dict:
        """导入种子文件（已在目录中的文件自动索引）"""
        if not self._loaded:
            self._load_all_files()

        seed_files = self.full_config.get("seed_files", [])
        total = len(seed_files)
        success = sum(1 for f in seed_files if f in self._content_cache)

        return {
            "success": success,
            "total": total,
            "details": [
                {
                    "file": f,
                    "success": f in self._content_cache,
                    "category": "已索引" if f in self._content_cache else "未找到"
                }
                for f in seed_files
            ]
        }

    def get_info(self) -> dict:
        """获取后端信息"""
        return {
            "backend": self.backend_name,
            "ready": self.is_ready(),
            "file_count": len(self._content_cache),
            "index_dir": str(self.index_dir),
            "supported_formats": self.supported_exts,
            "has_pdf_support": HAS_PYPDF2,
            "has_docx_support": HAS_DOCX,
            "dependencies": "无（纯Python标准库）" if not (HAS_PYPDF2 or HAS_DOCX) else
                           f"额外支持: {', '.join(['PDF' if HAS_PYPDF2 else '', 'Word' if HAS_DOCX else ''])}".strip(),
        }

    def import_url(self, url: str, metadata: dict = None) -> dict:
        """本地后端不支持URL导入"""
        return {"success": False, "message": "本地检索后端不支持URL导入，请使用 ima 后端导入网页"}

    def delete(self, file_id: str) -> dict:
        """删除知识库中的文件"""
        file_path = self.index_dir / file_id
        if not file_path.exists():
            return {"success": False, "message": f"文件不存在: {file_id}"}

        try:
            file_path.unlink()
            if file_id in self._content_cache:
                del self._content_cache[file_id]
            self._save_index()
            return {"success": True, "message": f"已删除: {file_id}"}
        except Exception as e:
            return {"success": False, "message": f"删除失败: {e}"}


if __name__ == "__main__":
    print("=" * 60)
    print("  本地文件检索后端 — 自测")
    print("=" * 60)

    from kb_backend import load_config
    config = load_config()

    # 如果配置是 chromadb，临时用 local_search 测试
    test_config = config.copy()
    test_config["backend"] = {"type": "local_search"}

    kb = LocalSearchBackend({}, test_config)

    print(f"\n  知识库目录: {kb.index_dir}")
    print(f"  支持格式: {kb.supported_exts}")
    print(f"  PDF支持: {'是' if HAS_PYPDF2 else '否（pip install PyPDF2 启用）'}")
    print(f"  Word支持: {'是' if HAS_DOCX else '否（pip install python-docx 启用）'}")

    result = kb.init()
    print(f"\n  初始化: {result['message']}")

    if kb.is_ready():
        print(f"\n  --- 搜索测试 ---")
        test_queries = [
            "废标条款 资质不符",
            "招标投标法 联合体",
            "等保2.0 网络安全",
            "报价 低于成本价",
            "资质替代 CMMI",
        ]

        for query in test_queries:
            results = kb.search(query, limit=2)
            if results:
                for r in results:
                    print(f"\n  查询: {query}")
                    print(f"  命中: {r['source']} (score: {r['score']}, hits: {r['metadata']['hit_count']})")
                    print(f"  关键词: {r['metadata']['matched_keywords']}")
                    snippet = r['content'][:200].replace('\n', ' ')
                    print(f"  摘要: {snippet}...")
            else:
                print(f"\n  查询: {query} → 无结果")

        print(f"\n  --- 文件列表 ---")
        for item in kb.list_knowledge():
            print(f"  {item['name']}  ({item['size']} bytes, {item['status']})")
    else:
        print(f"\n  知识库为空，请先放入种子文件。")
