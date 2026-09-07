"""统一下载入口 - 自动识别平台并路由

支持平台：抖音、B站、YouTube、快手、TikTok
- 抖音：使用 douyin_downloader_pro.py（httpx 直连 API）
- B站：使用 bilibili_downloader.py（基于 yt-dlp）
- YouTube：使用 youtube_downloader.py（基于 yt-dlp）
- 快手/TikTok：暂不支持，返回明确错误（平台已识别）

调用方式：
    python unified_downloader.py --json-input '{"func": "download_bgm", "params": {"url": "https://v.douyin.com/xxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}'
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# 将当前目录加入 sys.path 以便 import 同级模块
_CURRENT_DIR = str(Path(__file__).resolve().parent)
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

# ==================== 常量配置 ====================

# 平台识别规则
PLATFORM_RULES: Dict[str, list] = {
    "douyin": ["douyin.com", "iesdouyin.com", "v.douyin.com"],
    "bilibili": ["bilibili.com", "b23.tv", "acg.tv"],
    "youtube": ["youtube.com", "youtu.be"],
    "kuaishou": ["kuaishou.com", "chenzhongtech.com"],
    "tiktok": ["tiktok.com"],
}

# 默认输出目录（支持环境变量）
def _get_env_or_default(env_key: str, default: str) -> str:
    """从环境变量获取值，支持 .env 文件。"""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except Exception:
            pass
    return os.environ.get(env_key, default)

DEFAULT_OUTPUT_DIR = _get_env_or_default("AEK_VIDEO_LIBRARY", "D:/AE-Work/视频素材库")
DEFAULT_BGM_DIR = _get_env_or_default("AEK_BGM_LIBRARY", "D:/AE-Work/音频素材库/BGM")


# ==================== 异常定义 ====================


class UnifiedDownloaderError(Exception):
    """统一下载器基础异常"""


class UnsupportedPlatformError(UnifiedDownloaderError):
    """不支持的平台"""


class UnknownPlatformError(UnifiedDownloaderError):
    """无法识别的平台"""


# ==================== 平台识别 ====================


def detect_platform(url: str) -> Optional[str]:
    """自动识别 URL 对应的平台。

    识别规则：
    - 抖音：包含 douyin.com、iesdouyin.com、v.douyin.com
    - B站：包含 bilibili.com、b23.tv
    - YouTube：包含 youtube.com、youtu.be
    - 快手：包含 kuaishou.com
    - TikTok：包含 tiktok.com

    Args:
        url: 待识别的 URL

    Returns:
        平台名称（douyin/bilibili/youtube/kuaishou/tiktok），无法识别时返回 None
    """
    if not url:
        return None

    url_lower = url.lower()

    # 按优先级匹配（抖音短链可能包含 douyin，需要先匹配）
    for platform, patterns in PLATFORM_RULES.items():
        for pattern in patterns:
            if pattern in url_lower:
                return platform

    return None


# ==================== 模块加载器 ====================


class _ModuleLoader:
    """延迟加载下载器模块，避免单平台依赖缺失导致整体不可用。"""

    _instances: Dict[str, Any] = {}
    _errors: Dict[str, str] = {}

    @classmethod
    def get_douyin_downloader(
        cls,
        cookie: Optional[str] = None,
        cookie_path: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> Tuple[Any, Optional[str]]:
        """加载抖音下载器。

        Returns:
            (downloader_instance, error_or_None)
        """
        cache_key = f"douyin:{cookie or ''}:{cookie_path or ''}:{proxy or ''}"
        if cache_key in cls._instances:
            return cls._instances[cache_key], None
        if cache_key in cls._errors:
            return None, cls._errors[cache_key]

        try:
            module = importlib.import_module("douyin_downloader_pro")
            instance = module.DouyinDownloaderPro(
                cookie=cookie, cookie_path=cookie_path, proxy=proxy
            )
            cls._instances[cache_key] = instance
            return instance, None
        except Exception as e:
            error_msg = f"加载抖音下载器失败: {e}"
            cls._errors[cache_key] = error_msg
            return None, error_msg

    @classmethod
    def get_bilibili_downloader(
        cls,
        cookie_path: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> Tuple[Any, Optional[str]]:
        """加载 B站下载器。

        Returns:
            (downloader_instance, error_or_None)
        """
        cache_key = f"bilibili:{cookie_path or ''}:{proxy or ''}"
        if cache_key in cls._instances:
            return cls._instances[cache_key], None
        if cache_key in cls._errors:
            return None, cls._errors[cache_key]

        try:
            module = importlib.import_module("bilibili_downloader")
            instance = module.BilibiliDownloader(
                cookie_path=cookie_path, proxy=proxy
            )
            cls._instances[cache_key] = instance
            return instance, None
        except Exception as e:
            error_msg = f"加载 B站下载器失败: {e}"
            cls._errors[cache_key] = error_msg
            return None, error_msg

    @classmethod
    def get_youtube_downloader(
        cls,
        cookie_path: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> Tuple[Any, Optional[str]]:
        """加载 YouTube 下载器。

        Returns:
            (downloader_instance, error_or_None)
        """
        cache_key = f"youtube:{cookie_path or ''}:{proxy or ''}"
        if cache_key in cls._instances:
            return cls._instances[cache_key], None
        if cache_key in cls._errors:
            return None, cls._errors[cache_key]

        try:
            module = importlib.import_module("youtube_downloader")
            instance = module.YouTubeDownloader(
                cookie_path=cookie_path, proxy=proxy
            )
            cls._instances[cache_key] = instance
            return instance, None
        except Exception as e:
            error_msg = f"加载 YouTube 下载器失败: {e}"
            cls._errors[cache_key] = error_msg
            return None, error_msg

    @classmethod
    def reset(cls) -> None:
        """重置所有缓存的实例和错误。"""
        cls._instances.clear()
        cls._errors.clear()


# ==================== 异步辅助 ====================


def _run_async(coro):
    """同步运行异步协程。

    用于调用抖音下载器的异步方法。
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ==================== 统一下载器类 ====================


class UnifiedDownloader:
    """统一下载入口

    自动识别平台（抖音/B站/YouTube/快手/TikTok），
    路由到对应的下载器实例。
    """

    def __init__(
        self,
        cookie: Optional[str] = None,
        cookie_path: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> None:
        """初始化统一下载器。

        Args:
            cookie: cookie 字符串（主要用于抖音）
            cookie_path: cookie 文件路径
            proxy: 代理地址（主要用于 YouTube）
        """
        self.cookie = cookie
        self.cookie_path = cookie_path
        self.proxy = proxy

    # ---------- 公共接口 ----------

    def detect_platform(self, url: str) -> Dict[str, Any]:
        """检测 URL 对应的平台。

        Args:
            url: 待识别的 URL

        Returns:
            检测结果字典：
            - platform: 平台名称（无法识别时为 None）
            - url: 原始 URL
            - supported: 是否受支持
            - message: 描述信息
        """
        platform = detect_platform(url)
        supported_platforms = {"douyin", "bilibili", "youtube"}
        return {
            "success": True,
            "platform": platform,
            "url": url,
            "supported": platform in supported_platforms,
            "message": (
                f"识别为 {platform} 平台"
                if platform
                else "无法识别平台"
            ),
        }

    def download(
        self,
        url: str,
        output_dir: Optional[str] = None,
        audio_only: bool = False,
        quality: str = "1080p",
    ) -> Dict[str, Any]:
        """统一下载入口，自动路由到对应下载器。

        Args:
            url: 视频 URL
            output_dir: 输出目录
            audio_only: 是否仅下载音频
            quality: 画质（用于视频下载）

        Returns:
            下载结果字典，统一格式：
            - success: 是否成功
            - file_path: 下载文件路径
            - title: 标题
            - author: 作者
            - duration: 时长
            - platform: 平台
            - error: 错误信息（失败时）
        """
        if output_dir is None:
            output_dir = (
                DEFAULT_BGM_DIR if audio_only else DEFAULT_OUTPUT_DIR
            )

        platform = detect_platform(url)
        if platform is None:
            return {
                "success": False,
                "error": f"无法识别 URL 平台: {url}",
                "platform": None,
                "url": url,
            }

        if platform == "douyin":
            return self._download_douyin(
                url, output_dir, audio_only=audio_only
            )
        elif platform == "bilibili":
            return self._download_bilibili(
                url, output_dir, audio_only=audio_only, quality=quality
            )
        elif platform == "youtube":
            return self._download_youtube(
                url, output_dir, audio_only=audio_only, quality=quality
            )
        elif platform in ("kuaishou", "tiktok"):
            return {
                "success": False,
                "error": (
                    f"暂不支持 {platform} 平台下载。"
                    f"已识别为 {platform}，但该平台尚未实现专用下载器。"
                ),
                "platform": platform,
                "url": url,
            }
        else:
            return {
                "success": False,
                "error": f"不支持的平台: {platform}",
                "platform": platform,
                "url": url,
            }

    def download_bgm(
        self,
        url: str,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """下载视频并提取音频为 MP3（自动识别平台）。

        Args:
            url: 视频 URL
            output_dir: 输出目录（默认 D:/AE-Work/音频素材库/BGM）

        Returns:
            下载结果字典
        """
        if output_dir is None:
            output_dir = DEFAULT_BGM_DIR
        return self.download(url, output_dir=output_dir, audio_only=True)

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频元数据（自动识别平台）。

        Args:
            url: 视频 URL

        Returns:
            视频信息字典
        """
        platform = detect_platform(url)
        if platform is None:
            return {
                "success": False,
                "error": f"无法识别 URL 平台: {url}",
                "platform": None,
            }

        if platform == "douyin":
            return self._get_info_douyin(url)
        elif platform == "bilibili":
            return self._get_info_bilibili(url)
        elif platform == "youtube":
            return self._get_info_youtube(url)
        elif platform in ("kuaishou", "tiktok"):
            return {
                "success": False,
                "error": f"暂不支持 {platform} 平台",
                "platform": platform,
            }
        else:
            return {
                "success": False,
                "error": f"不支持的平台: {platform}",
                "platform": platform,
            }

    # ---------- 平台路由实现 ----------

    def _download_douyin(
        self,
        url: str,
        output_dir: str,
        audio_only: bool = False,
    ) -> Dict[str, Any]:
        """抖音下载路由。"""
        downloader, error = _ModuleLoader.get_douyin_downloader(
            cookie=self.cookie, cookie_path=self.cookie_path, proxy=self.proxy
        )
        if error:
            return {
                "success": False,
                "error": error,
                "platform": "douyin",
                "url": url,
            }

        try:
            if audio_only:
                coro = downloader.download_bgm(
                    url, output_dir=output_dir, cookie=self.cookie
                )
                result = _run_async(coro)
            else:
                coro = downloader.download_video(
                    url,
                    output_dir=output_dir,
                    cookie=self.cookie,
                    watermark_free=True,
                )
                result = _run_async(coro)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"抖音下载失败: {e}",
                "platform": "douyin",
                "url": url,
            }

    def _download_bilibili(
        self,
        url: str,
        output_dir: str,
        audio_only: bool = False,
        quality: str = "1080p",
    ) -> Dict[str, Any]:
        """B站下载路由。"""
        downloader, error = _ModuleLoader.get_bilibili_downloader(
            cookie_path=self.cookie_path, proxy=self.proxy
        )
        if error:
            return {
                "success": False,
                "error": error,
                "platform": "bilibili",
                "url": url,
            }

        try:
            if audio_only:
                return downloader.download_audio(url, output_dir=output_dir)
            else:
                return downloader.download_video(
                    url, output_dir=output_dir, quality=quality
                )
        except Exception as e:
            return {
                "success": False,
                "error": f"B站下载失败: {e}",
                "platform": "bilibili",
                "url": url,
            }

    def _download_youtube(
        self,
        url: str,
        output_dir: str,
        audio_only: bool = False,
        quality: str = "1080p",
    ) -> Dict[str, Any]:
        """YouTube 下载路由。"""
        downloader, error = _ModuleLoader.get_youtube_downloader(
            cookie_path=self.cookie_path, proxy=self.proxy
        )
        if error:
            return {
                "success": False,
                "error": error,
                "platform": "youtube",
                "url": url,
            }

        try:
            if audio_only:
                return downloader.download_audio(url, output_dir=output_dir)
            else:
                return downloader.download_video(
                    url, output_dir=output_dir, quality=quality
                )
        except Exception as e:
            return {
                "success": False,
                "error": f"YouTube 下载失败: {e}",
                "platform": "youtube",
                "url": url,
            }

    def _get_info_douyin(self, url: str) -> Dict[str, Any]:
        """抖音信息查询路由。"""
        downloader, error = _ModuleLoader.get_douyin_downloader(
            cookie=self.cookie, cookie_path=self.cookie_path, proxy=self.proxy
        )
        if error:
            return {
                "success": False,
                "error": error,
                "platform": "douyin",
            }

        try:
            coro = downloader.get_video_info(url, cookie=self.cookie)
            return _run_async(coro)
        except Exception as e:
            return {
                "success": False,
                "error": f"获取抖音视频信息失败: {e}",
                "platform": "douyin",
            }

    def _get_info_bilibili(self, url: str) -> Dict[str, Any]:
        """B站信息查询路由。"""
        downloader, error = _ModuleLoader.get_bilibili_downloader(
            cookie_path=self.cookie_path, proxy=self.proxy
        )
        if error:
            return {
                "success": False,
                "error": error,
                "platform": "bilibili",
            }

        try:
            return downloader.get_video_info(url)
        except Exception as e:
            return {
                "success": False,
                "error": f"获取 B站视频信息失败: {e}",
                "platform": "bilibili",
            }

    def _get_info_youtube(self, url: str) -> Dict[str, Any]:
        """YouTube 信息查询路由。"""
        downloader, error = _ModuleLoader.get_youtube_downloader(
            cookie_path=self.cookie_path, proxy=self.proxy
        )
        if error:
            return {
                "success": False,
                "error": error,
                "platform": "youtube",
            }

        try:
            return downloader.get_video_info(url)
        except Exception as e:
            return {
                "success": False,
                "error": f"获取 YouTube 视频信息失败: {e}",
                "platform": "youtube",
            }


# ==================== 同步包装器（用于 --json-input 协议） ====================


def _handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """处理 --json-input 协议请求。"""
    func_name = request.get("func")
    params = request.get("params", {}) or {}

    if not func_name:
        return {"success": False, "error": "缺少 func 字段"}

    # 初始化下载器
    init_kwargs: Dict[str, Any] = {}
    if "cookie" in params:
        init_kwargs["cookie"] = params.pop("cookie")
    if "cookie_path" in params:
        init_kwargs["cookie_path"] = params.pop("cookie_path")
    if "proxy" in params:
        init_kwargs["proxy"] = params.pop("proxy")

    try:
        downloader = UnifiedDownloader(**init_kwargs)
    except Exception as e:
        return {"success": False, "error": f"初始化下载器失败: {e}"}

    func_map = {
        "download": downloader.download,
        "download_bgm": downloader.download_bgm,
        "get_video_info": downloader.get_video_info,
        "detect_platform": downloader.detect_platform,
    }

    try:
        if func_name in func_map:
            return func_map[func_name](**params)
        else:
            return {
                "success": False,
                "error": (
                    f"未知函数: {func_name}，"
                    f"支持的函数: {list(func_map.keys())}"
                ),
            }
    except TypeError as e:
        return {"success": False, "error": f"参数错误: {e}"}
    except Exception as e:
        return {"success": False, "error": f"执行失败: {e}"}


# ==================== 主入口 ====================


def main() -> None:
    """主入口函数，支持 --json-input 参数。"""
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()

            if not input_data.strip():
                print(
                    json.dumps(
                        {"success": False, "error": "输入为空"},
                        ensure_ascii=False,
                    )
                )
                return

            request = json.loads(input_data)
            response = _handle_request(request)
            print(json.dumps(response, ensure_ascii=False, indent=2))
        except json.JSONDecodeError as e:
            print(
                json.dumps(
                    {"success": False, "error": f"JSON 解析失败: {e}"},
                    ensure_ascii=False,
                )
            )
        except Exception as e:
            print(
                json.dumps(
                    {"success": False, "error": f"内部错误: {e}"},
                    ensure_ascii=False,
                )
            )
        return

    # 交互模式
    print("统一下载入口 - 自动识别平台并路由")
    print()
    print("支持平台：")
    print("  - 抖音 (douyin.com, v.douyin.com, iesdouyin.com)")
    print("  - B站 (bilibili.com, b23.tv)")
    print("  - YouTube (youtube.com, youtu.be)")
    print("  - 快手 (kuaishou.com) [识别但暂不支持下载]")
    print("  - TikTok (tiktok.com) [识别但暂不支持下载]")
    print()
    print("使用方式：")
    print('  python unified_downloader.py --json-input \'{"func": "download_bgm", "params": {"url": "https://v.douyin.com/xxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}\'')
    print()
    print("支持的函数：")
    print("  - download(url, output_dir?, audio_only?, quality?): 自动路由下载")
    print("  - download_bgm(url, output_dir?): 自动识别平台并提取音频")
    print("  - get_video_info(url): 获取视频元数据")
    print("  - detect_platform(url): 检测平台")
    print()
    print("示例：")
    print(json.dumps(
        {
            "func": "download_bgm",
            "params": {
                "url": "https://v.douyin.com/xxx",
                "output_dir": "D:/AE-Work/音频素材库/BGM"
            }
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
