"""
智能排序器 - 多维度智能排序

核心功能：
1. 多维度评分融合
2. 个性化偏好权重调整
3. 多样性保障
4. 结果重排序
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional


class SmartRanker:
    """智能排序器"""
    
    # 默认权重配置（扩展版）
    DEFAULT_WEIGHTS = {
        "semantic": 0.25,      # 语义相似度
        "quality": 0.20,       # 质量评分
        "audio": 0.15,         # 音频匹配
        "popularity": 0.10,    # 热度
        "freshness": 0.08,     # 新鲜度
        "duration_match": 0.08, # 时长匹配
        "bpm_match": 0.07,     # BPM匹配
        "keyword_match": 0.07, # 关键词匹配
        "diversity": 0.00,     # 多样性惩罚（负向）
    }
    
    # 情绪权重调整（扩展版）
    MOOD_WEIGHT_ADJUSTMENTS = {
        "happy": {"semantic": 1.1, "audio": 1.1, "popularity": 1.1},
        "excited": {"semantic": 1.0, "audio": 1.3, "popularity": 1.2},
        "sad": {"semantic": 1.2, "audio": 1.1, "popularity": 0.9},
        "calm": {"semantic": 1.1, "audio": 1.1, "popularity": 0.9},
        "relaxed": {"semantic": 1.1, "audio": 1.1, "popularity": 0.9},
        "romantic": {"semantic": 1.2, "audio": 1.3, "popularity": 1.0},
        "energetic": {"semantic": 1.0, "audio": 1.3, "popularity": 1.2},
        "epic": {"semantic": 1.2, "audio": 1.2, "popularity": 1.1},
        "inspirational": {"semantic": 1.1, "audio": 1.2, "popularity": 1.1},
        "funny": {"semantic": 1.0, "audio": 1.0, "popularity": 1.2},
        "scary": {"semantic": 1.1, "audio": 1.2, "popularity": 1.0},
        "mysterious": {"semantic": 1.2, "audio": 1.1, "popularity": 1.0},
        "cool": {"semantic": 1.0, "audio": 1.1, "popularity": 1.2},
        "vintage": {"semantic": 1.1, "audio": 1.0, "popularity": 0.9},
        "healing": {"semantic": 1.1, "audio": 1.1, "popularity": 0.9},
        "ethereal": {"semantic": 1.2, "audio": 1.1, "popularity": 0.9},
        "emotional": {"semantic": 1.2, "audio": 1.2, "popularity": 1.0},
        "tense": {"semantic": 1.1, "audio": 1.2, "popularity": 1.0},
    }
    
    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
    
    def rank(
        self,
        results: list[dict[str, Any]],
        query_mood: str | None = None,
        query_genre: str | None = None,
        query_bpm: float | None = None,
        diversity: bool = True,
        top_k: int = 20
    ) -> list[dict[str, Any]]:
        """
        智能排序
        
        参数:
            results: 待排序的结果列表
            query_mood: 查询情绪（用于调整权重）
            query_genre: 查询曲风（用于调整权重）
            query_bpm: 查询BPM（用于调整权重）
            diversity: 是否启用多样性保障
            top_k: 返回结果数
        
        返回:
            排序后的结果列表
        """
        if not results:
            return []
        
        # 计算各项分数
        scored_results = self._score_results(results, query_mood, query_genre, query_bpm)
        
        # 如果启用多样性保障，进行重排序
        if diversity:
            scored_results = self._ensure_diversity(scored_results)
        
        # 按最终分数排序
        scored_results.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        
        return scored_results[:top_k]
    
    def _score_results(
        self,
        results: list[dict[str, Any]],
        query_mood: str | None,
        query_genre: str | None,
        query_bpm: float | None
    ) -> list[dict[str, Any]]:
        """计算各项分数并融合"""
        scored = []
        
        # 获取情绪调整权重
        mood_adjustments = self.MOOD_WEIGHT_ADJUSTMENTS.get(query_mood, {}) if query_mood else {}
        
        for result in results:
            scores = {}
            
            # 语义相似度分数
            semantic_score = result.get("similarity", result.get("combined_score", 0.0))
            try:
                semantic_score = float(semantic_score)
            except (ValueError, TypeError):
                semantic_score = 0.0
            semantic_weight = self.weights["semantic"] * mood_adjustments.get("semantic", 1.0)
            scores["semantic"] = round(semantic_score * semantic_weight, 4)
            
            # 质量分数
            quality_score = result.get("quality_score", 0.5)
            try:
                quality_score = float(quality_score)
            except (ValueError, TypeError):
                quality_score = 0.5
            scores["quality"] = round(quality_score * self.weights["quality"], 4)
            
            # 音频匹配分数
            audio_score = result.get("audio_match_score", result.get("audio_features", {}).get("mood_score", 0.5))
            try:
                audio_score = float(audio_score)
            except (ValueError, TypeError):
                audio_score = 0.5
            audio_weight = self.weights["audio"] * mood_adjustments.get("audio", 1.0)
            scores["audio"] = round(audio_score * audio_weight, 4)
            
            # 热度分数
            popularity_score = self._calculate_popularity_score(result)
            popularity_weight = self.weights["popularity"] * mood_adjustments.get("popularity", 1.0)
            scores["popularity"] = round(popularity_score * popularity_weight, 4)
            
            # 新鲜度分数（假设metadata中有timestamp）
            freshness_score = self._calculate_freshness_score(result)
            scores["freshness"] = round(freshness_score * self.weights["freshness"], 4)
            
            # 时长匹配分数
            duration_match_score = self._calculate_duration_match_score(result, query_bpm)
            scores["duration_match"] = round(duration_match_score * self.weights["duration_match"], 4)
            
            # BPM匹配分数
            bpm_match_score = self._calculate_bpm_match_score(result, query_bpm)
            scores["bpm_match"] = round(bpm_match_score * self.weights["bpm_match"], 4)
            
            # 关键词匹配分数
            keyword_match_score = self._calculate_keyword_match_score(result, query_genre, query_mood)
            scores["keyword_match"] = round(keyword_match_score * self.weights["keyword_match"], 4)
            
            # 计算最终分数
            final_score = sum(scores.values())
            
            # 添加额外信息
            result_with_scores = result.copy()
            result_with_scores["scores"] = scores
            result_with_scores["final_score"] = round(final_score, 4)
            
            scored.append(result_with_scores)
        
        return scored
    
    def _calculate_popularity_score(self, result: dict[str, Any]) -> float:
        """计算热度分数"""
        view_count = result.get("view_count", 0)
        like_count = result.get("like_count", 0)
        download_count = result.get("download_count", 0)
        
        # 归一化处理
        max_view = 10000000
        max_like = 1000000
        max_download = 100000
        
        view_norm = min(view_count / max_view, 1.0)
        like_norm = min(like_count / max_like, 1.0)
        download_norm = min(download_count / max_download, 1.0)
        
        # 热度 = 观看量(0.5) + 点赞量(0.3) + 下载量(0.2)
        return view_norm * 0.5 + like_norm * 0.3 + download_norm * 0.2
    
    def _calculate_freshness_score(self, result: dict[str, Any]) -> float:
        """计算新鲜度分数"""
        # 假设metadata中有upload_time或timestamp
        metadata = result.get("metadata", {})
        
        # 如果没有时间信息，默认给0.5
        if not metadata:
            return 0.5
        
        # 简化处理：如果有时间戳，计算相对新鲜度
        upload_time = metadata.get("upload_time", "")
        if upload_time:
            try:
                from datetime import datetime
                upload_date = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
                now = datetime.now()
                days_old = (now - upload_date).days
                
                # 新鲜度：1天内1.0，30天内0.7，90天内0.5，超过90天0.3
                if days_old <= 1:
                    return 1.0
                elif days_old <= 30:
                    return 0.7
                elif days_old <= 90:
                    return 0.5
                else:
                    return 0.3
            except Exception:
                pass
        
        return 0.5
    
    def _calculate_duration_match_score(self, result: dict[str, Any], query_bpm: float | None) -> float:
        """计算时长匹配分数
        
        根据BPM推断期望时长，匹配度越高分数越高
        """
        metadata = result.get("metadata", {})
        duration = metadata.get("duration", 0)
        
        if duration <= 0:
            return 0.5
        
        expected_duration = 180
        if query_bpm:
            if query_bpm < 90:
                expected_duration = 240
            elif query_bpm < 120:
                expected_duration = 180
            elif query_bpm < 150:
                expected_duration = 150
            else:
                expected_duration = 120
        
        diff_ratio = abs(duration - expected_duration) / max(duration, expected_duration)
        
        return max(0.0, 1.0 - diff_ratio)
    
    def _calculate_bpm_match_score(self, result: dict[str, Any], query_bpm: float | None) -> float:
        """计算BPM匹配分数"""
        if query_bpm is None:
            return 0.5
        
        audio_features = result.get("audio_features", {})
        result_bpm = audio_features.get("bpm", query_bpm)
        
        if result_bpm <= 0:
            return 0.5
        
        diff_ratio = abs(result_bpm - query_bpm) / query_bpm
        
        return max(0.0, 1.0 - diff_ratio * 2)
    
    def _calculate_keyword_match_score(self, result: dict[str, Any], query_genre: str | None, query_mood: str | None) -> float:
        """计算关键词匹配分数"""
        matches = 0
        total = 0
        
        if query_genre:
            total += 1
            audio_features = result.get("audio_features", {})
            result_genre = audio_features.get("genre", "")
            if result_genre and query_genre.lower() in result_genre.lower():
                matches += 1
        
        if query_mood:
            total += 1
            audio_features = result.get("audio_features", {})
            result_mood = audio_features.get("mood", "")
            if result_mood and query_mood.lower() in result_mood.lower():
                matches += 1
        
        if total == 0:
            return 0.5
        
        return matches / total
    
    def _ensure_diversity(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        保障结果多样性（优化版）
        
        策略：
        1. 平台多样性 - 避免单一平台垄断
        2. 情绪多样性 - 避免情绪单一
        3. 曲风多样性 - 避免曲风单一
        4. 时长范围多样性 - 避免时长过于集中
        5. BPM范围多样性 - 避免节奏过于集中
        
        采用增量惩罚机制：排名越靠前的结果惩罚越小
        """
        if len(results) <= 1:
            for r in results:
                r["diversity_penalty"] = 0.0
                r["diversity_penalty_details"] = {
                    "platform": 0.0, "mood": 0.0, "genre": 0.0, 
                    "duration": 0.0, "bpm": 0.0
                }
            return results
        
        total_count = len(results)
        
        # 统计各维度分布
        platform_counts = defaultdict(int)
        mood_counts = defaultdict(int)
        genre_counts = defaultdict(int)
        duration_range_counts = defaultdict(int)
        bpm_range_counts = defaultdict(int)
        
        for result in results:
            platform = result.get("platform", "unknown")
            platform_counts[platform] += 1
            
            audio_features = result.get("audio_features", {})
            mood = audio_features.get("mood", "unknown")
            mood_counts[mood] += 1
            
            genre = audio_features.get("genre", "unknown")
            genre_counts[genre] += 1
            
            metadata = result.get("metadata", {})
            duration = metadata.get("duration", 0)
            if duration <= 60:
                duration_range = "short"
            elif duration <= 180:
                duration_range = "medium"
            else:
                duration_range = "long"
            duration_range_counts[duration_range] += 1
            
            bpm = audio_features.get("bpm", 0)
            if bpm <= 90:
                bpm_range = "slow"
            elif bpm <= 120:
                bpm_range = "medium"
            else:
                bpm_range = "fast"
            bpm_range_counts[bpm_range] += 1
        
        # 计算各维度的多样性分数（逆向分布）
        max_platform_count = max(platform_counts.values()) if platform_counts else 1
        max_mood_count = max(mood_counts.values()) if mood_counts else 1
        max_genre_count = max(genre_counts.values()) if genre_counts else 1
        max_duration_count = max(duration_range_counts.values()) if duration_range_counts else 1
        max_bpm_count = max(bpm_range_counts.values()) if bpm_range_counts else 1
        
        # 调整分数以增加多样性（采用增量惩罚）
        adjusted = []
        for idx, result in enumerate(results):
            adjusted_result = result.copy()
            
            # 基础惩罚系数（排名越靠前惩罚越小）
            rank_factor = 1.0 - (idx / total_count) * 0.5
            
            audio_features = result.get("audio_features", {})
            metadata = result.get("metadata", {})
            
            # 平台多样性惩罚
            platform = result.get("platform", "unknown")
            platform_ratio = platform_counts[platform] / max_platform_count
            platform_penalty = min(platform_ratio * 0.2, 0.15) * rank_factor
            
            # 情绪多样性惩罚
            mood = audio_features.get("mood", "unknown")
            mood_ratio = mood_counts[mood] / max_mood_count
            mood_penalty = min(mood_ratio * 0.15, 0.1) * rank_factor
            
            # 曲风多样性惩罚
            genre = audio_features.get("genre", "unknown")
            genre_ratio = genre_counts[genre] / max_genre_count
            genre_penalty = min(genre_ratio * 0.15, 0.1) * rank_factor
            
            # 时长范围多样性惩罚
            duration = metadata.get("duration", 0)
            if duration <= 60:
                duration_range = "short"
            elif duration <= 180:
                duration_range = "medium"
            else:
                duration_range = "long"
            duration_ratio = duration_range_counts[duration_range] / max_duration_count
            duration_penalty = min(duration_ratio * 0.1, 0.08) * rank_factor
            
            # BPM范围多样性惩罚
            bpm = audio_features.get("bpm", 0)
            if bpm <= 90:
                bpm_range = "slow"
            elif bpm <= 120:
                bpm_range = "medium"
            else:
                bpm_range = "fast"
            bpm_ratio = bpm_range_counts[bpm_range] / max_bpm_count
            bpm_penalty = min(bpm_ratio * 0.1, 0.08) * rank_factor
            
            # 总惩罚
            total_penalty = platform_penalty + mood_penalty + genre_penalty + duration_penalty + bpm_penalty
            
            # 应用惩罚
            final_score = result.get("final_score", 0.0)
            final_score *= (1.0 - total_penalty)
            
            adjusted_result["final_score"] = round(final_score, 4)
            adjusted_result["diversity_penalty"] = round(total_penalty, 4)
            adjusted_result["diversity_penalty_details"] = {
                "platform": round(platform_penalty, 4),
                "mood": round(mood_penalty, 4),
                "genre": round(genre_penalty, 4),
                "duration": round(duration_penalty, 4),
                "bpm": round(bpm_penalty, 4)
            }
            
            adjusted.append(adjusted_result)
        
        return adjusted
    
    def adjust_weights(self, preferences: dict[str, float]) -> None:
        """
        根据用户偏好调整权重
        
        参数:
            preferences: 偏好权重调整字典
        """
        for key, adjustment in preferences.items():
            if key in self.weights:
                self.weights[key] = min(max(self.weights[key] * adjustment, 0.01), 0.99)
    
    def get_weight_summary(self) -> dict[str, float]:
        """获取当前权重配置"""
        return self.weights.copy()


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python smart_ranker.py --json-input '<JSON字符串>'")
        print("示例: python smart_ranker.py --json-input '{\"action\": \"rank\", \"results\": [...], \"query_mood\": \"happy\"}'")
        sys.exit(1)
    
    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)
    
    try:
        input_json = json.loads(sys.argv[2])
        action = input_json.get("action", "")
        
        result: dict[str, Any] = {"success": False, "results": []}
        
        if action == "rank":
            results = input_json.get("results", [])
            query_mood = input_json.get("query_mood")
            query_genre = input_json.get("query_genre")
            query_bpm = input_json.get("query_bpm")
            diversity = input_json.get("diversity", True)
            top_k = input_json.get("top_k", 20)
            
            ranker = SmartRanker()
            ranked_results = ranker.rank(results, query_mood, query_genre, query_bpm, diversity, top_k)
            
            result["results"] = ranked_results
            result["weights"] = ranker.get_weight_summary()
            result["success"] = True
        
        elif action == "adjust_weights":
            preferences = input_json.get("preferences", {})
            
            ranker = SmartRanker()
            ranker.adjust_weights(preferences)
            
            result["weights"] = ranker.get_weight_summary()
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
