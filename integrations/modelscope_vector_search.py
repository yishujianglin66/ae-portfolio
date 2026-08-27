"""
魔搭社区 bge-m3 向量检索增强模块
=====================================
使用魔搭社区的bge-m3模型对知识库进行向量化，实现语义搜索。

功能列表：
- 知识库文档向量化
- 语义相似度搜索
- 风格化剪辑知识智能检索
- 与AE自动化管线集成

使用示例：
    from integrations.modelscope_vector_search import KnowledgeBaseSearcher

    searcher = KnowledgeBaseSearcher()
    results = searcher.search("如何制作赛博朋克风格文字特效", top_k=5)
    print(results)
"""

from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class SearchResult:
    """搜索结果"""
    doc_id: str
    title: str
    content: str
    score: float
    source_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "score": round(self.score, 4),
            "source_path": self.source_path,
            "metadata": self.metadata,
        }


@dataclass
class Document:
    """文档对象"""
    doc_id: str
    title: str
    content: str
    source_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


class ModelScopeEmbeddingClient:
    """
    魔搭社区 Embedding 客户端
    使用bge-m3模型生成文本向量
    """

    BASE_URL = "https://modelscope.cn/openapi/v1"
    MODEL_NAME = "bge-m3"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MODELSCOPE_API_KEY", "")
        self.base_url = (base_url or os.environ.get("MODELSCOPE_BASE_URL", self.BASE_URL)).rstrip("/")
        self.model_name = os.environ.get("MODELSCOPE_EMBEDDING_MODEL", self.MODEL_NAME)

        if not self.api_key:
            raise ValueError("未找到MODELSCOPE_API_KEY")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文本向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        endpoint = "/inference/embeddings"

        payload = {
            "model": self.model_name,
            "input": texts,
        }

        try:
            response = self.session.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()

            # 解析响应
            if "data" in result:
                # 按index排序，确保顺序一致
                embeddings = sorted(
                    result["data"],
                    key=lambda x: x.get("index", 0)
                )
                return [item["embedding"] for item in embeddings]
            elif "embeddings" in result:
                return result["embeddings"]
            else:
                raise ValueError(f"未知的响应格式: {list(result.keys())}")

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"API请求失败: {e}")

    def embed_text(self, text: str) -> List[float]:
        """生成单个文本向量"""
        return self.embed_texts([text])[0]


class KnowledgeBaseSearcher:
    """
    知识库语义搜索引擎

    使用bge-m3模型对知识库文档进行向量化，支持语义相似度搜索。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        kb_root: Optional[str] = None,
        index_file: Optional[str] = None,
    ):
        self.embedding_client = ModelScopeEmbeddingClient(api_key=api_key)
        self.kb_root = Path(kb_root) if kb_root else Path(__file__).parent.parent / "10-风格化剪辑知识库"
        self.index_file = Path(index_file) if index_file else self.kb_root.parent / ".kb_cache" / "vector_index.json"

        # 内存中的向量索引
        self.documents: Dict[str, Document] = {}
        self.embeddings: Dict[str, List[float]] = {}

        # 尝试加载已有索引
        self._load_index()

    def _load_index(self):
        """加载向量索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for doc_id, doc_data in data.get("documents", {}).items():
                    self.documents[doc_id] = Document(
                        doc_id=doc_id,
                        title=doc_data["title"],
                        content=doc_data["content"],
                        source_path=doc_data["source_path"],
                        metadata=doc_data.get("metadata", {}),
                    )

                self.embeddings = data.get("embeddings", {})
                print(f"✓ 已加载向量索引: {len(self.documents)} 个文档")

            except Exception as e:
                print(f"⚠ 加载索引失败: {e}")

    def _save_index(self):
        """保存向量索引"""
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "documents": {
                doc_id: {
                    "title": doc.title,
                    "content": doc.content,
                    "source_path": doc.source_path,
                    "metadata": doc.metadata,
                }
                for doc_id, doc in self.documents.items()
            },
            "embeddings": self.embeddings,
            "model": self.embedding_client.model_name,
        }

        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✓ 向量索引已保存: {self.index_file}")

    def _generate_doc_id(self, content: str) -> str:
        """生成文档ID"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

    def scan_knowledge_base(self, file_pattern: str = "*.md") -> List[Document]:
        """
        扫描知识库目录，提取文档

        Args:
            file_pattern: 文件匹配模式

        Returns:
            文档列表
        """
        documents = []

        if not self.kb_root.exists():
            print(f"⚠ 知识库目录不存在: {self.kb_root}")
            return documents

        for file_path in self.kb_root.glob(f"**/{file_pattern}"):
            try:
                content = file_path.read_text(encoding="utf-8")

                # 提取标题（第一行#开头）
                lines = content.split("\n")
                title = ""
                for line in lines:
                    if line.startswith("#"):
                        title = line.lstrip("# ").strip()
                        break

                if not title:
                    title = file_path.stem

                doc_id = self._generate_doc_id(content)

                doc = Document(
                    doc_id=doc_id,
                    title=title,
                    content=content,
                    source_path=str(file_path),
                    metadata={
                        "filename": file_path.name,
                        "size": len(content),
                        "lines": len(lines),
                    },
                )

                documents.append(doc)
                self.documents[doc_id] = doc

            except Exception as e:
                print(f"⚠ 读取文件失败 {file_path}: {e}")

        print(f"✓ 扫描完成: 找到 {len(documents)} 个文档")
        return documents

    def build_index(self, batch_size: int = 32):
        """
        构建向量索引

        Args:
            batch_size: 批量处理大小
        """
        # 扫描文档
        documents = self.scan_knowledge_base()

        if not documents:
            print("⚠ 没有找到文档")
            return

        # 分批生成向量
        texts = [f"{doc.title}\n{doc.content[:2000]}" for doc in documents]

        print(f"开始生成向量... (共 {len(texts)} 个文档)")

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]

            try:
                embeddings = self.embedding_client.embed_texts(batch)

                for doc, embedding in zip(batch_docs, embeddings):
                    self.embeddings[doc.doc_id] = embedding

                print(f"  进度: {min(i + batch_size, len(texts))}/{len(texts)}")

            except Exception as e:
                print(f"⚠ 批次 {i} 失败: {e}")
                continue

        # 保存索引
        self._save_index()
        print(f"✓ 索引构建完成: {len(self.embeddings)} 个向量")

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> List[SearchResult]:
        """
        语义搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            min_score: 最低相似度阈值

        Returns:
            搜索结果列表
        """
        if not self.embeddings:
            print("⚠ 索引为空，请先调用 build_index()")
            return []

        # 生成查询向量
        query_embedding = self.embedding_client.embed_text(query)

        # 计算相似度
        scores = []
        for doc_id, doc_embedding in self.embeddings.items():
            score = self._cosine_similarity(query_embedding, doc_embedding)
            if score >= min_score:
                scores.append((doc_id, score))

        # 排序
        scores.sort(key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for doc_id, score in scores[:top_k]:
            doc = self.documents.get(doc_id)
            if doc:
                results.append(SearchResult(
                    doc_id=doc_id,
                    title=doc.title,
                    content=doc.content,
                    score=score,
                    source_path=doc.source_path,
                    metadata=doc.metadata,
                ))

        return results

    def search_and_format(
        self,
        query: str,
        top_k: int = 5,
    ) -> str:
        """
        搜索并格式化结果（用于AI上下文注入）

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            格式化的搜索结果文本
        """
        results = self.search(query, top_k=top_k)

        if not results:
            return "未找到相关知识。"

        lines = [f"找到 {len(results)} 条相关知识：\n"]

        for i, result in enumerate(results, 1):
            lines.append(f"### {i}. {result.title} (相似度: {result.score:.2%})")
            lines.append(f"来源: {result.source_path}")
            lines.append(f"内容摘要: {result.content[:300]}...")
            lines.append("")

        return "\n".join(lines)


# 便捷函数
def create_searcher(
    api_key: Optional[str] = None,
    kb_root: Optional[str] = None,
) -> KnowledgeBaseSearcher:
    """创建知识库搜索引擎"""
    return KnowledgeBaseSearcher(api_key=api_key, kb_root=kb_root)


if __name__ == "__main__":
    print("=" * 60)
    print("魔搭社区 bge-m3 向量检索增强测试")
    print("=" * 60)

    try:
        searcher = create_searcher()

        # 构建索引（首次运行）
        if not searcher.embeddings:
            print("\n正在构建向量索引...")
            searcher.build_index()

        # 测试搜索
        test_queries = [
            "赛博朋克风格文字特效",
            "如何制作故障艺术效果",
            "电影级调色技巧",
        ]

        print("\n" + "=" * 60)
        print("搜索测试")
        print("=" * 60)

        for query in test_queries:
            print(f"\n查询: {query}")
            results = searcher.search(query, top_k=3)

            if results:
                for i, result in enumerate(results, 1):
                    print(f"  {i}. {result.title} ({result.score:.2%})")
            else:
                print("  未找到结果")

    except ValueError as e:
        print(f"✗ 错误: {e}")
        print("  请确保已设置 MODELSCOPE_API_KEY 环境变量")
    except Exception as e:
        print(f"✗ 未知错误: {e}")
        import traceback
        traceback.print_exc()
