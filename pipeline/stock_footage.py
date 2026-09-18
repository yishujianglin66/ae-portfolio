"""
stock_footage.py - 无水印素材获取客户端
========================================

支持 Pexels + Pixabay 双源搜索和下载免费无水印视频素材。
集成到 UnifiedPipeline 的 perceive 阶段，替代带水印的 B 站测试素材。

API 文档:
- Pexels: https://www.pexels.com/api/documentation/#videos-search
- Pixabay: https://pixabay.com/api/docs/#api_search_videos

Usage:
    from pipeline.stock_footage import StockFootageClient
    
    client = StockFootageClient()
    videos = client.search_and_download("cinematic nature", count=5)
    # videos: List[str] - 下载后的本地文件路径列表
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认素材缓存目录
DEFAULT_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "stock_footage"
)


@dataclass
class VideoResult:
    """单个视频搜索结果"""
    id: str
    url: str              # 视频页面 URL
    download_url: str     # 直接下载链接 (无水印)
    width: int = 0
    height: int = 0
    duration: float = 0.0  # 秒
    size_bytes: int = 0
    source: str = ""       # "pexels" | "pixabay"
    thumbnail: str = ""
    tags: str = ""


@dataclass
class SearchConfig:
    """搜索配置"""
    query: str = ""
    count: int = 5               # 需要下载的视频数
    min_width: int = 1280        # 最小宽度
    min_height: int = 720        # 最小高度
    min_duration: float = 5.0    # 最短时长(秒)
    max_duration: float = 60.0   # 最长时长(秒)
    orientation: str = "landscape"  # landscape | portrait | all
    per_page: int = 15           # 每页请求数
    timeout: int = 30            # HTTP 超时(秒)
    download_timeout: int = 120  # 下载超时(秒)


class StockFootageClient:
    """无水印素材获取客户端 - Pexels + Pixabay 双源"""

    def __init__(
        self,
        pexels_api_key: str = "",
        pixabay_api_key: str = "",
        cache_dir: str = "",
        config_manager: Any = None,
    ):
        # 优先级 1: 显式参数
        self._pexels_key = pexels_api_key
        self._pixabay_key = pixabay_api_key
        cache_dir_param = cache_dir

        # 优先级 2: 环境变量 (无前缀兼容 + AEKV_ 前缀通用)
        if not self._pexels_key:
            self._pexels_key = os.environ.get("AEKV_STOCK_PEXELS_API_KEY", "") or os.environ.get("PEXELS_API_KEY", "")
        if not self._pixabay_key:
            self._pixabay_key = os.environ.get("AEKV_STOCK_PIXABAY_API_KEY", "") or os.environ.get("PIXABAY_API_KEY", "")
        # cache_dir 优先级 (高 -> 低): 参数 > 环境变量 > ConfigManager > 默认
        env_cache = os.environ.get("AEKV_STOCK_CACHE_DIR", "")

        # 优先级 3: ConfigManager (只有 env/参数 为空才从 CM 读)
        if config_manager is None:
            try:
                from core.config import ConfigManager
                config_manager = ConfigManager(auto_load=True)
            except Exception as e:
                logger.debug(f"[StockFootage] ConfigManager not available: {e}")
                config_manager = None

        if config_manager is not None:
            if not self._pexels_key:
                self._pexels_key = config_manager.get_str("stock.pexels.api_key", "")
            if not self._pixabay_key:
                self._pixabay_key = config_manager.get_str("stock.pixabay.api_key", "")
            if not cache_dir_param and not env_cache:
                cache_dir_param = config_manager.get_str("stock.cache_dir", "")

        # 环境变量 cache_dir 比 ConfigManager 优先级高
        if not cache_dir_param and env_cache:
            cache_dir_param = env_cache

        # 优先级 4: .env 文件加载 (最后兜底)
        if not self._pexels_key or not self._pixabay_key:
            self._load_env()

        # 默认缓存目录
        base_cache = cache_dir_param or DEFAULT_CACHE_DIR
        self._cache_dir = Path(base_cache)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[StockFootage] Pexels: {'OK' if self._pexels_key else 'MISSING'}, "
                    f"Pixabay: {'OK' if self._pixabay_key else 'MISSING'}, "
                    f"Cache: {self._cache_dir}")

    def _load_env(self) -> None:
        """从项目 .env 文件加载配置"""
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if not env_path.exists():
            return
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key == "PEXELS_API_KEY" and not self._pexels_key:
                        self._pexels_key = value
                    elif key == "PIXABAY_API_KEY" and not self._pixabay_key:
                        self._pixabay_key = value
        except Exception as e:
            logger.warning(f"[StockFootage] .env load error: {e}")

    # =========================================================================
    #  公共 API
    # =========================================================================

    def search_and_download(
        self,
        query: str,
        count: int = 5,
        min_width: int = 1280,
        min_height: int = 720,
        min_duration: float = 5.0,
    ) -> list[str]:
        """搜索并下载无水印视频素材。

        Args:
            query: 搜索关键词 (英文效果最佳)
            count: 需要下载的视频数量
            min_width: 最小宽度
            min_height: 最小高度
            min_duration: 最短时长(秒)

        Returns:
            下载后的本地文件路径列表
        """
        config = SearchConfig(
            query=query,
            count=count,
            min_width=min_width,
            min_height=min_height,
            min_duration=min_duration,
        )

        # 双源搜索，优先 Pexels，补充 Pixabay
        results: list[VideoResult] = []

        if self._pexels_key:
            pexels_results = self._search_pexels(config)
            results.extend(pexels_results)
            logger.info(f"[StockFootage] Pexels: {len(pexels_results)} results")

        if len(results) < count and self._pixabay_key:
            pixabay_results = self._search_pixabay(config)
            results.extend(pixabay_results)
            logger.info(f"[StockFootage] Pixabay: {len(pixabay_results)} results")

        if not results:
            logger.warning(f"[StockFootage] No results for '{query}'")
            return []

        # 去重 + 按分辨率排序
        seen_ids = set()
        unique_results = []
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                unique_results.append(r)
        unique_results.sort(key=lambda r: r.width * r.height, reverse=True)

        # 下载 top-N
        downloaded = []
        for r in unique_results[:count]:
            local_path = self._download_video(r)
            if local_path:
                downloaded.append(local_path)

        logger.info(f"[StockFootage] Downloaded {len(downloaded)}/{count} videos for '{query}'")
        return downloaded

    def search_only(self, query: str, count: int = 10) -> list[VideoResult]:
        """仅搜索不下载，返回结果列表"""
        config = SearchConfig(query=query, count=count, per_page=count)
        results = []
        if self._pexels_key:
            results.extend(self._search_pexels(config))
        if self._pixabay_key:
            results.extend(self._search_pixabay(config))
        return results[:count]

    def test_connectivity(self) -> dict[str, Any]:
        """测试 API 连通性"""
        report = {"pexels": False, "pixabay": False, "errors": []}

        if self._pexels_key:
            try:
                results = self._search_pexels(SearchConfig(query="nature", per_page=1, count=1))
                report["pexels"] = len(results) > 0
            except Exception as e:
                report["errors"].append(f"Pexels: {e}")
        
        if self._pixabay_key:
            try:
                results = self._search_pixabay(SearchConfig(query="nature", per_page=3, count=1))
                report["pixabay"] = len(results) > 0
            except Exception as e:
                report["errors"].append(f"Pixabay: {e}")

        return report

    # =========================================================================
    #  Pexels API
    # =========================================================================

    def _search_pexels(self, config: SearchConfig) -> list[VideoResult]:
        """Pexels Video Search API
        
        GET https://api.pexels.com/videos/search
        Headers: Authorization: <api_key>
        """
        url = "https://api.pexels.com/videos/search"
        params = {
            "query": config.query,
            "per_page": min(config.per_page, 80),
            "orientation": config.orientation if config.orientation != "all" else "",
        }
        # 移除空值
        params = {k: v for k, v in params.items() if v}

        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"

        req = urllib.request.Request(full_url)
        req.add_header("Authorization", self._pexels_key)
        req.add_header("User-Agent", "AE-Knowledge-Vault/1.0")

        try:
            with urllib.request.urlopen(req, timeout=config.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            logger.error(f"[Pexels] HTTP {e.code}: {e.reason}")
            return []
        except Exception as e:
            logger.error(f"[Pexels] Request failed: {e}")
            return []

        results = []
        for video in data.get("videos", []):
            # 选择最佳质量文件
            video_files = video.get("video_files", [])
            best_file = self._select_best_file_pexels(
                video_files, config.min_width, config.min_height
            )
            if not best_file:
                continue

            duration = float(video.get("duration", 0))
            if duration < config.min_duration:
                continue

            width = best_file.get("width", 0)
            height = best_file.get("height", 0)

            results.append(VideoResult(
                id=f"pexels_{video.get('id', '')}",
                url=video.get("url", ""),
                download_url=best_file.get("link", ""),
                width=width,
                height=height,
                duration=duration,
                size_bytes=best_file.get("size", 0),
                source="pexels",
                thumbnail=video.get("image", ""),
            ))

        return results

    def _select_best_file_pexels(
        self, video_files: list[dict], min_w: int, min_h: int
    ) -> dict | None:
        """从 Pexels video_files 中选择最佳质量"""
        candidates = []
        for f in video_files:
            w = f.get("width", 0)
            h = f.get("height", 0)
            if w >= min_w and h >= min_h:
                candidates.append(f)

        if not candidates:
            # 降级：取最大的
            candidates = video_files

        if not candidates:
            return None

        # 优先 1080p，其次最大分辨率
        candidates.sort(key=lambda f: (
            abs(f.get("width", 0) - 1920) + abs(f.get("height", 0) - 1080)
        ))
        return candidates[0]

    # =========================================================================
    #  Pixabay API
    # =========================================================================

    def _search_pixabay(self, config: SearchConfig) -> list[VideoResult]:
        """Pixabay Video Search API
        
        GET https://pixabay.com/api/videos/
        Params: key, q, min_width, min_height, per_page
        """
        params = {
            "key": self._pixabay_key,
            "q": config.query,
            "per_page": min(config.per_page, 200),
            "min_width": config.min_width,
            "min_height": config.min_height,
            "safesearch": "true",
        }

        query_string = urllib.parse.urlencode(params)
        full_url = f"https://pixabay.com/api/videos/?{query_string}"

        req = urllib.request.Request(full_url)
        req.add_header("User-Agent", "AE-Knowledge-Vault/1.0")

        try:
            with urllib.request.urlopen(req, timeout=config.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            logger.error(f"[Pixabay] HTTP {e.code}: {e.reason}")
            return []
        except Exception as e:
            logger.error(f"[Pixabay] Request failed: {e}")
            return []

        results = []
        for hit in data.get("hits", []):
            # Pixabay 提供多种质量: large/medium/small/tiny
            videos_dict = hit.get("videos", {})
            best = self._select_best_pixabay(videos_dict, config.min_width)
            if not best:
                continue

            duration = float(hit.get("duration", 0))
            if duration < config.min_duration:
                continue

            results.append(VideoResult(
                id=f"pixabay_{hit.get('id', '')}",
                url=hit.get("pageURL", ""),
                download_url=best.get("url", ""),
                width=best.get("width", 0),
                height=best.get("height", 0),
                duration=duration,
                size_bytes=best.get("size", 0),
                source="pixabay",
                thumbnail=f"https://i.vimeocdn.com/video/{hit.get('picture_id', '')}_295x166.jpg",
                tags=hit.get("tags", ""),
            ))

        return results

    def _select_best_pixabay(
        self, videos_dict: dict, min_width: int
    ) -> dict | None:
        """从 Pixabay videos 对象中选择最佳质量
        
        Pixabay 格式: {"large": {...}, "medium": {...}, "small": {...}, "tiny": {...}}
        """
        # 优先级: large > medium > small > tiny
        for quality in ["large", "medium", "small", "tiny"]:
            v = videos_dict.get(quality)
            if v and v.get("width", 0) >= min_width:
                return v

        # 降级：取 large 即使小于 min_width
        return videos_dict.get("large") or videos_dict.get("medium")

    # =========================================================================
    #  下载
    # =========================================================================

    def _download_video(self, result: VideoResult) -> str | None:
        """下载单个视频到本地缓存"""
        if not result.download_url:
            return None

        # 生成本地文件名 (result.id 已包含 source 前缀，例如 "pexels_123456")
        ext = ".mp4"
        filename = f"{result.id}{ext}"
        local_path = self._cache_dir / filename

        # 已存在则跳过
        if local_path.exists() and local_path.stat().st_size > 10240:
            logger.info(f"[StockFootage] Cached: {filename}")
            return str(local_path)

        logger.info(f"[StockFootage] Downloading: {result.source} {result.width}x{result.height} "
                    f"{result.duration:.0f}s -> {filename}")

        try:
            req = urllib.request.Request(result.download_url)
            req.add_header("User-Agent", "AE-Knowledge-Vault/1.0")

            with urllib.request.urlopen(req, timeout=120) as resp:
                # 流式下载
                tmp_path = local_path.with_suffix(".tmp")
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        f.write(chunk)

                # 原子重命名
                tmp_path.rename(local_path)

            size_mb = local_path.stat().st_size / (1024 * 1024)
            logger.info(f"[StockFootage] Downloaded: {filename} ({size_mb:.1f}MB)")
            return str(local_path)

        except Exception as e:
            logger.error(f"[StockFootage] Download failed: {e}")
            # 清理临时文件
            tmp_path = local_path.with_suffix(".tmp")
            if tmp_path.exists():
                tmp_path.unlink()
            return None

    # =========================================================================
    #  关键词翻译 (中文→英文搜索词)
    # =========================================================================

    @staticmethod
    def translate_query(topic: str) -> str:
        """将中文主题转换为英文搜索关键词"""
        # 简单映射表（高频场景）
        CN_TO_EN = {
            "高燃混剪": "epic action cinematic",
            "自然风景": "nature landscape aerial",
            "城市夜景": "city night timelapse",
            "动漫": "anime animation",
            "科技": "technology futuristic",
            "运动": "sports extreme",
            "美食": "food cooking",
            "旅行": "travel adventure",
            "海洋": "ocean underwater",
            "太空": "space galaxy stars",
            "森林": "forest nature green",
            "日落": "sunset golden hour",
            "雨天": "rain moody dark",
            "赛博朋克": "cyberpunk neon city",
            "古风": "chinese traditional culture",
        }

        # 精确匹配
        if topic in CN_TO_EN:
            return CN_TO_EN[topic]

        # 模糊匹配
        for cn, en in CN_TO_EN.items():
            if cn in topic:
                return en

        # 如果已经是英文，直接返回
        if topic.isascii():
            return topic

        # 默认：用拼音或通用词
        return f"cinematic {topic}"


# 全局单例
_client: StockFootageClient | None = None


def get_stock_client() -> StockFootageClient:
    """获取全局素材客户端单例"""
    global _client
    if _client is None:
        _client = StockFootageClient()
    return _client
