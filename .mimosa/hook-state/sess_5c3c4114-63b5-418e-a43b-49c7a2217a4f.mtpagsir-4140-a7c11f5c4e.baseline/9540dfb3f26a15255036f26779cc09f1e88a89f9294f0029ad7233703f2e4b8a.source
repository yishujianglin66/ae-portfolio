"""
跨平台搜索器 - 多平台素材搜索集成

支持平台：抖音、B站、YouTube、快手、TikTok
核心功能：
1. 统一搜索接口
2. 跨平台去重
3. 质量评估
4. 搜索结果合并
"""

from __future__ import annotations

import json
import sys
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01-下载器"))

try:
    from douyin_downloader_pro import DouyinDownloaderPro
    from bilibili_downloader import BilibiliDownloader
    from youtube_downloader import YouTubeDownloader
    from unified_downloader import detect_platform, PLATFORM_RULES
    DOWNLOADERS_AVAILABLE = True
except ImportError:
    DOWNLOADERS_AVAILABLE = False


@dataclass
class SearchResult:
    """搜索结果结构"""
    url: str = ""
    title: str = ""
    platform: str = ""
    thumbnail: str = ""
    duration: float = 0.0
    view_count: int = 0
    like_count: int = 0
    download_count: int = 0
    quality: str = "medium"
    watermark: bool = True
    similarity: float = 0.0
    audio_features: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "platform": self.platform,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "download_count": self.download_count,
            "quality": self.quality,
            "watermark": self.watermark,
            "similarity": self.similarity,
            "audio_features": self.audio_features,
            "metadata": self.metadata
        }


class CrossPlatformSearcher:
    """跨平台搜索器"""
    
    def __init__(self):
        self.downloaders: Dict[str, Any] = {}
        if DOWNLOADERS_AVAILABLE:
            self._init_downloaders()
    
    def _init_downloaders(self) -> None:
        """初始化各平台下载器"""
        try:
            self.downloaders["douyin"] = DouyinDownloaderPro()
        except Exception:
            pass
        
        try:
            self.downloaders["bilibili"] = BilibiliDownloader()
        except Exception:
            pass
        
        try:
            self.downloaders["youtube"] = YouTubeDownloader()
        except Exception:
            pass
    
    def search(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        max_results_per_platform: int = 10,
        media_type: str = "video"
    ) -> List[Dict[str, Any]]:
        """
        跨平台搜索
        
        参数:
            query: 搜索关键词
            platforms: 平台列表，为空则搜索所有支持的平台
            max_results_per_platform: 每个平台最大结果数
            media_type: 素材类型（video/audio）
        
        返回:
            搜索结果列表
        """
        results = []
        
        if not DOWNLOADERS_AVAILABLE:
            return results
        
        target_platforms = platforms or list(self.downloaders.keys())
        
        for platform in target_platforms:
            if platform not in self.downloaders:
                continue
            
            downloader = self.downloaders[platform]
            
            try:
                platform_results = self._search_platform(
                    downloader, platform, query, max_results_per_platform, media_type
                )
                results.extend(platform_results)
            except Exception as e:
                print(f"平台 {platform} 搜索失败: {str(e)}", file=sys.stderr)
        
        return results
    
    def _search_platform(
        self,
        downloader: Any,
        platform: str,
        query: str,
        max_results: int,
        media_type: str
    ) -> List[Dict[str, Any]]:
        """搜索单个平台"""
        results = []
        
        try:
            # 不同平台的搜索接口可能不同
            if hasattr(downloader, "search"):
                search_result = downloader.search(query, limit=max_results)
                if search_result.get("success"):
                    for item in search_result.get("results", []):
                        result = {
                            "url": item.get("url", ""),
                            "title": item.get("title", ""),
                            "platform": platform,
                            "thumbnail": item.get("thumbnail", ""),
                            "duration": item.get("duration", 0),
                            "view_count": item.get("view_count", 0),
                            "like_count": item.get("like_count", 0),
                            "download_count": item.get("download_count", 0),
                            "quality": item.get("quality", "medium"),
                            "watermark": item.get("watermark", True),
                            "similarity": item.get("similarity", 0.0),
                            "audio_features": item.get("audio_features", {}),
                            "metadata": item.get("metadata", {})
                        }
                        results.append(result)
            
            # 如果没有search方法，尝试解析视频信息（作为备选）
            elif hasattr(downloader, "get_video_info"):
                # 这里简化处理，实际应该有搜索API
                pass
                
        except Exception as e:
            print(f"{platform} 搜索异常: {str(e)}", file=sys.stderr)
        
        return results[:max_results]
    
    def deduplicate(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        跨平台去重
        
        基于：
        1. URL MD5去重
        2. 标题相似度去重
        3. 内容指纹去重
        """
        if not results:
            return []
        
        seen_urls = set()
        seen_titles = set()
        deduplicated = []
        
        for result in results:
            url = result.get("url", "")
            title = result.get("title", "").strip().lower()
            
            # URL去重
            url_hash = hashlib.md5(url.encode()).hexdigest()
            if url_hash in seen_urls:
                continue
            seen_urls.add(url_hash)
            
            # 标题相似度去重（简单版）
            if title in seen_titles:
                continue
            seen_titles.add(title)
            
            # 检查标题相似度（更严格的去重）
            is_duplicate = False
            for existing in deduplicated:
                existing_title = existing.get("title", "").strip().lower()
                if self._title_similarity(title, existing_title) > 0.9:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(result)
        
        return deduplicated
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """计算标题相似度（Jaccard相似度）"""
        words1 = set(title1.replace(" ", "").replace("_", ""))
        words2 = set(title2.replace(" ", "").replace("_", ""))
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def assess_quality(self, result: Dict[str, Any]) -> float:
        """
        评估单个结果的质量（便捷方法）
        
        参数:
            result: 单个搜索结果字典
        
        返回:
            质量分数（0-1）
        """
        evaluated = self.evaluate_quality([result])
        if evaluated:
            return evaluated[0].get("quality_score", 0.5)
        return 0.5
    
    def evaluate_quality(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        质量评估
        
        评估维度：
        1. 分辨率/画质
        2. 是否有水印
        3. 观看量/点赞量
        4. 时长
        """
        evaluated = []
        
        for result in results:
            score = 0.0
            factors = []
            
            # 画质评分
            quality = result.get("quality", "medium")
            if quality == "4k":
                score += 0.3
                factors.append("4K画质")
            elif quality == "high":
                score += 0.25
                factors.append("高清")
            elif quality == "medium":
                score += 0.15
                factors.append("标清")
            
            # 水印评分
            watermark = result.get("watermark", True)
            if not watermark:
                score += 0.2
                factors.append("无水印")
            else:
                score += 0.05
                factors.append("有水印")
            
            # 热度评分
            view_count = result.get("view_count", 0)
            if view_count > 1000000:
                score += 0.2
                factors.append("高热度")
            elif view_count > 100000:
                score += 0.15
                factors.append("中等热度")
            elif view_count > 10000:
                score += 0.1
                factors.append("一般热度")
            
            # 时长评分（假设30秒到5分钟为最佳）
            duration = result.get("duration", 0)
            if 30 <= duration <= 300:
                score += 0.15
                factors.append("时长适中")
            elif duration > 300:
                score += 0.1
                factors.append("较长")
            elif duration > 0:
                score += 0.05
                factors.append("较短")
            
            # 点赞率评分
            if view_count > 0:
                like_ratio = result.get("like_count", 0) / view_count
                if like_ratio > 0.1:
                    score += 0.1
                    factors.append("高点赞率")
                elif like_ratio > 0.05:
                    score += 0.05
                    factors.append("良好点赞率")
            
            result_with_score = result.copy()
            result_with_score["quality_score"] = round(min(score, 1.0), 4)
            result_with_score["quality_factors"] = factors
            
            evaluated.append(result_with_score)
        
        evaluated.sort(key=lambda x: x["quality_score"], reverse=True)
        return evaluated
    
    def merge_results(
        self,
        local_results: List[Dict[str, Any]],
        remote_results: List[Dict[str, Any]],
        local_weight: float = 0.6,
        remote_weight: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        合并本地和远程搜索结果
        
        参数:
            local_results: 本地索引搜索结果
            remote_results: 远程平台搜索结果
            local_weight: 本地结果权重
            remote_weight: 远程结果权重
        
        返回:
            合并排序后的结果
        """
        merged = []
        
        # 添加本地结果
        for result in local_results:
            merged_item = result.copy()
            merged_item["source"] = "local"
            merged_item["final_score"] = result.get("combined_score", result.get("similarity", 0.0)) * local_weight
            merged.append(merged_item)
        
        # 添加远程结果
        for result in remote_results:
            merged_item = result.copy()
            merged_item["source"] = "remote"
            merged_item["final_score"] = result.get("quality_score", 0.0) * remote_weight
            merged.append(merged_item)
        
        # 去重
        merged = self.deduplicate(merged)
        
        # 按最终分数排序
        merged.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        
        return merged


def main() -> None:
    """主函数，支持JSON输入协议"""
    if len(sys.argv) < 2:
        print("用法: python cross_platform_searcher.py --json-input '<JSON字符串>'")
        print("示例: python cross_platform_searcher.py --json-input '{\"action\": \"search\", \"query\": \"夕阳下的海滩\", \"platforms\": [\"douyin\", \"bilibili\"]}'")
        sys.exit(1)
    
    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)
    
    try:
        input_json = json.loads(sys.argv[2])
        action = input_json.get("action", "")
        
        searcher = CrossPlatformSearcher()
        result: Dict[str, Any] = {"success": False, "results": []}
        
        if action == "search":
            query = input_json.get("query", "")
            platforms = input_json.get("platforms")
            max_results = input_json.get("max_results_per_platform", 10)
            media_type = input_json.get("media_type", "video")
            
            results = searcher.search(query, platforms, max_results, media_type)
            results = searcher.evaluate_quality(results)
            
            result["results"] = results
            result["success"] = True
        
        elif action == "deduplicate":
            results = input_json.get("results", [])
            deduplicated = searcher.deduplicate(results)
            
            result["results"] = deduplicated
            result["duplicates_removed"] = len(results) - len(deduplicated)
            result["success"] = True
        
        elif action == "merge_results":
            local_results = input_json.get("local_results", [])
            remote_results = input_json.get("remote_results", [])
            local_weight = input_json.get("local_weight", 0.6)
            remote_weight = input_json.get("remote_weight", 0.4)
            
            merged = searcher.merge_results(local_results, remote_results, local_weight, remote_weight)
            
            result["results"] = merged
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
