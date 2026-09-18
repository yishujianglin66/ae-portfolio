"""
素材智能匹配主入口

端到端流程：
用户输入 → 语义解析 → 多模态检索(CLIP+CLAP+Essentia) → 跨平台搜索 → RRF融合 → 智能排序 → 个性化推荐

核心研究点：
1. CLIP 语义搜索与 CLAP 音频嵌入的联合检索 + RRF倒数排名融合
2. Essentia 音频物理特征（BPM/Key/情绪）硬过滤
3. 跨平台素材去重与质量评估
4. 用户偏好学习与个性化推荐

架构参考：
- ImageBind (github.com/facebookresearch/ImageBind): 统一多模态嵌入
- CLAP (github.com/LAION-AI/CLAP): 音频-文本对齐
- MMT (github.com/gabeur/mmt): Late Fusion + Gated Embedding
- clip-retrieval (github.com/rom1504/clip-retrieval): CLIP检索工程实现
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audio_feature_extractor import AudioFeatureExtractor
from cross_platform_searcher import CrossPlatformSearcher
from multimodal_retriever import CLAPEncoder, MultimodalRetriever, RRFFusion
from semantic_parser import ParsedQuery, SemanticParser
from smart_ranker import SmartRanker
from user_preference import UserPreferenceLearner


class SmartMatcher:
    """智能匹配器
    
    端到端流程：
    ┌──────────┐   ┌──────────────┐   ┌─────────────────┐
    │ 用户输入  │ → │ 语义解析器   │ → │ 多模态检索器    │
    └──────────┘   └──────────────┘   │ CLIP+CLAP+RRF  │
                                       └────────┬────────┘
                                                │
                    ┌──────────────┐   ┌────────┴────────┐
                    │ 个性化推荐   │ ← │ 智能排序器      │
                    └──────┬───────┘   │ Essentia过滤    │
                           │           └────────┬────────┘
                           │                    │
                    ┌──────┴───────┐   ┌────────┴────────┐
                    │ 下载推荐     │ ← │ 跨平台搜索器    │
                    └──────────────┘   └─────────────────┘
    """
    
    def __init__(
        self,
        index_path: str | None = None,
        offline_mode: bool | None = None,
        preference_data_dir: str | None = None,
    ):
        self.index_path = index_path or str(Path(__file__).resolve().parent / "index.json")
        self.offline_mode = offline_mode
        
        if self.offline_mode is not None:
            if self.offline_mode:
                os.environ["AEK_OFFLINE_MODE"] = "1"
                os.environ["HF_HUB_OFFLINE"] = "1"
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
            else:
                os.environ.pop("AEK_OFFLINE_MODE", None)
                os.environ.pop("HF_HUB_OFFLINE", None)
                os.environ.pop("TRANSFORMERS_OFFLINE", None)
        
        # 初始化各模块
        self.parser = SemanticParser()
        self.retriever = MultimodalRetriever(index_path=self.index_path)
        self.audio_extractor = AudioFeatureExtractor()
        self.searcher = CrossPlatformSearcher()
        self.ranker = SmartRanker()
        self.preference_learner = UserPreferenceLearner(data_dir=preference_data_dir)
    
    def match(
        self,
        query: str,
        user_id: str = "default",
        top_k: int = 10,
        include_remote: bool = True,
        enable_personalization: bool = True,
        clip_weight: float = 1.0,
        clap_weight: float = 0.8,
        local_weight: float = 0.6,
        remote_weight: float = 0.4
    ) -> dict[str, Any]:
        """
        端到端智能匹配
        
        参数:
            query: 用户输入查询
            user_id: 用户ID（用于个性化推荐）
            top_k: 返回结果数
            include_remote: 是否包含远程平台搜索
            enable_personalization: 是否启用个性化推荐
            clip_weight: CLIP视觉语义通道权重
            clap_weight: CLAP音频语义通道权重
            local_weight: 本地结果权重
            remote_weight: 远程结果权重
        """
        result: dict[str, Any] = {
            "success": False,
            "query": query,
            "user_id": user_id,
            "results": [],
            "parsed_query": {},
            "stats": {}
        }
        
        try:
            # Step 1: 语义解析
            parsed_query = self.parser.parse(query)
            result["parsed_query"] = {
                "semantic_query": parsed_query.semantic_query,
                "target_bpm": parsed_query.target_bpm,
                "bpm_range": parsed_query.bpm_range,
                "mood": parsed_query.mood,
                "genre": parsed_query.genre,
                "media_type": parsed_query.media_type,
                "quality": parsed_query.quality,
                "watermark_free": parsed_query.watermark_free,
                "preferred_platforms": parsed_query.preferred_platforms,
                "tags": parsed_query.tags,
                "confidence": parsed_query.confidence
            }
            
            # Step 2: 多模态检索（CLIP + CLAP + Essentia过滤 + RRF融合）
            local_results = []
            if os.path.exists(self.index_path):
                local_results = self.retriever.search(
                    query=parsed_query.semantic_query or query,
                    index_path=self.index_path,
                    top_k=top_k * 2,
                    target_bpm=parsed_query.target_bpm,
                    bpm_range=parsed_query.bpm_range,
                    mood=parsed_query.mood,
                    genre=parsed_query.genre,
                    clip_weight=clip_weight,
                    clap_weight=clap_weight
                )
            result["stats"]["local_results"] = len(local_results)
            
            # Step 3: 跨平台搜索
            remote_results = []
            if include_remote:
                platforms = parsed_query.preferred_platforms or None
                raw_remote = self.searcher.search(
                    query=parsed_query.semantic_query or query,
                    platforms=platforms,
                    max_results_per_platform=top_k,
                    media_type=parsed_query.media_type
                )
                remote_results = self.searcher.evaluate_quality(raw_remote)
            result["stats"]["remote_results"] = len(remote_results)
            
            # Step 4: 合并结果
            merged_results = self.searcher.merge_results(
                local_results,
                remote_results,
                local_weight=local_weight,
                remote_weight=remote_weight
            )
            result["stats"]["merged_results"] = len(merged_results)
            
            # Step 5: 智能排序
            ranked_results = self.ranker.rank(
                merged_results,
                query_mood=parsed_query.mood,
                query_genre=parsed_query.genre,
                query_bpm=parsed_query.target_bpm,
                diversity=True,
                top_k=top_k * 2
            )
            result["stats"]["ranked_results"] = len(ranked_results)
            
            # Step 6: 个性化推荐
            final_results = ranked_results
            if enable_personalization:
                final_results = self.preference_learner.personalize_results(
                    user_id,
                    ranked_results,
                    top_k=top_k
                )
            
            result["results"] = final_results[:top_k]
            result["success"] = True
            
            # 统计信息
            result["stats"]["total_results"] = len(final_results)
            
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        
        return result
    
    def record_action(
        self,
        user_id: str,
        action_type: str,
        query: str,
        item_id: str,
        item_metadata: dict[str, Any] | None = None,
        duration: float = 0.0,
        position: int = 0
    ) -> None:
        """
        记录用户行为（用于偏好学习）
        
        参数:
            user_id: 用户ID
            action_type: 行为类型（search/click/download/like/skip）
            query: 搜索查询
            item_id: 素材ID/URL
            item_metadata: 素材元数据
            duration: 停留时长（秒）
            position: 结果位置
        """
        from user_preference import UserAction
        self.preference_learner.record_action(UserAction(
            user_id=user_id,
            action_type=action_type,
            query=query,
            item_id=item_id,
            item_metadata=item_metadata or {},
            duration=duration,
            position=position
        ))
    
    def extract_audio_features(self, audio_path: str) -> dict[str, Any]:
        """
        提取音频特征（集成 Essentia/librosa 双引擎）
        
        参数:
            audio_path: 音频文件路径
        
        返回:
            音频特征字典
        """
        features = self.audio_extractor.extract(audio_path)
        return features.to_dict()
    
    def batch_extract_audio_features(self, audio_paths: list[str]) -> list[dict[str, Any]]:
        """
        批量提取音频特征
        
        参数:
            audio_paths: 音频文件路径列表
        
        返回:
            音频特征字典列表
        """
        return self.audio_extractor.extract_batch(audio_paths)
    
    def get_engine_info(self) -> dict[str, Any]:
        """获取当前可用的引擎信息"""
        return {
            "audio": self.audio_extractor.get_engine_info(),
            "clap": self.retriever.clap_encoder.is_available(),
        }
    
    def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        """
        获取用户偏好
        
        参数:
            user_id: 用户ID
        
        返回:
            用户偏好字典
        """
        return self.preference_learner.get_preferences(user_id)
    
    def get_suggested_queries(self, user_id: str, count: int = 5) -> list[str]:
        """
        获取建议搜索词
        
        参数:
            user_id: 用户ID
            count: 返回数量
        
        返回:
            建议搜索词列表
        """
        return self.preference_learner.get_suggested_queries(user_id, count)


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python smart_matcher.py --json-input '<JSON字符串>'")
        print("示例: python smart_matcher.py --json-input '{\"action\": \"match\", \"query\": \"开心的流行音乐 BPM120 抖音 BGM\"}'")
        sys.exit(1)
    
    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)
    
    try:
        input_json = json.loads(sys.argv[2])
        action = input_json.get("action", "")
        
        index_path = input_json.get("index_path")
        matcher = SmartMatcher(index_path=index_path)
        
        result: dict[str, Any] = {"success": False}
        
        if action == "match":
            query = input_json.get("query", "")
            user_id = input_json.get("user_id", "default")
            top_k = input_json.get("top_k", 10)
            include_remote = input_json.get("include_remote", True)
            enable_personalization = input_json.get("enable_personalization", True)
            clip_weight = input_json.get("clip_weight", 1.0)
            clap_weight = input_json.get("clap_weight", 0.8)
            local_weight = input_json.get("local_weight", 0.6)
            remote_weight = input_json.get("remote_weight", 0.4)
            
            match_result = matcher.match(
                query=query,
                user_id=user_id,
                top_k=top_k,
                include_remote=include_remote,
                enable_personalization=enable_personalization,
                clip_weight=clip_weight,
                clap_weight=clap_weight,
                local_weight=local_weight,
                remote_weight=remote_weight
            )
            
            result.update(match_result)
        
        elif action == "record_action":
            user_id = input_json.get("user_id", "")
            action_type = input_json.get("action_type", "")
            query = input_json.get("query", "")
            item_id = input_json.get("item_id", "")
            item_metadata = input_json.get("item_metadata", {})
            duration = input_json.get("duration", 0.0)
            position = input_json.get("position", 0)
            
            matcher.record_action(
                user_id=user_id,
                action_type=action_type,
                query=query,
                item_id=item_id,
                item_metadata=item_metadata,
                duration=duration,
                position=position
            )
            
            result["success"] = True
            result["message"] = "行为记录成功"
        
        elif action == "get_preferences":
            user_id = input_json.get("user_id", "")
            preferences = matcher.get_user_preferences(user_id)
            
            result["preferences"] = preferences
            result["success"] = True
        
        elif action == "get_suggestions":
            user_id = input_json.get("user_id", "")
            count = input_json.get("count", 5)
            suggestions = matcher.get_suggested_queries(user_id, count)
            
            result["suggestions"] = suggestions
            result["success"] = True
        
        elif action == "parse_query":
            query = input_json.get("query", "")
            parsed = matcher.parser.parse(query)
            
            result["parsed_query"] = {
                "semantic_query": parsed.semantic_query,
                "target_bpm": parsed.target_bpm,
                "bpm_range": parsed.bpm_range,
                "mood": parsed.mood,
                "genre": parsed.genre,
                "media_type": parsed.media_type,
                "quality": parsed.quality,
                "watermark_free": parsed.watermark_free,
                "preferred_platforms": parsed.preferred_platforms,
                "tags": parsed.tags,
                "confidence": parsed.confidence
            }
            result["success"] = True
        
        elif action == "extract_audio":
            audio_path = input_json.get("audio_path", "")
            features = matcher.extract_audio_features(audio_path)
            
            result["features"] = features
            result["success"] = True
        
        elif action == "engine_info":
            info = matcher.get_engine_info()
            
            result["engine_info"] = info
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
        import traceback
        print(json.dumps({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
