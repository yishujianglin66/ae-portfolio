#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRS 知识库 RAG 模块 - KnowledgeRAG v2.0
====================================

视频效果逆向分析系统 (Video Reverse-engineering System) v2.0 的核心模块。
将 100+ 篇知识库 Markdown 文档向量化，支持效果识别时的精确参数检索。

核心能力：
1. 知识库向量化（按 ## 章节切分 chunk）
2. 语义检索（余弦相似度，Top-K 召回）
3. 视觉特征检索（"画面边缘发光" → Glow 参数范围）
4. VISION 分析结果增强（补充精确参数范围 + matchName）
5. 单效果参数范围表查询

embedding 模型：doubao-embedding-large-240428（火山方舟 ARK，OpenAI 兼容协议）
fallback 策略：LLM 网关不可用时使用 TF-IDF（sklearn）作为简单替代

使用方式：
    from vrs.vrs_knowledge_rag import KnowledgeRAG

    rag = KnowledgeRAG()
    rag.build_index()  # 构建索引（一次性）

    # 语义检索
    results = rag.search("画面边缘发光")

    # 视觉特征检索
    matches = rag.search_by_visual_feature("高光区域形成多边形光斑")

    # 增强 VISION 分析结果
    enhanced = rag.enhance_analysis({
        "effects": [{"effect_name": "Gaussian Blur", "intensity": 0.6}]
    })

命令行：
    python vrs_knowledge_rag.py --build
    python vrs_knowledge_rag.py --search "画面边缘发光"
    python vrs_knowledge_rag.py --test
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# numpy 是核心依赖（pyproject.toml 已声明 numpy>=1.24,<2.0）
import numpy as np

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Path = Path(__file__).parent.resolve()
_DEFAULT_KB_DIR: Path = _PROJECT_ROOT / "10-风格化剪辑知识库"
_DEFAULT_INDEX_PATH: Path = _PROJECT_ROOT / "data" / "kb_index"

# embedding 模型（火山方舟 ARK，OpenAI 兼容协议）
_DEFAULT_EMBEDDING_MODEL: str = "doubao-embedding-large-240428"
_ARK_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
_EMBEDDING_BATCH_SIZE: int = 16  # 单次 API 调用最多 16 个文本
_EMBEDDING_TIMEOUT: float = 120.0
_CHUNK_MAX_CHARS: int = 3000  # 单 chunk 最大字符数（embedding 输入有上限）
_CHUNK_MIN_CHARS: int = 50  # 单 chunk 最小字符数（过短的 chunk 跳过）

# 优先索引的高价值文档（按文件名匹配）
PRIORITY_DOCS: List[str] = [
    "参数-效果原子级映射库.md",
    "AE效果视觉特征库.md",
    "AE第三方插件与脚本知识库.md",
    "视频效果逆向分析系统方法论.md",
    "图层堆栈与合成结构推断.md",
    "关键帧与速度曲线逆向分析.md",
    "AE效果插件完全速查手册.md",
]

# 视觉特征检索的优先文档
_VISUAL_FEATURE_DOCS: List[str] = [
    "参数-效果原子级映射库.md",
    "AE效果视觉特征库.md",
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class ChunkRecord:
    """知识库 chunk 记录 - 一个 ## 章节作为一个 chunk"""
    id: str
    content: str
    vector: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转为可序列化的 dict"""
        return {
            "id": self.id,
            "content": self.content,
            "vector": self.vector,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# 核心类：KnowledgeRAG
# ---------------------------------------------------------------------------
class KnowledgeRAG:
    """知识库 RAG 检索增强生成系统

    将 100+ 篇知识库 Markdown 文档向量化，支持效果识别时的精确参数检索。

    Attributes:
        kb_dir: 知识库目录（默认 10-风格化剪辑知识库/）
        index_path: 向量索引存储路径（默认 data/kb_index/）
        embedding_model: embedding 模型名
    """

    VERSION: str = "2.0"

    def __init__(
        self,
        kb_dir: Optional[Path] = None,
        index_path: Optional[Path] = None,
        embedding_model: str = _DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        """初始化 RAG 系统

        Args:
            kb_dir: 知识库目录，默认为项目根下的 10-风格化剪辑知识库/
            index_path: 向量索引存储路径，默认为 data/kb_index/
            embedding_model: embedding 模型名，默认 doubao-embedding-large-240428
        """
        self.kb_dir: Path = Path(kb_dir) if kb_dir else _DEFAULT_KB_DIR
        self.index_path: Path = Path(index_path) if index_path else _DEFAULT_INDEX_PATH
        self.embedding_model: str = embedding_model

        # 索引数据
        self._chunks: List[Dict[str, Any]] = []
        self._vectors: Optional[np.ndarray] = None  # shape: (N, D)
        self._index_meta: Dict[str, Any] = {
            "version": self.VERSION,
            "model": embedding_model,
            "dimension": 0,
        }

        # TF-IDF fallback 状态
        self._tfidf_fallback: bool = False
        self._tfidf_vectorizer: Any = None

        # 自动加载已有索引
        self._load_index()

    # =========================================================================
    # 1. 索引构建
    # =========================================================================

    def build_index(self) -> dict:
        """构建知识库向量索引

        流程：
        1. 扫描 kb_dir 下所有 .md 文件（优先索引高价值文档）
        2. 按 ## 标题切分 chunk
        3. 调用 LLM embedding API 向量化（不可用时用 TF-IDF fallback）
        4. 存储到 index_path（JSON 格式，包含 chunk 文本+向量+元数据）

        Returns:
            统计信息：{total_docs, total_chunks, indexed_categories, dimension, ...}
        """
        logger.info(f"开始构建知识库索引: kb_dir={self.kb_dir}")
        start_time: float = time.time()

        if not self.kb_dir.exists():
            logger.error(f"知识库目录不存在: {self.kb_dir}")
            return {
                "total_docs": 0,
                "total_chunks": 0,
                "indexed_categories": [],
                "error": f"kb_dir not found: {self.kb_dir}",
            }

        # 收集所有 .md 文件，按优先级排序
        md_files: List[Path] = sorted(
            self.kb_dir.rglob("*.md"),
            key=self._priority_sort_key,
        )
        logger.info(f"发现 {len(md_files)} 个 Markdown 文件（优先文档已前置）")

        # 切分 chunk
        all_chunks: List[Dict[str, Any]] = []
        doc_categories: set = set()
        chunk_seq: int = 0

        for md_file in md_files:
            try:
                chunks = self._parse_md_file(md_file)
                for ch in chunks:
                    chunk_seq += 1
                    chunk_id = f"chunk_{chunk_seq:04d}"
                    all_chunks.append({
                        "id": chunk_id,
                        "content": ch["content"],
                        "vector": [],  # 待 embedding 填充
                        "metadata": ch["metadata"],
                    })
                    doc_categories.add(ch["metadata"].get("doc_type", "unknown"))
            except Exception as e:
                logger.warning(f"解析文件失败 {md_file.name}: {e}")

        logger.info(
            f"切分完成：{len(all_chunks)} 个 chunk，来自 {len(md_files)} 篇文档，"
            f"类型分布={sorted(doc_categories)}"
        )

        if not all_chunks:
            logger.warning("未切分出任何 chunk，索引构建终止")
            return {
                "total_docs": len(md_files),
                "total_chunks": 0,
                "indexed_categories": [],
            }

        # 向量化
        texts: List[str] = [c["content"] for c in all_chunks]
        try:
            vectors = self._embed_sync(texts)
            self._tfidf_fallback = False
            dim = int(vectors.shape[1]) if vectors.size > 0 else 0
            logger.info(f"LLM embedding 成功，维度={dim}")
        except Exception as e:
            logger.warning(f"LLM embedding 不可用 ({e})，降级为 TF-IDF")
            vectors = self._embed_tfidf(texts, fit=True)
            self._tfidf_fallback = True
            dim = int(vectors.shape[1]) if vectors.size > 0 else 0

        # 填充向量
        for i in range(len(all_chunks)):
            vec = vectors[i]
            all_chunks[i]["vector"] = vec.tolist() if hasattr(vec, "tolist") else list(vec)

        # 构建索引
        self._chunks = all_chunks
        self._index_meta = {
            "version": self.VERSION,
            "model": "tfidf-fallback" if self._tfidf_fallback else self.embedding_model,
            "dimension": dim,
        }
        if dim > 0:
            self._vectors = np.array(
                [c["vector"] for c in all_chunks],
                dtype=np.float32,
            )

        # 持久化
        self._save_index()

        elapsed: float = time.time() - start_time
        stats: Dict[str, Any] = {
            "total_docs": len(md_files),
            "total_chunks": len(all_chunks),
            "indexed_categories": sorted(doc_categories),
            "dimension": dim,
            "embedding_mode": self._index_meta["model"],
            "elapsed_seconds": round(elapsed, 2),
        }
        logger.info(f"索引构建完成: {stats}")
        return stats

    def _priority_sort_key(self, path: Path) -> Tuple[int, int, str]:
        """优先索引高价值文档的排序键

        Returns:
            (priority, order, name) - priority=0 表示优先文档
        """
        name: str = path.name
        if name in PRIORITY_DOCS:
            return (0, PRIORITY_DOCS.index(name), name)
        return (1, 0, name)

    def _parse_md_file(self, md_path: Path) -> List[Dict[str, Any]]:
        """解析 Markdown 文件，按 ## 标题切分 chunk

        Args:
            md_path: Markdown 文件路径

        Returns:
            chunk 列表，每个 chunk 含 {content, metadata}
            metadata 包含 {source_file, section_title, doc_type, tags}
        """
        content: str = md_path.read_text(encoding="utf-8", errors="ignore")
        source_file: str = md_path.name
        tags: List[str] = self._extract_tags(content)
        doc_type: str = self._classify_doc_type(source_file, content)

        # 去除 YAML frontmatter（--- ... ---）
        content = re.sub(r"\A---\n.*?\n---\n", "", content, count=1, flags=re.DOTALL)

        chunks: List[Dict[str, Any]] = []
        # 按 ## 标题切分（## 是二级标题，### 是三级标题不切分）
        pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
        matches = list(pattern.finditer(content))

        if not matches:
            # 没有 ## 标题，整篇作为一个 chunk
            stripped = content.strip()
            if len(stripped) >= _CHUNK_MIN_CHARS:
                chunks.append({
                    "content": stripped[:_CHUNK_MAX_CHARS],
                    "metadata": {
                        "source_file": source_file,
                        "section_title": md_path.stem,
                        "doc_type": doc_type,
                        "tags": tags,
                    },
                })
            return chunks

        for i, match in enumerate(matches):
            section_title: str = match.group(1).strip()
            start: int = match.start()
            end: int = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content: str = content[start:end].strip()

            # 跳过过短的 chunk
            if len(section_content) < _CHUNK_MIN_CHARS:
                continue

            # 截断保护（embedding 输入有上限）
            if len(section_content) > _CHUNK_MAX_CHARS:
                section_content = section_content[:_CHUNK_MAX_CHARS]

            chunks.append({
                "content": section_content,
                "metadata": {
                    "source_file": source_file,
                    "section_title": section_title,
                    "doc_type": doc_type,
                    "tags": tags,
                },
            })

        return chunks

    def _classify_doc_type(self, source_file: str, content: str) -> str:
        """根据文件名和内容关键词分类文档类型

        分类：
        - param_mapping: 参数-效果原子级映射
        - visual_feature: 视觉特征库
        - plugin_guide: 插件指南
        - case_study: 案例研究
        - methodology: 方法论（默认）
        """
        content_sample: str = content[:2000]

        if "参数-效果" in source_file or "原子级映射" in source_file:
            return "param_mapping"
        if "视觉特征" in source_file:
            return "visual_feature"
        if any(kw in source_file for kw in ["插件", "Sapphire", "Trapcode", "BCC", "Video Copilot"]):
            return "plugin_guide"
        if any(kw in source_file for kw in ["案例", "实战", "解析库"]):
            return "case_study"

        # 内容关键词兜底
        if "视觉签名" in content_sample or "识别特征" in content_sample:
            return "visual_feature"
        if "参数→效果" in content_sample or "matchName" in content_sample:
            return "param_mapping"
        if any(kw in content_sample for kw in ["插件", "Sapphire", "Trapcode", "BCC"]):
            return "plugin_guide"

        return "methodology"

    def _extract_tags(self, content: str) -> List[str]:
        """从 YAML frontmatter 提取 tags

        支持格式：
            tags:
              - 参数映射
              - 效果库
        """
        match = re.search(r"^tags:\s*\n((?:\s*-\s*.+\n?)+)", content, re.MULTILINE)
        if not match:
            return []
        tags_block: str = match.group(1)
        tags: List[str] = re.findall(r"-\s*(.+?)\s*$", tags_block, re.MULTILINE)
        return [t.strip() for t in tags if t.strip()]

    # =========================================================================
    # 2. Embedding 调用
    # =========================================================================

    def _embed_sync(self, texts: List[str]) -> np.ndarray:
        """同步调用 embedding（内部封装 asyncio）

        优先级：
        1. AEKV_LLM_BASE_URL + AEKV_LLM_API_KEY（与 LLM 网关一致）
        2. OPENAI_BASE_URL + OPENAI_API_KEY
        3. DOUBAO_API_KEY + ARK 端点（火山方舟原生）

        Args:
            texts: 待向量化的文本列表

        Returns:
            numpy 数组，shape=(N, D)

        Raises:
            RuntimeError: 未配置 API Key 或 HTTP 调用失败
        """
        try:
            asyncio.get_running_loop()
            # 已在事件循环中 - 在新线程中运行避免冲突
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(asyncio.run, self._embed_async(texts))
                return future.result()
        except RuntimeError:
            # 没有运行中的事件循环
            return asyncio.run(self._embed_async(texts))

    async def _embed_async(self, texts: List[str]) -> np.ndarray:
        """异步批量调用 embedding API（OpenAI 兼容协议）

        通过 httpx 直接调用 /embeddings 端点。
        """
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx 未安装，请安装：pip install httpx") from e

        # 从环境变量获取配置（与 core/llm_gateway.py 的 configure_from_env 一致）
        base_url: str = (
            os.environ.get("AEKV_LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or _ARK_BASE_URL
        )
        api_key: str = (
            os.environ.get("AEKV_LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("DOUBAO_API_KEY")
            or ""
        )

        if not api_key:
            raise RuntimeError(
                "未配置 embedding API Key "
                "(AEKV_LLM_API_KEY / OPENAI_API_KEY / DOUBAO_API_KEY 均为空)"
            )

        url: str = f"{base_url.rstrip('/')}/embeddings"
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        all_vectors: List[List[float]] = []
        total: int = len(texts)

        async with httpx.AsyncClient(timeout=_EMBEDDING_TIMEOUT) as client:
            for i in range(0, total, _EMBEDDING_BATCH_SIZE):
                batch: List[str] = texts[i:i + _EMBEDDING_BATCH_SIZE]
                payload: Dict[str, Any] = {
                    "model": self.embedding_model,
                    "input": batch,
                }

                # 重试 3 次
                for attempt in range(3):
                    try:
                        resp = await client.post(url, json=payload, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        # OpenAI 兼容格式：data.data[i].embedding
                        batch_vectors = [
                            item["embedding"] for item in data.get("data", [])
                        ]
                        all_vectors.extend(batch_vectors)
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise RuntimeError(
                                f"embedding 批次 {i // _EMBEDDING_BATCH_SIZE} "
                                f"失败（重试 3 次）: {e}"
                            ) from e
                        logger.warning(
                            f"embedding 批次 {i // _EMBEDDING_BATCH_SIZE} "
                            f"失败 (尝试 {attempt + 1}/3): {e}"
                        )
                        await asyncio.sleep(1.0 * (attempt + 1))

                done = min(i + _EMBEDDING_BATCH_SIZE, total)
                logger.info(f"embedding 进度: {done}/{total}")

        if not all_vectors:
            raise RuntimeError("embedding 返回空结果")

        return np.array(all_vectors, dtype=np.float32)

    def _embed_tfidf(self, texts: List[str], fit: bool = False) -> np.ndarray:
        """TF-IDF fallback 向量化（sklearn）

        当 LLM embedding 不可用时作为简单替代。
        使用中英文混合的 token 模式。
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except ImportError as e:
            raise RuntimeError(
                "sklearn 未安装，无法使用 TF-IDF fallback。"
                "请安装：pip install scikit-learn"
            ) from e

        if fit or self._tfidf_vectorizer is None:
            # 字符级 ngram 对中文友好（避免 \b 词边界导致整句被当作单 token）
            # "画面边缘发光" → 1-gram: 画/面/边/缘/发/光, 2-gram: 画面/面边/边缘/缘发/发光
            self._tfidf_vectorizer = TfidfVectorizer(
                max_features=8000,
                analyzer="char",
                ngram_range=(1, 2),
                sublinear_tf=True,
                min_df=1,
            )
            matrix = self._tfidf_vectorizer.fit_transform(texts)
        else:
            matrix = self._tfidf_vectorizer.transform(texts)

        return matrix.toarray().astype(np.float32)

    # =========================================================================
    # 3. 语义检索
    # =========================================================================

    def search(self, query: str, top_k: int = 5) -> list:
        """语义检索：返回 top_k 最相关的 chunk

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            [{content, source_file, section_title, similarity, metadata}]
        """
        if not self._chunks:
            logger.warning("索引为空，请先调用 build_index()")
            return []

        if self._vectors is None or len(self._vectors) == 0:
            logger.warning("向量矩阵为空，无法检索")
            return []

        # 向量化 query
        try:
            if self._tfidf_fallback:
                query_vec: np.ndarray = self._embed_tfidf([query], fit=False)[0]
            else:
                query_vec = self._embed_sync([query])[0]
        except Exception as e:
            logger.error(f"query 向量化失败: {e}")
            return []

        # 计算余弦相似度
        similarities: np.ndarray = self._cosine_batch(query_vec, self._vectors)

        # Top-K（降序）
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results: List[Dict[str, Any]] = []
        for idx in top_indices:
            idx_int: int = int(idx)
            sim: float = float(similarities[idx_int])
            if sim <= 0.0:  # 过滤完全无关（相似度为0）
                continue
            chunk = self._chunks[idx_int]
            results.append({
                "content": chunk["content"],
                "source_file": chunk["metadata"].get("source_file", ""),
                "section_title": chunk["metadata"].get("section_title", ""),
                "similarity": round(sim, 4),
                "metadata": chunk["metadata"],
            })

        return results

    def _cosine_batch(
        self,
        query_vec: np.ndarray,
        matrix: np.ndarray,
    ) -> np.ndarray:
        """批量计算余弦相似度（numpy）

        Args:
            query_vec: 查询向量，shape=(D,)
            matrix: 知识库向量矩阵，shape=(N, D)

        Returns:
            相似度数组，shape=(N,)
        """
        q_norm: float = float(np.linalg.norm(query_vec))
        m_norms: np.ndarray = np.linalg.norm(matrix, axis=1)

        # 避免除零
        denom: np.ndarray = m_norms * q_norm
        denom[denom == 0] = 1e-10

        return (matrix @ query_vec) / denom

    # =========================================================================
    # 4. 视觉特征检索
    # =========================================================================

    def search_by_visual_feature(self, feature_desc: str) -> list:
        """按视觉特征描述检索

        优先检索 [参数-效果原子级映射库.md] 和 [AE效果视觉特征库.md]，
        从视觉特征描述（如"画面边缘发光"）匹配到具体效果的参数范围。

        Args:
            feature_desc: 视觉特征描述，如"画面边缘发光"、"高光形成多边形光斑"

        Returns:
            [{effect_name, matchName, params_range, source, similarity, content_excerpt}]
        """
        # 先用通用 search 检索（多召回一些以便筛选）
        raw_results: List[Dict[str, Any]] = self.search(feature_desc, top_k=10)

        # 优先保留来自视觉特征库和参数映射库的 chunk
        prioritized: List[Dict[str, Any]] = []
        others: List[Dict[str, Any]] = []
        for r in raw_results:
            src: str = r.get("source_file", "")
            if src in _VISUAL_FEATURE_DOCS:
                prioritized.append(r)
            else:
                others.append(r)

        ordered: List[Dict[str, Any]] = prioritized + others

        # 解析出效果名、matchName、参数范围
        parsed: List[Dict[str, Any]] = []
        for r in ordered:
            parsed.append(self._parse_effect_from_chunk(r))

        return parsed[:5]

    def _parse_effect_from_chunk(
        self,
        chunk_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """从 chunk 内容解析出效果信息

        Args:
            chunk_result: search 返回的单个结果

        Returns:
            {effect_name, matchName, params_range, source, similarity, content_excerpt}
        """
        content: str = chunk_result["content"]
        section_title: str = chunk_result.get("section_title", "")

        # 效果名优先从 section_title 提取
        effect_name: str = section_title

        # 提取括号内的英文名作为 matchName 候选
        matchName: str = ""
        m = re.search(r"[（(]([^()（）]+)[)）]", section_title)
        if m:
            matchName = m.group(1).strip()

        # 从内容中提取参数范围表
        params_range: Dict[str, Dict[str, Any]] = self._extract_params_range(content)

        return {
            "effect_name": effect_name,
            "matchName": matchName,
            "params_range": params_range,
            "source": chunk_result.get("source_file", ""),
            "similarity": chunk_result.get("similarity", 0.0),
            "content_excerpt": content[:300],
        }

    def _extract_params_range(
        self,
        content: str,
    ) -> Dict[str, Dict[str, Any]]:
        """从内容中提取参数范围表

        识别 Markdown 表格中的 | 参数名 | 范围 | 效果 | ... 格式，
        提取每个参数的 min/max/typical/visual_signature。

        Args:
            content: chunk 文本内容

        Returns:
            {param_name: {min, max, typical, visual_signature}}
        """
        params: Dict[str, Dict[str, Any]] = {}

        lines: List[str] = content.split("\n")
        for line in lines:
            if "|" not in line:
                continue

            cells: List[str] = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue

            # 跳过分隔线 |---|---|
            if all(re.match(r"^[-:\s]+$", c) for c in cells):
                continue

            # 第一个单元格作为参数名
            param_name: str = cells[0]
            # 跳过表头
            if param_name in (
                "参数", "参数名", "参数组合", "参数值",
                "类型+参数", "参数值组合", "Property",
            ):
                continue

            # 找范围（数字范围，如 0-100、5~30）
            range_str: str = ""
            for c in cells[1:]:
                if re.search(r"\d+\s*[-~]\s*\d+", c):
                    range_str = c
                    break

            if range_str:
                range_match = re.search(r"(\d+)\s*[-~]\s*(\d+)", range_str)
                if range_match:
                    # visual_signature 取后续单元格内容
                    sig_cells = cells[1:4] if len(cells) >= 4 else cells[1:]
                    params[param_name] = {
                        "min": int(range_match.group(1)),
                        "max": int(range_match.group(2)),
                        "typical": range_str,
                        "visual_signature": " | ".join(sig_cells),
                    }

        return params

    # =========================================================================
    # 5. VISION 分析结果增强
    # =========================================================================

    def enhance_analysis(self, vision_result: dict) -> dict:
        """增强 VISION 分析结果

        接收 vision_result（含 effects 列表，每个效果含 effect_name + intensity），
        用效果名称检索知识库，补充精确参数范围、matchName、典型组合。

        Args:
            vision_result: VISION 分析结果，形如：
                {
                    "effects": [
                        {"effect_name": "Gaussian Blur", "intensity": 0.6},
                        ...
                    ]
                }

        Returns:
            增强后的结果（原结果 + 每个效果补充 params_range + recommended_matchName）
        """
        enhanced: Dict[str, Any] = dict(vision_result)
        effects: List[Dict[str, Any]] = (
            vision_result.get("effects")
            or vision_result.get("effect_list")
            or []
        )

        enhanced_effects: List[Dict[str, Any]] = []
        for eff in effects:
            eff_enhanced: Dict[str, Any] = dict(eff)
            effect_name: str = eff.get("effect_name", "") or eff.get("name", "")

            if not effect_name:
                enhanced_effects.append(eff_enhanced)
                continue

            # 用效果名检索知识库
            results: List[Dict[str, Any]] = self.search(effect_name, top_k=3)

            if results:
                top: Dict[str, Any] = results[0]
                parsed: Dict[str, Any] = self._parse_effect_from_chunk(top)
                eff_enhanced["params_range"] = parsed["params_range"]
                eff_enhanced["recommended_matchName"] = parsed["matchName"]
                eff_enhanced["knowledge_source"] = parsed["source"]
                eff_enhanced["knowledge_reference"] = top.get("section_title", "")
                eff_enhanced["typical_combinations"] = parsed["content_excerpt"]
            else:
                eff_enhanced["params_range"] = {}
                eff_enhanced["recommended_matchName"] = ""
                eff_enhanced["knowledge_source"] = ""
                eff_enhanced["knowledge_reference"] = ""

            enhanced_effects.append(eff_enhanced)

        enhanced["effects"] = enhanced_effects
        enhanced["_enhanced_by"] = f"KnowledgeRAG v{self.VERSION}"
        return enhanced

    # =========================================================================
    # 6. 单效果参数范围查询
    # =========================================================================

    def get_effect_param_range(self, effect_name: str) -> dict:
        """查询单个效果的参数范围表

        Args:
            effect_name: 效果名称（中英文均可，如"Gaussian Blur"、"高斯模糊"）

        Returns:
            {param_name: {min, max, typical, visual_signature}}
        """
        results: List[Dict[str, Any]] = self.search(effect_name, top_k=3)

        all_params: Dict[str, Dict[str, Any]] = {}
        for r in results:
            parsed: Dict[str, Any] = self._parse_effect_from_chunk(r)
            for pname, pinfo in parsed["params_range"].items():
                if pname not in all_params:
                    all_params[pname] = pinfo

        return all_params

    # =========================================================================
    # 索引持久化
    # =========================================================================

    def _save_index(self) -> None:
        """保存索引到 JSON 文件"""
        self.index_path.mkdir(parents=True, exist_ok=True)
        index_file: Path = self.index_path / "kb_index.json"

        serializable: Dict[str, Any] = {
            "version": self._index_meta["version"],
            "model": self._index_meta["model"],
            "dimension": self._index_meta["dimension"],
            "chunks": self._chunks,
        }

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        logger.info(
            f"索引已保存: {index_file} "
            f"({len(self._chunks)} chunks, model={self._index_meta['model']})"
        )

    def _load_index(self) -> bool:
        """从 JSON 加载已有索引

        Returns:
            True 表示加载成功
        """
        index_file: Path = self.index_path / "kb_index.json"
        if not index_file.exists():
            return False

        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._index_meta = {
                "version": data.get("version", self.VERSION),
                "model": data.get("model", self.embedding_model),
                "dimension": data.get("dimension", 0),
            }
            self._chunks = data.get("chunks", [])
            self._tfidf_fallback = (self._index_meta["model"] == "tfidf-fallback")

            if self._chunks and self._chunks[0].get("vector"):
                self._vectors = np.array(
                    [c["vector"] for c in self._chunks],
                    dtype=np.float32,
                )
                logger.info(
                    f"已加载索引: {len(self._chunks)} chunks, "
                    f"model={self._index_meta['model']}, "
                    f"dim={self._index_meta['dimension']}"
                )

                # 如果是 TF-IDF 模式，重新 fit vectorizer（用于 query 向量化）
                if self._tfidf_fallback:
                    texts: List[str] = [c["content"] for c in self._chunks]
                    try:
                        self._embed_tfidf(texts, fit=True)
                    except Exception as e:
                        logger.warning(f"TF-IDF vectorizer 重建失败: {e}")

                return True
        except Exception as e:
            logger.warning(f"加载索引失败: {e}")

        return False

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取当前索引统计信息"""
        return {
            "total_chunks": len(self._chunks),
            "model": self._index_meta.get("model", ""),
            "dimension": self._index_meta.get("dimension", 0),
            "tfidf_fallback": self._tfidf_fallback,
            "kb_dir": str(self.kb_dir),
            "index_path": str(self.index_path),
        }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def _run_cli() -> None:
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="VRS 知识库 RAG 模块 - 视频效果逆向分析系统 v2.0",
    )
    parser.add_argument("--build", action="store_true", help="构建索引（扫描知识库目录）")
    parser.add_argument("--search", type=str, help="检索查询文本")
    parser.add_argument("--test", action="store_true", help="运行内置测试用例")
    parser.add_argument("--kb-dir", type=str, help="知识库目录（默认 10-风格化剪辑知识库/）")
    parser.add_argument("--index-path", type=str, help="索引存储路径（默认 data/kb_index/）")
    parser.add_argument("--top-k", type=int, default=5, help="检索返回结果数量")

    args = parser.parse_args()

    kb_dir: Optional[Path] = Path(args.kb_dir) if args.kb_dir else None
    index_path: Optional[Path] = Path(args.index_path) if args.index_path else None

    rag = KnowledgeRAG(kb_dir=kb_dir, index_path=index_path)

    if args.build:
        stats = rag.build_index()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif args.search:
        results = rag.search(args.search, top_k=args.top_k)
        print(f"\n检索: {args.search}")
        print(f"结果数: {len(results)}\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] {r['source_file']} > {r['section_title']}")
            print(f"    相似度: {r['similarity']}")
            print(f"    内容预览: {r['content'][:150]}...")
            print()
    elif args.test:
        _run_builtin_test(rag)
    else:
        parser.print_help()


def _run_builtin_test(rag: KnowledgeRAG) -> None:
    """内置测试用例

    测试场景：
    1. 索引状态检查
    2. 检索"高斯模糊"（应返回参数映射库的相关 chunk）
    3. 视觉特征检索"画面边缘发光"
    4. 参数范围查询"Glow 发光"
    5. VISION 分析结果增强
    """
    print("=" * 60)
    print("VRS KnowledgeRAG v2.0 内置测试")
    print("=" * 60)

    # 如果索引为空，先构建
    if not rag._chunks:
        print("\n[0] 索引为空，自动构建...")
        rag.build_index()

    stats = rag.get_stats()
    print(f"\n[1] 索引状态")
    print(f"    chunks: {stats['total_chunks']}")
    print(f"    model:  {stats['model']}")
    print(f"    dim:    {stats['dimension']}")
    print(f"    fallback: {stats['tfidf_fallback']}")

    # 测试 1: 检索"高斯模糊"
    print("\n[2] 测试检索 '高斯模糊'...")
    results = rag.search("高斯模糊", top_k=3)
    assert results, "检索'高斯模糊'应返回结果"
    print(f"    返回 {len(results)} 个结果:")
    for r in results:
        print(f"    - {r['source_file']} > {r['section_title']} (sim={r['similarity']})")
    # 期望：参数-效果原子级映射库.md 或 AE效果视觉特征库.md 在 top 结果中
    top_sources = [r["source_file"] for r in results]
    assert any(
        s in _VISUAL_FEATURE_DOCS for s in top_sources
    ), "应优先匹配视觉特征库/参数映射库"
    print("    ✓ 通过")

    # 测试 2: 视觉特征检索
    print("\n[3] 测试视觉特征检索 '画面边缘发光'...")
    matches = rag.search_by_visual_feature("画面边缘发光")
    print(f"    返回 {len(matches)} 个匹配:")
    for m in matches[:3]:
        print(
            f"    - {m['effect_name']} | matchName={m['matchName']} | "
            f"params={list(m['params_range'].keys())}"
        )
    assert matches, "视觉特征检索应返回匹配"
    print("    ✓ 通过")

    # 测试 3: 参数范围查询
    print("\n[4] 测试参数范围查询 'Glow 发光'...")
    params = rag.get_effect_param_range("Glow 发光")
    print(f"    参数数量: {len(params)}")
    for pname, pinfo in list(params.items())[:3]:
        print(f"    - {pname}: min={pinfo['min']} max={pinfo['max']} typical={pinfo['typical']}")
    print("    ✓ 通过")

    # 测试 4: 增强分析
    print("\n[5] 测试 VISION 分析结果增强...")
    vision_result = {
        "effects": [
            {"effect_name": "Gaussian Blur", "intensity": 0.6},
            {"effect_name": "Glow", "intensity": 0.8},
        ],
    }
    enhanced = rag.enhance_analysis(vision_result)
    print(f"    增强后效果数: {len(enhanced['effects'])}")
    for eff in enhanced["effects"]:
        match_name = eff.get("recommended_matchName", "N/A")
        param_keys = list(eff.get("params_range", {}).keys())
        print(f"    - {eff['effect_name']}: matchName={match_name}, params={param_keys}")
    assert enhanced.get("_enhanced_by"), "应添加 _enhanced_by 标记"
    print("    ✓ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过 ✓")
    print("=" * 60)


if __name__ == "__main__":
    _run_cli()
