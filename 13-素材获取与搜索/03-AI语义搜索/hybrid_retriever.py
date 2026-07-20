"""
联合检索器 - CLIP语义搜索与音频特征的联合检索

核心功能：
1. CLIP语义检索（文本/图片/标签）
2. 音频特征过滤（BPM/情绪/曲风）
3. 多模态融合排序
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from clip_searcher import get_model, encode_text, encode_image, cosine_similarity, load_index


class HybridRetriever:
    """联合检索器"""
    
    def __init__(self):
        self.model = None
    
    def _ensure_model(self) -> None:
        """确保模型已加载"""
        if self.model is None:
            self.model = get_model()
    
    def semantic_search(
        self,
        query: str,
        index_path: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        CLIP语义搜索
        
        返回:
            [{file_path, similarity, metadata}]
        """
        self._ensure_model()
        
        index_data = load_index(index_path)
        if index_data is None or "items" not in index_data:
            return []
        
        query_vector = encode_text(self.model, query)
        if query_vector is None:
            return []
        
        results = []
        for item in index_data["items"]:
            file_path = item.get("file_path", "")
            if not os.path.exists(file_path):
                continue
            
            vector = np.array(item.get("vector", []))
            metadata = item.get("metadata", {})

            # 跳过空向量或维度不匹配的项，避免 cosine_similarity 抛出 ValueError
            if vector.size == 0 or vector.shape != query_vector.shape:
                continue

            try:
                similarity = cosine_similarity(query_vector, vector)
            except (ValueError, TypeError):
                continue

            results.append({
                "file_path": file_path,
                "similarity": round(float(similarity), 4),
                "metadata": metadata,
                "source": "local_index"
            })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def search_by_image(
        self,
        image_path: str,
        index_path: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        图片搜索
        
        返回:
            [{file_path, similarity, metadata}]
        """
        self._ensure_model()
        
        index_data = load_index(index_path)
        if index_data is None or "items" not in index_data:
            return []
        
        query_vector = encode_image(self.model, image_path)
        if query_vector is None:
            return []
        
        results = []
        for item in index_data["items"]:
            file_path = item.get("file_path", "")
            if not os.path.exists(file_path) or file_path == image_path:
                continue
            
            vector = np.array(item.get("vector", []))
            metadata = item.get("metadata", {})

            # 跳过空向量或维度不匹配的项，避免 cosine_similarity 抛出 ValueError
            if vector.size == 0 or vector.shape != query_vector.shape:
                continue

            try:
                similarity = cosine_similarity(query_vector, vector)
            except (ValueError, TypeError):
                continue

            results.append({
                "file_path": file_path,
                "similarity": round(float(similarity), 4),
                "metadata": metadata,
                "source": "local_index"
            })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def filter_by_audio_features(
        self,
        items: List[Dict[str, Any]],
        target_bpm: Optional[float] = None,
        bpm_range: Optional[tuple] = None,
        mood: Optional[str] = None,
        genre: Optional[str] = None,
        duration_range: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """
        根据音频特征过滤结果
        
        参数:
            items: 待过滤的结果列表
            target_bpm: 目标BPM
            bpm_range: BPM范围
            mood: 情绪标签
            genre: 曲风标签
        
        返回:
            过滤后的结果列表（增加 audio_match_score）
        """
        filtered = []
        
        for item in items:
            metadata = item.get("metadata", {})
            audio_features = metadata.get("audio_features", {})
            
            score = 1.0
            reasons = []
            
            # BPM匹配
            if target_bpm and audio_features.get("bpm"):
                item_bpm = float(audio_features["bpm"])
                if bpm_range:
                    if bpm_range[0] <= item_bpm <= bpm_range[1]:
                        reasons.append(f"BPM在范围内")
                    else:
                        bpm_diff = abs(item_bpm - target_bpm)
                        score *= max(0.3, 1.0 - bpm_diff / 60)
                        reasons.append(f"BPM偏差{int(bpm_diff)}")
                else:
                    bpm_diff = abs(item_bpm - target_bpm)
                    score *= max(0.3, 1.0 - bpm_diff / 60)
            
            # 情绪匹配
            if mood and audio_features.get("mood"):
                item_mood = audio_features["mood"].lower()
                if mood.lower() in item_mood or item_mood in mood.lower():
                    score *= 1.1
                    reasons.append(f"情绪匹配:{item_mood}")
                else:
                    score *= 0.7
            
            # 曲风匹配
            if genre and audio_features.get("genre"):
                item_genre = audio_features["genre"].lower()
                if genre.lower() in item_genre or item_genre in genre.lower():
                    score *= 1.1
                    reasons.append(f"曲风匹配:{item_genre}")
                else:
                    score *= 0.7
            
            # 时长过滤
            if duration_range and metadata.get("duration"):
                duration = float(metadata["duration"])
                if not (duration_range[0] <= duration <= duration_range[1]):
                    score *= 0.5
            
            item_with_score = item.copy()
            item_with_score["audio_match_score"] = round(min(score, 1.0), 4)
            item_with_score["match_reasons"] = reasons
            
            filtered.append(item_with_score)
        
        # 按音频匹配分数排序
        filtered.sort(key=lambda x: x.get("audio_match_score", 1.0), reverse=True)
        return filtered
    
    def hybrid_search(
        self,
        query: str,
        index_path: str,
        top_k: int = 20,
        target_bpm: Optional[float] = None,
        bpm_range: Optional[tuple] = None,
        mood: Optional[str] = None,
        genre: Optional[str] = None,
        duration_range: Optional[tuple] = None,
        semantic_weight: float = 0.7,
        audio_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        联合检索：CLIP语义 + 音频特征
        
        参数:
            query: 语义查询
            index_path: 索引路径
            top_k: 返回结果数
            semantic_weight: 语义权重
            audio_weight: 音频特征权重
        
        返回:
            融合排序后的结果列表
        """
        # 先进行语义搜索
        semantic_results = self.semantic_search(query, index_path, top_k * 2)
        
        if not semantic_results:
            return []
        
        # 再进行音频特征过滤
        filtered_results = self.filter_by_audio_features(
            semantic_results,
            target_bpm=target_bpm,
            bpm_range=bpm_range,
            mood=mood,
            genre=genre,
            duration_range=duration_range
        )
        
        # 融合排序
        final_results = []
        for item in filtered_results:
            semantic_score = item.get("similarity", 0.0)
            audio_score = item.get("audio_match_score", 1.0)
            
            combined_score = semantic_score * semantic_weight + audio_score * audio_weight
            
            final_item = item.copy()
            final_item["combined_score"] = round(combined_score, 4)
            final_item["semantic_weight"] = semantic_weight
            final_item["audio_weight"] = audio_weight
            
            final_results.append(final_item)
        
        final_results.sort(key=lambda x: x["combined_score"], reverse=True)
        return final_results[:top_k]


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python hybrid_retriever.py --json-input '<JSON字符串>'")
        print("示例: python hybrid_retriever.py --json-input '{\"action\": \"hybrid_search\", \"query\": \"夕阳下的海滩\", \"index_path\": \"index.json\", \"target_bpm\": 120}'")
        sys.exit(1)
    
    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)
    
    try:
        input_json = json.loads(sys.argv[2])
        action = input_json.get("action", "")
        
        retriever = HybridRetriever()
        result: Dict[str, Any] = {"success": False, "results": []}
        
        if action == "semantic_search":
            query = input_json.get("query", "")
            index_path = input_json.get("index_path", "")
            top_k = input_json.get("top_k", 20)
            
            results = retriever.semantic_search(query, index_path, top_k)
            result["results"] = results
            result["success"] = True
        
        elif action == "search_by_image":
            image_path = input_json.get("image_path", "")
            index_path = input_json.get("index_path", "")
            top_k = input_json.get("top_k", 20)
            
            results = retriever.search_by_image(image_path, index_path, top_k)
            result["results"] = results
            result["success"] = True
        
        elif action == "hybrid_search":
            query = input_json.get("query", "")
            index_path = input_json.get("index_path", "")
            top_k = input_json.get("top_k", 20)
            target_bpm = input_json.get("target_bpm")
            bpm_range = input_json.get("bpm_range")
            mood = input_json.get("mood")
            genre = input_json.get("genre")
            duration_range = input_json.get("duration_range")
            semantic_weight = input_json.get("semantic_weight", 0.7)
            audio_weight = input_json.get("audio_weight", 0.3)
            
            results = retriever.hybrid_search(
                query, index_path, top_k,
                target_bpm=target_bpm,
                bpm_range=bpm_range,
                mood=mood,
                genre=genre,
                duration_range=duration_range,
                semantic_weight=semantic_weight,
                audio_weight=audio_weight
            )
            result["results"] = results
            result["success"] = True
        
        else:
            result["error"] = f"未知操作: {action}"
        
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    except json.JSONDecodeError as e:
        print(json.dumps({
            "success": False,
            "error": f"JSON解析错误: {str(e)}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"执行错误: {str(e)}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
