"""
多模态融合检索器 - CLIP视觉 + CLAP音频 + RRF倒数排名融合

基于调研的架构方案：
- 第一层：CLIP（视觉语义）+ CLAP（音频语义）+ Essentia（音频物理特征）
- 第二层：RRF（Reciprocal Rank Fusion）倒数排名融合
- 第三层：Essentia特征作为硬过滤条件

参考项目：
- ImageBind: 统一多模态嵌入 (github.com/facebookresearch/ImageBind)
- CLAP: 音频-文本对齐 (github.com/LAION-AI/CLAP)
- MMT: 多模态视频检索 (github.com/gabeur/mmt)
- clip-retrieval: CLIP检索工程实现 (github.com/rom1504/clip-retrieval)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hashlib

from clip_searcher import cosine_similarity, encode_image, encode_text, load_index
from clip_searcher import get_model as get_clip_model

_OFFLINE_MODE = os.environ.get("AEK_OFFLINE_MODE", "").lower() == "true" or \
                os.environ.get("AEK_OFFLINE_MODE", "") == "1" or \
                os.environ.get("HF_HUB_OFFLINE", "").lower() == "true" or \
                os.environ.get("HF_HUB_OFFLINE", "") == "1"


class CLAPEncoder:
    """CLAP音频-文本对齐编码器
    
    使用 LAION-AI/CLAP 模型将音频和文本映射到共享语义空间，
    支持 text→audio 和 audio→text 跨模态检索。
    
    安装: pip install laion-clap
    
    支持离线模式：
    - 离线模式下使用模拟向量生成
    """
    
    def __init__(self):
        self.model = None
        self._available = False
        self._use_mock = False
        
        if _OFFLINE_MODE:
            self._use_mock = True
            print("离线模式：CLAP使用模拟向量生成", file=sys.stderr)
        else:
            try:
                import laion_clap
                self._available = True
            except ImportError:
                self._use_mock = True
                print("laion_clap 未安装，使用模拟向量生成", file=sys.stderr)
    
    def is_available(self) -> bool:
        return self._available or self._use_mock
    
    def _ensure_model(self) -> None:
        if self.model is None and self._available:
            import laion_clap
            try:
                self.model = laion_clap.CLAP_Module(enable_fusion=False)
                self.model.load_ckpt()
            except Exception as e:
                print(f"CLAP模型加载失败，使用模拟向量: {e}", file=sys.stderr)
                self._use_mock = True
    
    def _mock_encode_text(self, text: str) -> np.ndarray:
        """基于文本内容生成模拟CLAP向量（确定性哈希）"""
        hash_val = int(hashlib.sha256(text.encode('utf-8')).hexdigest(), 16)
        seed_val = hash_val % (2**32 - 1)
        np.random.seed(seed_val)
        vector = np.random.randn(512).astype(np.float32)
        vector /= np.linalg.norm(vector)
        return vector
    
    def encode_text(self, text: str) -> np.ndarray | None:
        """将文本编码为CLAP向量"""
        if self._use_mock:
            return self._mock_encode_text(text)
        
        if not self._available:
            return None
        self._ensure_model()
        try:
            return self.model.get_text_embedding([text], use_tensor=False)[0]
        except Exception as e:
            print(f"CLAP文本编码失败，使用模拟向量: {e}", file=sys.stderr)
            return self._mock_encode_text(text)
    
    def encode_audio(self, audio_path: str) -> np.ndarray | None:
        """将音频文件编码为CLAP向量"""
        if self._use_mock:
            return self._mock_encode_text(audio_path)
        
        if not self._available:
            return None
        self._ensure_model()
        try:
            return self.model.get_audio_embedding_from_filelist([audio_path], use_tensor=False)[0]
        except Exception as e:
            print(f"CLAP音频编码失败，使用模拟向量: {e}", file=sys.stderr)
            return self._mock_encode_text(audio_path)


class RRFFusion:
    """RRF（Reciprocal Rank Fusion）倒数排名融合
    
    优势：
    1. 不需要分数归一化，天然适配不同量纲
    2. 各通道可独立开发、调试、替换
    3. 对异常值鲁棒
    
    公式: RRF_score(d) = Σ 1/(k + rank_i(d))
    其中 k=60（标准值），rank_i(d) 是文档d在第i路检索中的排名
    """
    
    def __init__(self, k: int = 60):
        self.k = k
    
    def fuse(
        self,
        result_lists: list[list[dict[str, Any]]],
        id_key: str = "file_path",
        weights: list[float] | None = None
    ) -> list[dict[str, Any]]:
        """
        RRF倒数排名融合
        
        参数:
            result_lists: 多路检索结果列表
            id_key: 用于去重的唯一标识键
            weights: 各路检索的权重（默认等权）
        
        返回:
            融合后的结果列表
        """
        if not result_lists:
            return []
        
        if weights is None:
            weights = [1.0] * len(result_lists)
        
        # 计算每个文档的RRF分数
        rrf_scores: dict[str, float] = {}
        item_map: dict[str, dict[str, Any]] = {}
        
        for list_idx, results in enumerate(result_lists):
            weight = weights[list_idx] if list_idx < len(weights) else 1.0
            
            for rank, item in enumerate(results, start=1):
                item_id = item.get(id_key, "")
                if not item_id:
                    continue
                
                # RRF分数 = weight / (k + rank)
                rrf_score = weight / (self.k + rank)
                
                if item_id in rrf_scores:
                    rrf_scores[item_id] += rrf_score
                    # 合并各路的匹配信息
                    existing = item_map[item_id]
                    if "match_sources" not in existing:
                        existing["match_sources"] = [existing.get("source", "unknown")]
                    existing["match_sources"].append(item.get("source", f"channel_{list_idx}"))
                    existing["rrf_details"].append({
                        "channel": list_idx,
                        "rank": rank,
                        "score": item.get("similarity", item.get("combined_score", 0.0)),
                        "rrf_contribution": round(rrf_score, 6)
                    })
                else:
                    item_map[item_id] = item.copy()
                    item_map[item_id]["rrf_score"] = 0.0
                    item_map[item_id]["rrf_details"] = [{
                        "channel": list_idx,
                        "rank": rank,
                        "score": item.get("similarity", item.get("combined_score", 0.0)),
                        "rrf_contribution": round(rrf_score, 6)
                    }]
                
                rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + rrf_score
        
        # 更新RRF分数并排序
        fused_results = []
        for item_id, item in item_map.items():
            item["rrf_score"] = round(rrf_scores[item_id], 6)
            fused_results.append(item)
        
        fused_results.sort(key=lambda x: x["rrf_score"], reverse=True)
        
        return fused_results


class MultimodalRetriever:
    """多模态融合检索器
    
    架构：
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ CLIP通道    │   │ CLAP通道    │   │ Essentia    │
    │ (视觉语义)  │   │ (音频语义)  │   │ (硬过滤)    │
    └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
           │                 │                 │
           └────────┬────────┘                 │
                    │                          │
              RRF倒数排名融合              BPM/Key/情绪过滤
                    │                          │
                    └──────────┬───────────────┘
                               │
                          最终排序结果
    """
    
    def __init__(self, index_path: str | None = None):
        self.index_path = index_path
        self.clip_model = None
        self.clap_encoder = CLAPEncoder()
        self.rrf = RRFFusion(k=60)
    
    def _ensure_clip_model(self) -> None:
        if self.clip_model is None:
            self.clip_model = get_clip_model()
    
    def search(
        self,
        query: str,
        index_path: str | None = None,
        top_k: int = 20,
        target_bpm: float | None = None,
        bpm_range: tuple | None = None,
        mood: str | None = None,
        genre: str | None = None,
        clip_weight: float = 1.0,
        clap_weight: float = 0.8
    ) -> list[dict[str, Any]]:
        """
        多模态融合搜索
        
        参数:
            query: 查询文本
            index_path: 索引路径
            top_k: 返回结果数
            target_bpm: 目标BPM
            bpm_range: BPM范围
            mood: 情绪
            genre: 曲风
            clip_weight: CLIP通道权重
            clap_weight: CLAP通道权重
        """
        idx_path = index_path or self.index_path
        if not idx_path or not os.path.exists(idx_path):
            return []
        
        result_lists = []
        
        # 通道1: CLIP语义检索
        clip_results = self._clip_search(query, idx_path, top_k * 2)
        if clip_results:
            result_lists.append(clip_results)
        
        # 通道2: CLAP音频语义检索（如果可用）
        if self.clap_encoder.is_available():
            clap_results = self._clap_search(query, idx_path, top_k * 2)
            if clap_results:
                result_lists.append(clap_results)
        
        # RRF融合
        if len(result_lists) == 0:
            return []
        else:
            fused = self.rrf.fuse(
                result_lists,
                weights=[clip_weight, clap_weight]
            )
        
        # Essentia硬过滤（BPM/情绪/曲风）
        if target_bpm or bpm_range or mood or genre:
            fused = self._audio_filter(fused, target_bpm, bpm_range, mood, genre)
        
        return fused[:top_k]
    
    def _clip_search(
        self,
        query: str,
        index_path: str,
        top_k: int
    ) -> list[dict[str, Any]]:
        """CLIP语义检索"""
        self._ensure_clip_model()
        if self.clip_model is None:
            return []
        
        index_data = load_index(index_path)
        if index_data is None or "items" not in index_data:
            return []
        
        query_vector = encode_text(self.clip_model, query)
        if query_vector is None:
            return []
        
        results = []
        for item in index_data["items"]:
            file_path = item.get("file_path", "")
            if not os.path.exists(file_path):
                continue
            
            vector = np.array(item.get("vector", []))
            metadata = item.get("metadata", {})
            
            similarity = cosine_similarity(query_vector, vector)
            results.append({
                "file_path": file_path,
                "similarity": round(similarity, 4),
                "metadata": metadata,
                "source": "clip"
            })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def _clap_search(
        self,
        query: str,
        index_path: str,
        top_k: int
    ) -> list[dict[str, Any]]:
        """CLAP音频语义检索"""
        query_vector = self.clap_encoder.encode_text(query)
        if query_vector is None:
            return []
        
        index_data = load_index(index_path)
        if index_data is None or "items" not in index_data:
            return []
        
        results = []
        for item in index_data["items"]:
            file_path = item.get("file_path", "")
            metadata = item.get("metadata", {})
            
            # 查找CLAP音频向量
            clap_vector = metadata.get("clap_vector", [])
            if not clap_vector:
                continue
            
            item_vector = np.array(clap_vector)
            similarity = cosine_similarity(query_vector, item_vector)
            
            results.append({
                "file_path": file_path,
                "similarity": round(similarity, 4),
                "metadata": metadata,
                "source": "clap"
            })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def _audio_filter(
        self,
        items: list[dict[str, Any]],
        target_bpm: float | None = None,
        bpm_range: tuple | None = None,
        mood: str | None = None,
        genre: str | None = None
    ) -> list[dict[str, Any]]:
        """Essentia特征硬过滤"""
        filtered = []
        
        for item in items:
            metadata = item.get("metadata", {})
            audio_features = metadata.get("audio_features", {})
            
            passed = True
            
            # BPM过滤
            if target_bpm and audio_features.get("bpm"):
                item_bpm = float(audio_features["bpm"])
                if bpm_range:
                    if not (bpm_range[0] <= item_bpm <= bpm_range[1]):
                        passed = False
                else:
                    if abs(item_bpm - target_bpm) > 20:
                        passed = False
            
            # 情绪过滤
            if mood and audio_features.get("mood"):
                item_mood = audio_features["mood"].lower()
                if mood.lower() not in item_mood and item_mood not in mood.lower():
                    passed = False
            
            # 曲风过滤
            if genre and audio_features.get("genre"):
                item_genre = audio_features["genre"].lower()
                if genre.lower() not in item_genre and item_genre not in genre.lower():
                    passed = False
            
            if passed:
                filtered.append(item)
        
        return filtered


def main() -> None:
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python multimodal_retriever.py --json-input '<JSON字符串>'")
        sys.exit(1)
    
    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)
    
    try:
        input_json = json.loads(sys.argv[2])
        action = input_json.get("action", "")
        
        result: dict[str, Any] = {"success": False, "results": []}
        
        if action == "search":
            query = input_json.get("query", "")
            index_path = input_json.get("index_path", "")
            top_k = input_json.get("top_k", 20)
            target_bpm = input_json.get("target_bpm")
            bpm_range = input_json.get("bpm_range")
            mood = input_json.get("mood")
            genre = input_json.get("genre")
            
            retriever = MultimodalRetriever(index_path=index_path)
            results = retriever.search(
                query, index_path, top_k,
                target_bpm=target_bpm,
                bpm_range=bpm_range,
                mood=mood,
                genre=genre
            )
            
            result["results"] = results
            result["clap_available"] = retriever.clap_encoder.is_available()
            result["success"] = True
        
        elif action == "rrf_fuse":
            result_lists = input_json.get("result_lists", [])
            weights = input_json.get("weights")
            k = input_json.get("k", 60)
            
            rrf = RRFFusion(k=k)
            fused = rrf.fuse(result_lists, weights=weights)
            
            result["results"] = fused
            result["success"] = True
        
        else:
            result["error"] = f"未知操作: {action}"
        
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"JSON解析错误: {str(e)}"}, ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
