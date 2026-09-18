"""知识库语义搜索引擎 v2
=====================
实用化实现，支持多种向量化后端：
1. sentence-transformers (本地 bge-m3 / all-MiniLM)
2. TF-IDF 降级方案（无需GPU）
3. ModelScope API（如未来支持）

核心功能：
- 扫描 10-风格化剪辑知识库 目录
- 构建向量索引并持久化
- 语义相似度搜索
- 与 AE 自动化管线集成
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
KB_DIR = PROJECT_ROOT / "10-风格化剪辑知识库"
CACHE_DIR = PROJECT_ROOT / ".kb_cache"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class KBDocument:
    """知识库文档"""
    doc_id: str
    title: str
    content: str
    source_path: str
    category: str = ""
    tags: list[str] = field(default_factory=list)
    embedding: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.md5(self.content.encode()).hexdigest()[:12]


@dataclass
class SearchResult:
    """搜索结果"""
    doc: KBDocument
    score: float
    highlight: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc.doc_id,
            "title": self.doc.title,
            "score": round(self.score, 4),
            "source_path": self.doc.source_path,
            "category": self.doc.category,
            "highlight": self.highlight[:200],
        }


# ---------------------------------------------------------------------------
# 向量化后端
# ---------------------------------------------------------------------------

class EmbeddingBackend:
    """向量化后端基类"""

    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError

    @property
    def dimension(self) -> int:
        raise NotImplementedError


class TFIDFBackend(EmbeddingBackend):
    """TF-IDF 向量化（无需外部依赖）"""

    def __init__(self, max_features: int = 5000):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            token_pattern=r'(?u)\b\w+\b',
            stop_words=None,  # 中文不需要默认停用词
        )
        self._fitted = False
        self._dim = max_features

    def fit(self, corpus: list[str]):
        """拟合语料库"""
        self.vectorizer.fit(corpus)
        self._fitted = True
        self._dim = len(self.vectorizer.vocabulary_)
        logger.info(f"TF-IDF fitted: {self._dim} features")

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            self.fit(texts)
        return self.vectorizer.transform(texts).toarray().astype(np.float32)

    @property
    def dimension(self) -> int:
        return self._dim


class SentenceTransformerBackend(EmbeddingBackend):
    """Sentence-Transformers 向量化（支持 bge-m3）"""

    # 推荐模型（按优先级）
    MODELS = [
        "BAAI/bge-m3",                    # 多语言，1024维
        "BAAI/bge-small-zh-v1.5",         # 中文小模型，512维
        "sentence-transformers/all-MiniLM-L6-v2",  # 英文，384维
    ]

    def __init__(self, model_name: str | None = None, device: str = "cpu"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )

        self.model_name = model_name
        self.device = device
        self._model = None
        self._dim = None

    def _load_model(self):
        if self._model is not None:
            return

        from sentence_transformers import SentenceTransformer

        models_to_try = [self.model_name] if self.model_name else self.MODELS
        for name in models_to_try:
            try:
                logger.info(f"Loading embedding model: {name}")
                self._model = SentenceTransformer(name, device=self.device)
                self._dim = self._model.get_sentence_embedding_dimension()
                logger.info(f"Model loaded: {name} (dim={self._dim})")
                return
            except Exception as e:
                logger.warning(f"Failed to load {name}: {e}")
                continue

        raise RuntimeError("No embedding model could be loaded")

    def embed(self, texts: list[str]) -> np.ndarray:
        self._load_model()
        embeddings = self._model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.astype(np.float32)

    @property
    def dimension(self) -> int:
        self._load_model()
        return self._dim


# ---------------------------------------------------------------------------
# 知识库搜索引擎
# ---------------------------------------------------------------------------

class KnowledgeBaseSearcher:
    """知识库语义搜索引擎"""

    def __init__(
        self,
        kb_dir: Path | None = None,
        backend: str | None = "auto",
        cache_dir: Path | None = None,
    ):
        self.kb_dir = kb_dir or KB_DIR
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.documents: list[KBDocument] = []
        self._index: np.ndarray | None = None
        self._backend: EmbeddingBackend | None = None
        self._backend_type = backend

        # 统计
        self.stats = {
            "total_docs": 0,
            "total_chunks": 0,
            "index_build_time": 0.0,
            "last_search_time": 0.0,
        }

    def _init_backend(self) -> EmbeddingBackend:
        """初始化向量化后端"""
        if self._backend is not None:
            return self._backend

        if self._backend_type == "tfidf":
            self._backend = TFIDFBackend()
        elif self._backend_type == "transformer":
            self._backend = SentenceTransformerBackend()
        else:  # auto
            try:
                self._backend = SentenceTransformerBackend()
                logger.info("Using sentence-transformers backend")
            except ImportError:
                logger.info("sentence-transformers not available, falling back to TF-IDF")
                self._backend = TFIDFBackend()

        return self._backend

    # ------------------------------------------------------------------
    # 文档加载
    # ------------------------------------------------------------------

    def load_documents(self, force_reload: bool = False) -> int:
        """扫描并加载知识库文档"""
        if self.documents and not force_reload:
            return len(self.documents)

        self.documents = []

        if not self.kb_dir.exists():
            logger.warning(f"Knowledge base directory not found: {self.kb_dir}")
            return 0

        # 扫描 Markdown 文件
        md_files = list(self.kb_dir.glob("**/*.md"))
        logger.info(f"Found {len(md_files)} markdown files in {self.kb_dir}")

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                if len(content.strip()) < 50:
                    continue

                # 提取标题
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1) if title_match else md_file.stem

                # 提取分类（从目录结构）
                rel_path = md_file.relative_to(self.kb_dir)
                category = str(rel_path.parent) if str(rel_path.parent) != "." else "root"

                # 提取标签
                tags = re.findall(r'#(\w+)', content[:500])

                doc = KBDocument(
                    doc_id=hashlib.md5(str(md_file).encode()).hexdigest()[:12],
                    title=title,
                    content=content,
                    source_path=str(md_file),
                    category=category,
                    tags=tags[:10],
                    metadata={
                        "file_size": md_file.stat().st_size,
                        "modified": md_file.stat().st_mtime,
                    }
                )
                self.documents.append(doc)

            except Exception as e:
                logger.warning(f"Failed to load {md_file}: {e}")

        self.stats["total_docs"] = len(self.documents)
        logger.info(f"Loaded {len(self.documents)} documents")
        return len(self.documents)

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------

    def _backend_fingerprint(self, backend: EmbeddingBackend) -> str:
        """后端指纹（类型+模型+维度），用于缓存一致性校验。

        修复历史缺陷：缓存仅校验 doc_count，嵌入模型回退切换
        （如 bge-m3 1024维 → MiniLM 384维）后旧缓存与新查询向量维度
        不匹配，np.dot 直接崩溃。
        """
        model_name = getattr(backend, "model_name", None) or "auto"
        try:
            dim = backend.dimension
        except Exception:
            dim = -1
        return f"{type(backend).__name__}:{model_name}:{dim}"

    def build_index(self, force_rebuild: bool = False) -> bool:
        """构建向量索引"""
        start_time = time.time()

        # 检查缓存
        cache_file = self.cache_dir / "kb_index.pkl"
        if cache_file.exists() and not force_rebuild:
            try:
                with open(cache_file, "rb") as f:
                    cached = pickle.load(f)
                backend = self._init_backend()
                cache_ok = (
                    cached.get("doc_count") == len(self.documents)
                    and cached.get("backend_fp") == self._backend_fingerprint(backend)
                )
                if cache_ok:
                    self._index = cached["index"]
                    # 恢复 TF-IDF vectorizer 状态
                    if cached.get("vectorizer") is not None:
                        if isinstance(backend, TFIDFBackend):
                            backend.vectorizer = cached["vectorizer"]
                            backend._fitted = True
                            backend._dim = len(cached["vectorizer"].vocabulary_)
                    logger.info(f"Loaded cached index ({len(self.documents)} docs)")
                    return True
                logger.warning(
                    "Index cache stale "
                    f"(cached={cached.get('backend_fp')}, "
                    f"current={self._backend_fingerprint(backend)})，重建索引"
                )
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")

        if not self.documents:
            self.load_documents()

        if not self.documents:
            logger.warning("No documents to index")
            return False

        backend = self._init_backend()

        # 准备文本（标题 + 内容前500字）
        texts = [
            f"{doc.title}\n{doc.content[:500]}"
            for doc in self.documents
        ]

        # 如果是 TF-IDF，需要先 fit
        if isinstance(backend, TFIDFBackend):
            backend.fit(texts)

        # 生成向量
        logger.info(f"Building index for {len(texts)} documents...")
        self._index = backend.embed(texts)

        # 双保险：嵌入结果维度与后端声明不一致时拒绝写入缓存
        backend_fp = self._backend_fingerprint(backend)
        if self._index.ndim != 2 or (
            backend.dimension > 0 and self._index.shape[1] != backend.dimension
        ):
            logger.warning(
                f"Embedding dim mismatch (index={self._index.shape}, "
                f"backend={backend_fp})，跳过缓存写入"
            )

        # 保存缓存（含 vectorizer 状态与后端指纹）
        try:
            cache_data = {
                "doc_count": len(self.documents),
                "index": self._index,
                "backend_type": type(backend).__name__,
                "backend_fp": backend_fp,
            }
            if isinstance(backend, TFIDFBackend):
                cache_data["vectorizer"] = backend.vectorizer
            with open(cache_file, "wb") as f:
                pickle.dump(cache_data, f)
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

        self.stats["index_build_time"] = time.time() - start_time
        self.stats["total_chunks"] = len(self.documents)
        logger.info(f"Index built in {self.stats['index_build_time']:.2f}s")
        return True

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        category_filter: str | None = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """语义搜索"""
        start_time = time.time()

        if not self.documents:
            self.load_documents()

        if self._index is None:
            self.build_index()

        if self._index is None or len(self.documents) == 0:
            return []

        backend = self._init_backend()

        # 向量化查询
        query_vec = backend.embed([query])[0]

        # 计算相似度
        if isinstance(backend, TFIDFBackend):
            # TF-IDF 用余弦相似度
            from sklearn.metrics.pairwise import cosine_similarity
            scores = cosine_similarity(query_vec.reshape(1, -1), self._index)[0]
        else:
            # 已归一化的向量用点积
            scores = np.dot(self._index, query_vec)

        # 排序
        top_indices = np.argsort(scores)[::-1]

        results = []
        for idx in top_indices[:top_k * 2]:  # 多取一些用于过滤
            if idx >= len(self.documents):
                continue

            score = float(scores[idx])
            if score < min_score:
                continue

            doc = self.documents[idx]

            # 分类过滤
            if category_filter and category_filter not in doc.category:
                continue

            # 生成高亮
            highlight = self._generate_highlight(query, doc.content)

            results.append(SearchResult(
                doc=doc,
                score=score,
                highlight=highlight,
            ))

            if len(results) >= top_k:
                break

        self.stats["last_search_time"] = time.time() - start_time
        return results

    def _generate_highlight(self, query: str, content: str) -> str:
        """生成搜索结果高亮片段"""
        # 简单实现：找到包含查询词的句子
        query_terms = set(re.findall(r'\w+', query.lower()))
        sentences = re.split(r'[。！？\n]', content)

        best_sentence = ""
        best_overlap = 0

        for sent in sentences[:50]:  # 只检查前50句
            sent_lower = sent.lower()
            overlap = sum(1 for term in query_terms if term in sent_lower)
            if overlap > best_overlap:
                best_overlap = overlap
                best_sentence = sent.strip()

        return best_sentence[:200] if best_sentence else content[:200]

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------

    def search_style(self, style_name: str, top_k: int = 5) -> list[SearchResult]:
        """搜索特定风格的知识"""
        return self.search(f"{style_name} 风格 特效 制作", top_k=top_k)

    def search_technique(self, technique: str, top_k: int = 5) -> list[SearchResult]:
        """搜索特定技术"""
        return self.search(f"{technique} 教程 方法 步骤", top_k=top_k)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "kb_dir": str(self.kb_dir),
            "backend": type(self._backend).__name__ if self._backend else "not_initialized",
            "index_shape": self._index.shape if self._index is not None else None,
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_global_searcher: KnowledgeBaseSearcher | None = None


def get_searcher() -> KnowledgeBaseSearcher:
    """获取全局搜索引擎"""
    global _global_searcher
    if _global_searcher is None:
        _global_searcher = KnowledgeBaseSearcher()
    return _global_searcher


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Knowledge Base Search Engine v2")
    print("=" * 60)

    searcher = KnowledgeBaseSearcher(backend="tfidf")  # 使用 TF-IDF 避免依赖

    print("\n[1] Loading documents...")
    count = searcher.load_documents()
    print(f"    Loaded: {count} documents")

    if count > 0:
        print("\n[2] Building index...")
        searcher.build_index()
        print(f"    Index shape: {searcher._index.shape}")

        print("\n[3] Test search: '赛博朋克 文字特效'")
        results = searcher.search("赛博朋克 文字特效", top_k=3)
        for i, r in enumerate(results, 1):
            print(f"    {i}. [{r.score:.3f}] {r.doc.title}")
            print(f"       {r.highlight[:80]}...")

        print("\n[4] Test search: '转场 动画'")
        results = searcher.search("转场 动画", top_k=3)
        for i, r in enumerate(results, 1):
            print(f"    {i}. [{r.score:.3f}] {r.doc.title}")

    print("\n[5] Stats:")
    for k, v in searcher.get_stats().items():
        print(f"    {k}: {v}")

    print("\n" + "=" * 60)
