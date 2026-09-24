"""
FAISS Knowledge Service Tests
"""
import numpy as np
import pytest
from integrations.faiss_knowledge_service import FaissKnowledgeService, SearchRequest


class TestFaissKnowledgeService:
    """FAISS 服务测试"""
    
    def test_create_index_flat(self):
        """测试创建 Flat 索引"""
        service = FaissKnowledgeService()
        index = service.create_index(dimension=384, index_type="Flat")
        
        assert index is not None
        assert index.d == 384
    
    def test_create_index_ivf(self):
        """测试创建 IVF 索引"""
        service = FaissKnowledgeService()
        index = service.create_index(dimension=384, index_type="IVF")
        
        assert index is not None
        assert index.d == 384
    
    def test_add_vectors(self):
        """测试添加向量"""
        service = FaissKnowledgeService()
        service.index = service.create_index(dimension=128)  # Fix: assign index
        
        vectors = np.random.randn(10, 128).astype(np.float32)
        ids = [f"vec_{i}" for i in range(10)]
        metadatas = [{"id": i, "content": f"test_{i}"} for i in range(10)]
        
        service.add_vectors(vectors, ids, metadatas)
        
        assert len(service.vectors) == 10
    
    def test_search(self):
        """测试搜索功能"""
        service = FaissKnowledgeService()
        service.index = service.create_index(dimension=128)  # Fix
        
        # 添加测试向量
        vectors = np.random.randn(10, 128).astype(np.float32)
        ids = [f"vec_{i}" for i in range(10)]
        metadatas = [{"id": i, "content": f"test_{i}"} for i in range(10)]
        
        service.add_vectors(vectors, ids, metadatas)
        
        # 搜索
        query = np.random.randn(128).astype(np.float32)
        results = service.search(query, top_k=5)
        
        assert len(results) == 5
        assert all(hasattr(r, 'score') for r in results)
        assert all(hasattr(r, 'metadata') for r in results)
    
    def test_get_info(self):
        """测试获取索引信息"""
        service = FaissKnowledgeService()
        service.index = service.create_index(dimension=256)  # Fix
        
        info = service.get_info()
        
        assert info.dimension == 256
        assert info.n_vectors == 0
        assert info.index_type == "IndexFlat"
    
    def test_save_load_index(self, tmp_path):
        """测试保存和加载索引"""
        service = FaissKnowledgeService(str(tmp_path / "faiss_test"))
        service.index = service.create_index(dimension=64)  # Fix
        
        # 添加向量
        vectors = np.random.randn(5, 64).astype(np.float32)
        ids = [f"vec_{i}" for i in range(5)]
        metadatas = [{"id": i} for i in range(5)]
        
        service.add_vectors(vectors, ids, metadatas)
        
        # 保存
        service.save_index()
        
        # 重新加载
        new_service = FaissKnowledgeService(str(tmp_path / "faiss_test"))
        new_service.load_index()
        
        assert new_service.index is not None
        assert new_service.index.ntotal == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
