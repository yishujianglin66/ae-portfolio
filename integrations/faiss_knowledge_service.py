"""
FAISS 知识服务 P2-A - 向量检索 API 服务

提供基于 FAISS 的语义搜索、知识库索引、相似度检索等能力。
用于素材搜索、风格匹配、知识问答等场景。
"""
from __future__ import annotations

import faiss
import json
import logging
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# =============================================================================
# 数据模型定义
# =============================================================================

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="查询文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    filter_tags: Optional[List[str]] = Field(default=None, description="标签过滤")


class SearchResult(BaseModel):
    """搜索结果"""
    id: str
    score: float
    metadata: Dict[str, Any]
    content: str


class IndexInfo(BaseModel):
    """索引信息"""
    dimension: int
    n_vectors: int
    index_type: str
    size_bytes: int


# =============================================================================
# FAISS 服务类
# =============================================================================

class FaissKnowledgeService:
    """FAISS 知识服务核心类"""
    
    def __init__(self, index_path: str = "data/faiss_index"):
        self.index_path = Path(index_path)
        self.index: Optional[faiss.Index] = None
        self.vectors: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        
    def create_index(self, dimension: int, index_type: str = "Flat") -> faiss.Index:
        """创建 FAISS 索引
        
        Args:
            dimension: 向量维度
            index_type: 索引类型 (Flat, IVF, HNSW)
            
        Returns:
            FAISS 索引对象
        """
        if index_type == "Flat":
            return faiss.IndexFlat(dimension, faiss.METRIC_L2)
        elif index_type == "IVF":
            nlist = 100
            quantizer = faiss.IndexFlat(dimension, faiss.METRIC_L2)
            return faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_L2)
        elif index_type == "HNSW":
            return faiss.IndexHNSWFlat(dimension, 32)
        else:
            raise ValueError(f"Unknown index type: {index_type}")
    
    def add_vectors(self, vectors: np.ndarray, ids: List[str], metadatas: List[Dict]) -> None:
        """添加向量到索引
        
        Args:
            vectors: 向量数组 (n,d)
            ids: 向量 ID 列表
            metadatas: 元数据列表
        """
        if self.index is None:
            raise RuntimeError("Index not created")
        
        self.index.add(vectors.astype(np.float32))
        self._vectors_added = len(vectors)  # Track added count
        
        for i, (vid, meta) in enumerate(zip(ids, metadatas)):
            self.vectors.append({
                "id": vid,
                "metadata": meta
            })
    
    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[SearchResult]:
        """搜索最相似的向量
        
        Args:
            query_vector: 查询向量
            top_k: 返回数量
            
        Returns:
            搜索结果列表
        """
        if self.index is None:
            raise RuntimeError("Index not created")
        
        distances, indices = self.index.search(
            query_vector.astype(np.float32).reshape(1, -1), 
            top_k
        )
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.vectors):
                vec_info = self.vectors[idx]
                results.append(SearchResult(
                    id=vec_info["id"],
                    score=float(distances[0][i]),
                    metadata=vec_info["metadata"],
                    content=vec_info["metadata"].get("content", "")
                ))
        
        return results
    
    def save_index(self, path: Optional[str] = None) -> None:
        """保存索引到磁盘"""
        save_path = Path(path or self.index_path)
        save_path.mkdir(parents=True, exist_ok=True)  # Ensure exists
        
        faiss.write_index(self.index, str(save_path / "index.faiss"))
        
        # 保存元数据
        with open(save_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump({
                "dimension": self.index.d,
                "n_vectors": self.index.ntotal,
                "vectors": self.vectors
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Index saved to {save_path}")
    
    def load_index(self, path: Optional[str] = None) -> None:
        """从磁盘加载索引"""
        load_path = Path(path or self.index_path)
        
        if not load_path.exists():
            raise FileNotFoundError(f"Index not found at {load_path}")
        
        self.index = faiss.read_index(str(load_path / "index.faiss"))
        
        # 加载元数据
        with open(load_path / "metadata.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            self.vectors = data["vectors"]
        
        logger.info(f"Index loaded from {load_path}")
    
    def get_info(self) -> IndexInfo:
        """获取索引信息"""
        if self.index is None:
            raise RuntimeError("Index not created")
        
        return IndexInfo(
            dimension=self.index.d,
            n_vectors=self.index.ntotal,
            index_type=str(type(self.index).__name__),
            size_bytes=len(json.dumps(self.vectors))  # Approximate
        )


# =============================================================================
# FastAPI 应用
# =============================================================================

app = FastAPI(
    title="FAISS Knowledge Service",
    description="基于 FAISS 的向量检索服务",
    version="1.0.0"
)

# 全局服务实例
knowledge_service = FaissKnowledgeService()


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "service": "FAISS Knowledge Service"}


@app.get("/info")
async def get_index_info() -> IndexInfo:
    """获取索引信息"""
    try:
        return knowledge_service.get_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search(request: SearchRequest) -> List[SearchResult]:
    """搜索接口"""
    try:
        # TODO: 实现 query 向量化 (使用 sentence-transformers 或其他嵌入模型)
        # 这里暂时返回 mock 结果
        query_vector = np.random.randn(384)  # 假设维度为 384
        
        results = knowledge_service.search(query_vector, request.top_k)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add")
async def add_vectors(
    vectors: List[Dict[str, Any]],
    ids: List[str],
    metadatas: List[Dict]
) -> Dict[str, str]:
    """添加向量接口"""
    try:
        vectors_array = np.array([v["vector"] for v in vectors], dtype=np.float32)
        knowledge_service.add_vectors(vectors_array, ids, metadatas)
        return {"status": "success", "added": len(vectors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save")
async def save_index(path: Optional[str] = None) -> Dict[str, str]:
    """保存索引"""
    try:
        knowledge_service.save_index(path)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/load")
async def load_index(path: Optional[str] = None) -> Dict[str, str]:
    """加载索引"""
    try:
        knowledge_service.load_index(path)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
