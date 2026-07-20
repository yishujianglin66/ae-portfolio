"""
用户偏好学习模块 - 个性化推荐

核心功能：
1. 用户行为记录
2. 偏好模型学习
3. 个性化推荐生成
4. 冷启动处理
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class UserAction:
    """用户行为记录"""
    user_id: str = ""       # 用户ID
    action_type: str = ""   # search, click, download, like, skip
    query: str = ""         # 搜索查询
    item_id: str = ""       # 素材ID/URL
    item_metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""     # ISO时间戳
    duration: float = 0.0   # 停留时长（秒）
    position: int = 0       # 结果位置


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str = ""
    preferences: Dict[str, float] = field(default_factory=dict)
    mood_history: Dict[str, int] = field(default_factory=dict)
    genre_history: Dict[str, int] = field(default_factory=dict)
    platform_history: Dict[str, int] = field(default_factory=dict)
    quality_history: Dict[str, int] = field(default_factory=dict)
    bpm_history: Dict[str, int] = field(default_factory=dict)
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class UserPreferenceLearner:
    """用户偏好学习器"""
    
    # 行为权重
    ACTION_WEIGHTS = {
        "search": 1.0,
        "click": 2.0,
        "download": 5.0,
        "like": 3.0,
        "skip": -1.0,
        "preview": 1.5,
    }
    
    # 时间衰减因子（每天衰减10%）
    TIME_DECAY = 0.9
    
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or str(Path(__file__).resolve().parent / "user_data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.user_profiles: Dict[str, UserProfile] = {}
    
    def _load_profile(self, user_id: str) -> UserProfile:
        """加载用户画像"""
        if user_id in self.user_profiles:
            return self.user_profiles[user_id]
        
        profile_path = os.path.join(self.data_dir, f"user_{user_id}.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return UserProfile(**data)
            except Exception:
                pass
        
        return UserProfile(user_id=user_id, created_at=datetime.now().isoformat())
    
    def _save_profile(self, profile: UserProfile) -> None:
        """保存用户画像"""
        profile.updated_at = datetime.now().isoformat()
        profile_path = os.path.join(self.data_dir, f"user_{profile.user_id}.json")
        
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.__dict__, f, ensure_ascii=False, indent=2)
        
        self.user_profiles[profile.user_id] = profile
    
    def record_behavior(
        self,
        user_id: str,
        action_type: str,
        item_id: str = "",
        query: str = "",
        item_metadata: Optional[Dict[str, Any]] = None,
        duration: float = 0.0,
        position: int = 0
    ) -> None:
        """
        记录用户行为（便捷方法）
        
        参数:
            user_id: 用户ID
            action_type: 行为类型（search, click, download, like, skip, preview）
            item_id: 素材ID/URL
            query: 搜索查询
            item_metadata: 素材元数据
            duration: 停留时长（秒）
            position: 结果位置
        """
        action = UserAction(
            user_id=user_id,
            action_type=action_type,
            query=query,
            item_id=item_id,
            item_metadata=item_metadata or {},
            duration=duration,
            position=position
        )
        self.record_action(action)
    
    def record_action(self, action: UserAction) -> None:
        """
        记录用户行为
        
        参数:
            action: 用户行为对象
        """
        profile = self._load_profile(action.user_id)
        
        # 设置时间戳
        if not action.timestamp:
            action.timestamp = datetime.now().isoformat()
        
        # 记录到最近行为
        profile.recent_actions.append(action.__dict__)
        if len(profile.recent_actions) > 100:
            profile.recent_actions = profile.recent_actions[-100:]
        
        # 更新偏好历史
        weight = self.ACTION_WEIGHTS.get(action.action_type, 1.0)
        
        # 情绪偏好
        mood = action.item_metadata.get("audio_features", {}).get("mood", "")
        if mood:
            profile.mood_history[mood] = profile.mood_history.get(mood, 0) + int(weight)
        
        # 曲风偏好
        genre = action.item_metadata.get("audio_features", {}).get("genre", "")
        if genre:
            profile.genre_history[genre] = profile.genre_history.get(genre, 0) + int(weight)
        
        # 平台偏好
        platform = action.item_metadata.get("platform", "")
        if platform:
            profile.platform_history[platform] = profile.platform_history.get(platform, 0) + int(weight)
        
        # 质量偏好
        quality = action.item_metadata.get("quality", "")
        if quality:
            profile.quality_history[quality] = profile.quality_history.get(quality, 0) + int(weight)
        
        # BPM偏好
        bpm = action.item_metadata.get("audio_features", {}).get("bpm", "")
        if bpm:
            try:
                bpm_value = float(bpm)
                bpm_key = f"{int(bpm_value // 10) * 10}-{int(bpm_value // 10) * 10 + 10}"
                profile.bpm_history[bpm_key] = profile.bpm_history.get(bpm_key, 0) + int(weight)
            except (ValueError, TypeError):
                pass
        
        # 学习偏好
        self._learn_preferences(profile)
        
        # 保存
        self._save_profile(profile)
    
    def _learn_preferences(self, profile: UserProfile) -> None:
        """从历史行为学习偏好"""
        preferences = {}
        
        # 学习情绪偏好
        if profile.mood_history:
            total = sum(profile.mood_history.values())
            for mood, count in profile.mood_history.items():
                preferences[f"mood_{mood}"] = count / total
        
        # 学习曲风偏好
        if profile.genre_history:
            total = sum(profile.genre_history.values())
            for genre, count in profile.genre_history.items():
                preferences[f"genre_{genre}"] = count / total
        
        # 学习平台偏好
        if profile.platform_history:
            total = sum(profile.platform_history.values())
            for platform, count in profile.platform_history.items():
                preferences[f"platform_{platform}"] = count / total
        
        # 学习质量偏好
        if profile.quality_history:
            total = sum(profile.quality_history.values())
            for quality, count in profile.quality_history.items():
                preferences[f"quality_{quality}"] = count / total
        
        profile.preferences = preferences
    
    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户偏好
        
        参数:
            user_id: 用户ID
        
        返回:
            用户偏好字典
        """
        profile = self._load_profile(user_id)
        
        # 计算最频繁的偏好
        top_mood = max(profile.mood_history.items(), key=lambda x: x[1], default=(None, 0))[0]
        top_genre = max(profile.genre_history.items(), key=lambda x: x[1], default=(None, 0))[0]
        top_platform = max(profile.platform_history.items(), key=lambda x: x[1], default=(None, 0))[0]
        top_quality = max(profile.quality_history.items(), key=lambda x: x[1], default=(None, 0))[0]
        top_bpm_range = max(profile.bpm_history.items(), key=lambda x: x[1], default=(None, 0))[0]
        
        return {
            "user_id": user_id,
            "preferences": profile.preferences,
            "top_mood": top_mood,
            "top_genre": top_genre,
            "top_platform": top_platform,
            "top_quality": top_quality,
            "top_bpm_range": top_bpm_range,
            "action_count": len(profile.recent_actions),
            "is_cold_start": len(profile.recent_actions) < 5,
        }
    
    def personalize_results(
        self,
        user_id: str,
        results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        个性化推荐
        
        参数:
            user_id: 用户ID
            results: 待个性化的结果列表
            top_k: 返回结果数
        
        返回:
            个性化排序后的结果
        """
        preferences = self.get_preferences(user_id)
        
        # 冷启动处理：返回原始结果
        if preferences["is_cold_start"]:
            return results[:top_k]
        
        scored_results = []
        
        for result in results:
            score = 1.0
            reasons = []
            
            # 情绪偏好匹配
            if preferences["top_mood"]:
                item_mood = result.get("audio_features", {}).get("mood", "")
                if item_mood and preferences["top_mood"].lower() in item_mood.lower():
                    score *= 1.2
                    reasons.append(f"情绪偏好匹配:{item_mood}")
            
            # 曲风偏好匹配
            if preferences["top_genre"]:
                item_genre = result.get("audio_features", {}).get("genre", "")
                if item_genre and preferences["top_genre"].lower() in item_genre.lower():
                    score *= 1.15
                    reasons.append(f"曲风偏好匹配:{item_genre}")
            
            # 平台偏好匹配
            if preferences["top_platform"]:
                item_platform = result.get("platform", "")
                if item_platform and preferences["top_platform"].lower() == item_platform.lower():
                    score *= 1.1
                    reasons.append(f"平台偏好匹配:{item_platform}")
            
            # 质量偏好匹配
            if preferences["top_quality"]:
                item_quality = result.get("quality", "")
                if item_quality and preferences["top_quality"].lower() == item_quality.lower():
                    score *= 1.05
                    reasons.append(f"质量偏好匹配:{item_quality}")
            
            # BPM偏好匹配
            if preferences["top_bpm_range"]:
                item_bpm = result.get("audio_features", {}).get("bpm", "")
                if item_bpm:
                    try:
                        bpm_value = float(item_bpm)
                        bpm_key = f"{int(bpm_value // 10) * 10}-{int(bpm_value // 10) * 10 + 10}"
                        if bpm_key == preferences["top_bpm_range"]:
                            score *= 1.1
                            reasons.append(f"BPM偏好匹配:{bpm_key}")
                    except (ValueError, TypeError):
                        pass
            
            result_with_score = result.copy()
            result_with_score["personalization_score"] = round(score, 4)
            result_with_score["personalization_reasons"] = reasons
            
            scored_results.append(result_with_score)
        
        # 按个性化分数排序
        scored_results.sort(key=lambda x: x.get("personalization_score", 1.0), reverse=True)
        
        return scored_results[:top_k]
    
    def get_suggested_queries(self, user_id: str, count: int = 5) -> List[str]:
        """
        获取建议搜索词
        
        参数:
            user_id: 用户ID
            count: 返回数量
        
        返回:
            建议搜索词列表
        """
        preferences = self.get_preferences(user_id)
        
        suggestions = []
        
        # 基于情绪和曲风生成建议
        if preferences["top_mood"] and preferences["top_genre"]:
            suggestions.append(f"{preferences['top_mood']}的{preferences['top_genre']}音乐")
        
        if preferences["top_mood"]:
            suggestions.append(f"{preferences['top_mood']}的背景音乐")
        
        if preferences["top_genre"]:
            suggestions.append(f"{preferences['top_genre']}风格BGM")
        
        # 基于平台生成建议
        if preferences["top_platform"]:
            suggestions.append(f"{preferences['top_platform']}热门素材")
        
        # 默认建议（冷启动）
        if not suggestions:
            suggestions = [
                "欢快的背景音乐",
                "励志的流行音乐",
                "浪漫的钢琴曲",
                "抖音热门BGM",
                "高清无水印视频素材",
            ]
        
        return suggestions[:count]


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python user_preference.py --json-input '<JSON字符串>'")
        print("示例: python user_preference.py --json-input '{\"action\": \"record_action\", \"user_id\": \"test_user\", \"action_type\": \"download\", \"item_id\": \"xxx\"}'")
        sys.exit(1)
    
    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)
    
    try:
        input_json = json.loads(sys.argv[2])
        action = input_json.get("action", "")
        
        learner = UserPreferenceLearner()
        result: Dict[str, Any] = {"success": False}
        
        if action == "record_action":
            user_action = UserAction(
                action_type=input_json.get("action_type", ""),
                query=input_json.get("query", ""),
                item_id=input_json.get("item_id", ""),
                item_metadata=input_json.get("item_metadata", {}),
                timestamp=input_json.get("timestamp", ""),
                duration=input_json.get("duration", 0.0),
                position=input_json.get("position", 0),
                user_id=input_json.get("user_id", "")
            )
            
            learner.record_action(user_action)
            result["success"] = True
            result["message"] = "行为记录成功"
        
        elif action == "get_preferences":
            user_id = input_json.get("user_id", "")
            preferences = learner.get_preferences(user_id)
            
            result["preferences"] = preferences
            result["success"] = True
        
        elif action == "personalize_results":
            user_id = input_json.get("user_id", "")
            results = input_json.get("results", [])
            top_k = input_json.get("top_k", 10)
            
            personalized = learner.personalize_results(user_id, results, top_k)
            
            result["results"] = personalized
            result["success"] = True
        
        elif action == "get_suggested_queries":
            user_id = input_json.get("user_id", "")
            count = input_json.get("count", 5)
            
            suggestions = learner.get_suggested_queries(user_id, count)
            
            result["suggestions"] = suggestions
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
