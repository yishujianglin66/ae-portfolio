#!/usr/bin/env python3
"""
FAISS 向量索引加速器 (D1b)

替代 JSON 文件中的向量线性扫描，提供 O(log n) 近似最近邻检索。
与 media_metadata_db.py 配合使用：
    - SQLite 负责元数据查询
    - FAISS 负责向量相似度检索

架构：
    查询文本 → CLIP 编码 → FAISS 检索 → 返回 file_path + similarity
    配合 SQLite 做后过滤（BPM/情绪/曲风）

用法：
    from vector_index_faiss import VectorIndex

    idx = VectorIndex(dim=512)
    idx.add(file_paths, vectors)
    results = idx.search(query_vector, top_k=20)
    idx.save("path/to/index.faiss")

降级：
    FAISS 未安装时自动回退到 numpy 暴力搜索（功能不变，速度慢 ~10x）

迁移：
    python vector_index_faiss.py --migrate-from-json path/to/index.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_INDEX_DIR = _PROJECT_ROOT / "data"

# FAISS 可用性检测
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class VectorIndex:
    """向量索引，支持 FAISS 加速和 numpy 降级"""

    def __init__(self, dim: int = 512, index_path: Optional[str] = None):
        self.dim = dim
        self._index_path = index_path
        self._file_paths: List[str] = []     # ID → file_path 映射
        self._metadata: List[Dict] = []       # ID → metadata 映射
        self._faiss_index = None
        self._numpy_vectors: Optional[np.ndarray] = None  # 降级用

        if FAISS_AVAILABLE:
            # 使用内积索引（归一化向量等价于余弦相似度）
            self._faiss_index = faiss.IndexFlatIP(dim)
        else:
            print("[VectorIndex] FAISS 未安装，使用 numpy 暴力搜索", file=sys.stderr)

    @property
    def size(self) -> int:
        return len(self._file_paths)

    @property
    def using_faiss(self) -> bool:
        return FAISS_AVAILABLE and self._faiss_index is not None

    # ------------------------------------------------------------------
    # 索引构建
    # ------------------------------------------------------------------

    def add(self, file_paths: List[str], vectors: np.ndarray, metadata: Optional[List[Dict]] = None):
        """添加向量到索引

        Args:
            file_paths: 文件路径列表
            vectors: 向量矩阵 (N, dim)，应为 float32 归一化向量
            metadata: 可选的元数据列表
        """
        if len(file_paths) == 0:
            return

        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        if vectors.shape[1] != self.dim:
            raise ValueError(f"向量维度不匹配: 期望 {self.dim}, 实际 {vectors.shape[1]}")

        # 归一化（使内积等价于余弦相似度）
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vectors = vectors / norms

        self._file_paths.extend(file_paths)
        if metadata:
            self._metadata.extend(metadata)
        else:
            self._metadata.extend([{}] * len(file_paths))

        if self.using_faiss:
            self._faiss_index.add(vectors)
        else:
            if self._numpy_vectors is None:
                self._numpy_vectors = vectors
            else:
                self._numpy_vectors = np.vstack([self._numpy_vectors, vectors])

    def add_single(self, file_path: str, vector: np.ndarray, metadata: Optional[Dict] = None):
        """添加单个向量"""
        self.add([file_path], vector.reshape(1, -1), [metadata] if metadata else None)

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    def search(self, query_vector: np.ndarray, top_k: int = 20) -> List[Dict[str, Any]]:
        """搜索最相似的向量

        Args:
            query_vector: 查询向量 (dim,)
            top_k: 返回数量

        Returns:
            [{"file_path": str, "similarity": float, "rank": int, "metadata": dict}, ...]
        """
        if self.size == 0:
            return []

        query = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)
        # 归一化查询
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        actual_k = min(top_k, self.size)

        if self.using_faiss:
            similarities, indices = self._faiss_index.search(query, actual_k)
            similarities = similarities[0]
            indices = indices[0]
        else:
            # numpy 降级：暴力余弦相似度
            sims = self._numpy_vectors @ query.T
            sims = sims.flatten()
            top_indices = np.argsort(sims)[::-1][:actual_k]
            indices = top_indices
            similarities = sims[top_indices]

        results = []
        for rank, (idx, sim) in enumerate(zip(indices, similarities)):
            if idx < 0 or idx >= len(self._file_paths):
                continue
            results.append({
                "file_path": self._file_paths[idx],
                "similarity": round(float(sim), 4),
                "rank": rank + 1,
                "metadata": self._metadata[idx] if idx < len(self._metadata) else {},
            })

        return results

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def save(self, path: Optional[str] = None):
        """保存索引到磁盘"""
        save_path = path or self._index_path
        if not save_path:
            save_path = str(_DEFAULT_INDEX_DIR / "clip_vectors.faiss")

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # 保存 FAISS 索引
        if self.using_faiss and self._faiss_index:
            faiss.write_index(self._faiss_index, save_path)

        # 保存映射关系（JSON sidecar）
        meta_path = save_path + ".meta.json"
        meta = {
            "dim": self.dim,
            "size": self.size,
            "file_paths": self._file_paths,
            "metadata": self._metadata,
            "using_faiss": self.using_faiss,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

    def load(self, path: Optional[str] = None) -> bool:
        """从磁盘加载索引"""
        load_path = path or self._index_path
        if not load_path:
            load_path = str(_DEFAULT_INDEX_DIR / "clip_vectors.faiss")

        meta_path = load_path + ".meta.json"
        if not os.path.exists(meta_path):
            return False

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.dim = meta.get("dim", self.dim)
        self._file_paths = meta.get("file_paths", [])
        self._metadata = meta.get("metadata", [])

        if self.using_faiss and os.path.exists(load_path):
            self._faiss_index = faiss.read_index(load_path)
            return True
        elif os.path.exists(load_path):
            # FAISS 不可用但有索引文件 → 无法加载向量到 numpy
            # 需要从 JSON 重新构建
            return False

        return False

    # ------------------------------------------------------------------
    # JSON 迁移
    # ------------------------------------------------------------------

    def migrate_from_json(self, json_path: str) -> Dict[str, Any]:
        """从 CLIP index.json 迁移向量到 FAISS 索引

        Args:
            json_path: index.json 文件路径

        Returns:
            迁移统计
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        dim = data.get("vector_dim", self.dim)
        self.dim = dim

        file_paths = []
        vectors = []
        metadata_list = []

        for item in items:
            fp = item.get("file_path", "")
            vec = item.get("vector", [])
            if not fp or not vec:
                continue
            file_paths.append(fp)
            vectors.append(vec)
            metadata_list.append(item.get("metadata", {}))

        if vectors:
            vec_array = np.array(vectors, dtype=np.float32)
            self.add(file_paths, vec_array, metadata_list)

        return {
            "migrated": len(file_paths),
            "dim": dim,
            "using_faiss": self.using_faiss,
            "total_in_json": len(items),
        }


# ------------------------------------------------------------------
# 与 multimodal_retriever.py 集成接口
# ------------------------------------------------------------------

def create_retriever_with_faiss(
    index_json_path: str,
    faiss_index_path: Optional[str] = None,
) -> VectorIndex:
    """从现有 JSON 索引创建 FAISS 加速的检索器

    用法：
        idx = create_retriever_with_faiss("path/to/index.json")
        results = idx.search(query_vector, top_k=20)
    """
    idx = VectorIndex(index_path=faiss_index_path)

    # 尝试加载已有 FAISS 索引
    if idx.load(faiss_index_path):
        return idx

    # 从 JSON 迁移
    idx.migrate_from_json(index_json_path)

    # 保存 FAISS 索引供下次使用
    if idx.using_faiss:
        idx.save(faiss_index_path)

    return idx


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def _cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="FAISS 向量索引管理器")
    parser.add_argument("--migrate-from-json", type=str, help="从 JSON 索引迁移")
    parser.add_argument("--save", type=str, help="保存路径")
    parser.add_argument("--stats", action="store_true", help="显示统计")
    parser.add_argument("--benchmark", type=str, help="性能测试 (JSON 路径)")
    args = parser.parse_args()

    if args.migrate_from_json:
        idx = VectorIndex()
        print(f"从 JSON 迁移: {args.migrate_from_json}")
        result = idx.migrate_from_json(args.migrate_from_json)
        print(f"迁移完成: {json.dumps(result, ensure_ascii=False, indent=2)}")

        save_path = args.save or str(_DEFAULT_INDEX_DIR / "clip_vectors.faiss")
        idx.save(save_path)
        print(f"索引已保存: {save_path}")

    elif args.benchmark:
        # 性能对比
        import time

        print("加载 JSON 索引...")
        with open(args.benchmark, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        dim = data.get("vector_dim", 512)
        vectors = np.array([item["vector"] for item in items if item.get("vector")], dtype=np.float32)
        query = vectors[0] if len(vectors) > 0 else np.random.randn(dim).astype(np.float32)

        # numpy 暴力搜索
        print(f"\n=== 暴力搜索 (numpy) ===")
        print(f"索引大小: {len(vectors)} 向量, 维度: {dim}")
        start = time.perf_counter()
        for _ in range(100):
            sims = vectors @ query
            top_idx = np.argsort(sims)[::-1][:20]
        numpy_time = (time.perf_counter() - start) / 100
        print(f"100 次搜索平均: {numpy_time*1000:.2f}ms")

        # FAISS
        if FAISS_AVAILABLE:
            print(f"\n=== FAISS 搜索 ===")
            idx = VectorIndex(dim=dim)
            paths = [item.get("file_path", "") for item in items if item.get("vector")]
            idx.add(paths, vectors)
            start = time.perf_counter()
            for _ in range(100):
                idx.search(query, top_k=20)
            faiss_time = (time.perf_counter() - start) / 100
            print(f"100 次搜索平均: {faiss_time*1000:.2f}ms")
            print(f"加速比: {numpy_time/faiss_time:.1f}x")
        else:
            print("\nFAISS 未安装，无法进行对比测试")
            print("安装: pip install faiss-cpu")

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli_main()
