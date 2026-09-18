"""YouTube 下载器 - 基于 yt-dlp 的 Python API

支持视频下载、音频提取、字幕下载、搜索等功能。
支持代理配置，适合国内访问场景。

核心功能：
- download_video: 下载 YouTube 视频
- download_audio: 下载并提取音频为 MP3
- search_videos: 搜索 YouTube 视频
- get_video_info: 获取视频元数据
- download_subtitles: 下载字幕

调用方式：
    python youtube_downloader.py --json-input '{"func": "download_audio", "params": {"url": "https://www.youtube.com/watch?v=xxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}'

依赖：
    pip install yt-dlp
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from yt_dlp import YoutubeDL
except ImportError:
    YoutubeDL = None  # 延迟到调用时报错

# ==================== 常量配置 ====================

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

# 默认输出目录
DEFAULT_OUTPUT_DIR = _get_env_or_default("AEK_VIDEO_LIBRARY", "D:/AE-Work/视频素材库")
DEFAULT_BGM_DIR = _get_env_or_default("AEK_BGM_LIBRARY", "D:/AE-Work/音频素材库/BGM")
DEFAULT_SUBTITLE_DIR = _get_env_or_default("AEK_SUBTITLE_LIBRARY", "D:/AE-Work/字幕库")

# 默认 Cookie 路径（从环境变量读取）
DEFAULT_COOKIE_PATH = _get_env_or_default(
    "YOUTUBE_COOKIE_PATH",
    "D:/AE-Work/cookies/youtube_cookies.txt"
)
# 环境变量中的 Cookie 字符串（优先于文件）
ENV_COOKIE = os.environ.get("YOUTUBE_COOKIE", "")

# 输出文件名模板（包含视频 ID 防止重名）
OUTPUT_TEMPLATE = "%(title)s [%(id)s].%(ext)s"

# 默认画质
DEFAULT_QUALITY = "1080p"

# 字幕语言代码
SUBTITLE_LANG_MAP = {
    "zh-Hans": ["zh-Hans", "zh-Hans-en", "zh-CN", "zh"],
    "zh-Hant": ["zh-Hant", "zh-TW", "zh"],
    "zh": ["zh", "zh-Hans", "zh-Hant", "zh-CN", "zh-TW"],
    "en": ["en", "en-US"],
}

# YouTube 域名列表
YOUTUBE_DOMAINS = ["youtube.com", "youtu.be"]


# ==================== 异常定义 ====================


class YouTubeError(Exception):
    """YouTube 下载器基础异常"""


class VideoUnavailableError(YouTubeError):
    """视频不可用"""


# ==================== 工具函数 ====================


def _safe_filename(name: str, max_length: int = 100) -> str:
    """清理文件名，移除非法字符。

    Args:
        name: 原始文件名
        max_length: 最大长度限制

    Returns:
        安全的文件名
    """
    if not name:
        return "youtube_video"
    cleaned = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", name)
    cleaned = cleaned.strip(" .")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned or "youtube_video"


def _resolve_cookie_path(cookie_path: str | None = None) -> str | None:
    """解析 cookie 文件路径。

    优先级：
    1. 用户指定的路径
    2. 默认路径 D:/AE-Work/cookies/youtube_cookies.txt
    3. 项目内 cookies/youtube_cookies.txt
    """
    candidates: list[str] = []
    if cookie_path:
        candidates.append(cookie_path)
    candidates.append(DEFAULT_COOKIE_PATH)

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _build_base_options(
    output_dir: str,
    output_template: str = OUTPUT_TEMPLATE,
    cookie_path: str | None = None,
    quality: str = DEFAULT_QUALITY,
    audio_only: bool = False,
    proxy: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建 yt-dlp 选项字典。

    Args:
        output_dir: 输出目录
        output_template: 输出文件名模板
        cookie_path: cookie 文件路径
        quality: 画质
        audio_only: 是否仅下载音频
        proxy: 代理地址
        extra: 额外选项

    Returns:
        yt-dlp 选项字典
    """
    os.makedirs(output_dir, exist_ok=True)

    options: dict[str, Any] = {
        "outtmpl": os.path.join(output_dir, output_template),
        "ignoreerrors": True,
        "no_warnings": True,
        "encoding": "utf-8",
        "quiet": True,
        "no_color": True,
        "noprogress": True,
        "ffmpeg_location": "ffmpeg",
        # 指定下载文件路径输出
        "print": "after_move:filepath",
        # 不限制速度
        "ratelimit": None,
    }

    # Cookie 配置
    resolved_cookie = _resolve_cookie_path(cookie_path)
    if resolved_cookie:
        options["cookiefile"] = resolved_cookie

    # 代理配置
    if proxy:
        options["proxy"] = proxy

    # 画质与格式
    if audio_only:
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        # 视频画质（默认 1080p）
        quality_height = quality[:-1] if quality.endswith("p") else "1080"
        options["format"] = (
            f"bestvideo[height<={quality_height}]+bestaudio/best[height<={quality_height}]/best"
        )
        # 合并为 MP4
        options["merge_output_format"] = "mp4"
        options["postprocessors"] = [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ]

    if extra:
        options.update(extra)

    return options


def _parse_yt_dlp_info(info: dict[str, Any]) -> dict[str, Any]:
    """从 yt-dlp info 字典中提取统一格式的视频信息。"""
    return {
        "success": True,
        "video_id": info.get("id", ""),
        "title": info.get("title", ""),
        "author": info.get("uploader", "")
        or info.get("channel", "")
        or info.get("uploader_id", ""),
        "duration": float(info.get("duration", 0) or 0),
        "view_count": int(info.get("view_count", 0) or 0),
        "like_count": int(info.get("like_count", 0) or 0),
        "comment_count": int(info.get("comment_count", 0) or 0),
        "upload_date": info.get("upload_date", ""),
        "description": (info.get("description") or "")[:500],
        "webpage_url": info.get("webpage_url", info.get("original_url", "")),
        "thumbnail": info.get("thumbnail", ""),
        "platform": "youtube",
    }


# ==================== 核心下载器类 ====================


class YouTubeDownloader:
    """YouTube 下载器

    基于 yt-dlp 的 Python API，支持视频下载、音频提取、
    字幕下载、搜索等功能。可配置代理。
    """

    def __init__(
        self,
        cookie_path: str | None = None,
        proxy: str | None = None,
    ) -> None:
        """初始化下载器。

        Args:
            cookie_path: cookie 文件路径（可选，用于会员视频）
            proxy: 代理地址（如 http://127.0.0.1:7890）
        """
        if YoutubeDL is None:
            raise YouTubeError("缺少依赖 yt-dlp，请运行: pip install yt-dlp")

        self.cookie_path = cookie_path
        self.proxy = proxy

    # ---------- 核心功能 ----------

    def get_video_info(self, url: str) -> dict[str, Any]:
        """获取视频元数据。

        Args:
            url: YouTube 视频链接

        Returns:
            视频信息字典
        """
        result: dict[str, Any] = {
            "success": False,
            "video_id": "",
            "title": "",
            "author": "",
            "duration": 0.0,
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "upload_date": "",
            "description": "",
            "webpage_url": url,
            "thumbnail": "",
            "platform": "youtube",
            "error": None,
        }

        try:
            options = _build_base_options(
                output_dir=".",
                cookie_path=self.cookie_path,
                proxy=self.proxy,
                extra={
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                },
            )

            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                result["error"] = "yt-dlp 未返回视频信息"
                return result

            if info.get("_type") == "playlist":
                entries = info.get("entries", []) or []
                if not entries:
                    result["error"] = "播放列表为空"
                    return result
                info = entries[0]

            result.update(_parse_yt_dlp_info(info))
            return result

        except Exception as e:
            error_msg = str(e)
            if "Video unavailable" in error_msg or "Private video" in error_msg:
                raise VideoUnavailableError(f"视频不可用: {url}")
            result["error"] = f"获取视频信息失败: {error_msg}"
            return result

    def download_video(
        self,
        url: str,
        output_dir: str | None = None,
        quality: str = DEFAULT_QUALITY,
    ) -> dict[str, Any]:
        """下载 YouTube 视频。

        Args:
            url: YouTube 视频链接
            output_dir: 输出目录（默认 D:/AE-Work/视频素材库）
            quality: 画质（360p/480p/720p/1080p/1440p/2160p）

        Returns:
            下载结果字典
        """
        if output_dir is None:
            output_dir = DEFAULT_OUTPUT_DIR

        result: dict[str, Any] = {
            "success": False,
            "file_path": None,
            "title": "",
            "author": "",
            "duration": 0.0,
            "video_id": "",
            "platform": "youtube",
            "error": None,
        }

        # 先获取视频信息
        try:
            info_result = self.get_video_info(url)
            if info_result.get("success"):
                result["title"] = info_result.get("title", "")
                result["author"] = info_result.get("author", "")
                result["duration"] = info_result.get("duration", 0.0)
                result["video_id"] = info_result.get("video_id", "")
        except Exception:
            pass

        try:
            options = _build_base_options(
                output_dir=output_dir,
                cookie_path=self.cookie_path,
                quality=quality,
                audio_only=False,
                proxy=self.proxy,
            )

            downloaded_paths: list[str] = []

            def _filepath_hook(d: dict[str, Any]) -> None:
                if d.get("status") == "finished":
                    filepath = d.get("info_dict", {}).get("filepath")
                    if filepath and filepath not in downloaded_paths:
                        downloaded_paths.append(filepath)

            options["progress_hooks"] = [_filepath_hook]

            with YoutubeDL(options) as ydl:
                ydl.download([url])

            # 优先使用 progress_hook 收集的路径
            file_path = downloaded_paths[0] if downloaded_paths else None
            if not file_path:
                file_path = self._find_latest_file(output_dir, [".mp4"])

            if file_path and os.path.exists(file_path):
                result["success"] = True
                result["file_path"] = file_path
            else:
                result["error"] = "无法确定下载文件路径"
                result["success"] = False

            return result

        except Exception as e:
            error_msg = str(e)
            if "Video unavailable" in error_msg:
                raise VideoUnavailableError(f"视频不可用: {url}")
            result["error"] = f"下载视频失败: {error_msg}"
            return result

    def download_audio(
        self,
        url: str,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        """下载 YouTube 视频并提取音频为 MP3。

        Args:
            url: YouTube 视频链接
            output_dir: 输出目录（默认 D:/AE-Work/音频素材库/BGM）

        Returns:
            下载结果字典
        """
        if output_dir is None:
            output_dir = DEFAULT_BGM_DIR

        result: dict[str, Any] = {
            "success": False,
            "file_path": None,
            "title": "",
            "author": "",
            "duration": 0.0,
            "platform": "youtube",
            "error": None,
        }

        # 获取视频信息
        try:
            info_result = self.get_video_info(url)
            if info_result.get("success"):
                result["title"] = info_result.get("title", "")
                result["author"] = info_result.get("author", "")
                result["duration"] = info_result.get("duration", 0.0)
        except Exception:
            pass

        try:
            options = _build_base_options(
                output_dir=output_dir,
                cookie_path=self.cookie_path,
                audio_only=True,
                proxy=self.proxy,
                output_template=OUTPUT_TEMPLATE,
            )

            downloaded_paths: list[str] = []

            def _filepath_hook(d: dict[str, Any]) -> None:
                if d.get("status") == "finished":
                    filepath = d.get("info_dict", {}).get("filepath")
                    if filepath and filepath not in downloaded_paths:
                        downloaded_paths.append(filepath)

            options["progress_hooks"] = [_filepath_hook]

            with YoutubeDL(options) as ydl:
                ydl.download([url])

            file_path = self._find_latest_file(output_dir, [".mp3"])
            if not file_path and downloaded_paths:
                file_path = downloaded_paths[0]

            if file_path and os.path.exists(file_path):
                result["success"] = True
                result["file_path"] = file_path
            else:
                result["error"] = "无法找到生成的 MP3 文件"
                result["success"] = False

            return result

        except Exception as e:
            error_msg = str(e)
            if "Video unavailable" in error_msg:
                raise VideoUnavailableError(f"视频不可用: {url}")
            result["error"] = f"提取音频失败: {error_msg}"
            return result

    def search_videos(
        self, query: str, max_results: int = 10
    ) -> dict[str, Any]:
        """搜索 YouTube 视频。

        使用 yt-dlp 的 `ytsearch{N}:query` 语法。

        Args:
            query: 搜索关键词
            max_results: 最大结果数（默认 10）

        Returns:
            搜索结果字典：
            - success: 是否成功
            - query: 搜索关键词
            - count: 结果数量
            - videos: 视频信息列表
        """
        result: dict[str, Any] = {
            "success": False,
            "query": query,
            "count": 0,
            "videos": [],
            "platform": "youtube",
            "error": None,
        }

        try:
            search_query = f"ytsearch{max_results}:{query}"
            options = _build_base_options(
                output_dir=".",
                cookie_path=self.cookie_path,
                proxy=self.proxy,
                extra={
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": True,
                },
            )

            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(search_query, download=False)

            if not info or not info.get("entries"):
                result["success"] = True
                result["count"] = 0
                return result

            videos: list[dict[str, Any]] = []
            for entry in info["entries"]:
                if not entry:
                    continue
                videos.append(
                    {
                        "title": entry.get("title", ""),
                        "url": entry.get("url", "")
                        or entry.get("webpage_url", ""),
                        "video_id": entry.get("id", ""),
                        "duration": float(entry.get("duration", 0) or 0),
                        "view_count": int(entry.get("view_count", 0) or 0),
                        "uploader": entry.get("uploader", "")
                        or entry.get("channel", ""),
                        "thumbnail": entry.get("thumbnail", ""),
                    }
                )

            result["success"] = True
            result["count"] = len(videos)
            result["videos"] = videos
            return result

        except Exception as e:
            result["error"] = f"搜索失败: {e}"
            return result

    def download_subtitles(
        self,
        url: str,
        output_dir: str | None = None,
        lang: str = "zh-Hans",
    ) -> dict[str, Any]:
        """下载 YouTube 视频字幕。

        Args:
            url: YouTube 视频链接
            output_dir: 输出目录（默认 D:/AE-Work/字幕库）
            lang: 字幕语言代码（zh-Hans/zh-Hant/zh/en）

        Returns:
            下载结果字典：
            - success: 是否成功
            - subtitle_paths: 字幕文件路径列表
            - languages: 实际下载的语言
            - error: 错误信息（失败时）
        """
        if output_dir is None:
            output_dir = DEFAULT_SUBTITLE_DIR

        result: dict[str, Any] = {
            "success": False,
            "subtitle_paths": [],
            "languages": [],
            "platform": "youtube",
            "error": None,
        }

        # 获取对应语言代码列表
        lang_codes = SUBTITLE_LANG_MAP.get(lang, [lang])
        result["languages"] = lang_codes

        try:
            options = _build_base_options(
                output_dir=output_dir,
                cookie_path=self.cookie_path,
                proxy=self.proxy,
                extra={
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": lang_codes,
                    "subtitlesformat": "srt/vtt/best",
                    # 字幕输出模板（与视频文件分离）
                    "subtitlesouttmpl": os.path.join(
                        output_dir, "%(title)s [%(id)s].%(ext)s"
                    ),
                },
            )

            subtitle_paths: list[str] = []

            def _filepath_hook(d: dict[str, Any]) -> None:
                # 检测字幕文件
                if d.get("status") == "finished":
                    filepath = d.get("info_dict", {}).get("filepath")
                    if filepath and filepath not in subtitle_paths:
                        subtitle_paths.append(filepath)

            options["progress_hooks"] = [_filepath_hook]

            with YoutubeDL(options) as ydl:
                ydl.download([url])

            # 扫描输出目录查找字幕文件
            sub_extensions = [".srt", ".vtt", ".ass"]
            found_files = self._find_recent_files(
                output_dir, sub_extensions, max_age_seconds=300
            )

            if found_files or subtitle_paths:
                result["success"] = True
                result["subtitle_paths"] = found_files or subtitle_paths
            else:
                result["error"] = "未找到字幕文件（视频可能没有此语言的字幕）"

            return result

        except Exception as e:
            result["error"] = f"下载字幕失败: {e}"
            return result

    # ---------- 辅助方法 ----------

    @staticmethod
    def _find_latest_file(
        directory: str, extensions: list[str]
    ) -> str | None:
        """在目录中查找最新的指定扩展名文件。"""
        if not os.path.exists(directory):
            return None

        candidates: list[tuple] = []
        for name in os.listdir(directory):
            for ext in extensions:
                if name.lower().endswith(ext.lower()):
                    fpath = os.path.join(directory, name)
                    if os.path.isfile(fpath):
                        try:
                            mtime = os.path.getmtime(fpath)
                            size = os.path.getsize(fpath)
                            if size > 0:
                                candidates.append((mtime, fpath))
                        except OSError:
                            continue
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    @staticmethod
    def _find_recent_files(
        directory: str,
        extensions: list[str],
        max_age_seconds: int = 300,
    ) -> list[str]:
        """查找目录中最近修改的文件。

        Args:
            directory: 目录路径
            extensions: 扩展名列表
            max_age_seconds: 最大修改时间差（秒）

        Returns:
            文件路径列表
        """
        if not os.path.exists(directory):
            return []

        import time

        now = time.time()
        files: list[str] = []
        for name in os.listdir(directory):
            for ext in extensions:
                if name.lower().endswith(ext.lower()):
                    fpath = os.path.join(directory, name)
                    if os.path.isfile(fpath):
                        try:
                            mtime = os.path.getmtime(fpath)
                            if now - mtime <= max_age_seconds:
                                files.append(fpath)
                        except OSError:
                            continue
        return files


# ==================== 同步包装器（用于 --json-input 协议） ====================

_SENSITIVE_PATTERNS = ["cookie", "token", "api_key", "secret", "sessionid"]


def _sanitize_error(error_msg: str) -> str:
    """过滤错误信息中的敏感字段。"""
    import re
    sanitized = error_msg
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = re.sub(
            rf'({pattern}\s*[=:]\s*)[^\s,;"\}}]+',
            r'\1[REDACTED]',
            sanitized,
            flags=re.IGNORECASE,
        )
    return sanitized


def _handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """处理 --json-input 协议请求。"""
    func_name = request.get("func")
    params = request.get("params", {}) or {}

    if not func_name:
        return {"success": False, "error": "缺少 func 字段"}

    # 初始化下载器
    init_kwargs: dict[str, Any] = {}
    if "cookie_path" in params:
        init_kwargs["cookie_path"] = params.pop("cookie_path")
    if "proxy" in params:
        init_kwargs["proxy"] = params.pop("proxy")

    try:
        downloader = YouTubeDownloader(**init_kwargs)
    except YouTubeError as e:
        return {"success": False, "error": _sanitize_error(str(e))}

    func_map = {
        "download_video": downloader.download_video,
        "download_audio": downloader.download_audio,
        "search_videos": downloader.search_videos,
        "get_video_info": downloader.get_video_info,
        "download_subtitles": downloader.download_subtitles,
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
        return {"success": False, "error": _sanitize_error(f"参数错误: {e}")}
    except VideoUnavailableError as e:
        return {"success": False, "error": _sanitize_error(str(e))}
    except Exception as e:
        return {"success": False, "error": _sanitize_error(f"执行失败: {e}")}


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
    print("YouTube 下载器 - 基于 yt-dlp")
    print()
    print("使用方式：")
    print('  python youtube_downloader.py --json-input \'{"func": "download_audio", "params": {"url": "https://www.youtube.com/watch?v=xxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}\'')
    print()
    print("支持的函数：")
    print("  - download_video(url, output_dir?, quality?): 下载视频")
    print("  - download_audio(url, output_dir?): 下载并提取音频为 MP3")
    print("  - search_videos(query, max_results?): 搜索 YouTube 视频")
    print("  - get_video_info(url): 获取视频元数据")
    print("  - download_subtitles(url, output_dir?, lang?): 下载字幕")
    print()
    print("支持代理：在 params 中传入 proxy 参数")
    print('  示例：{"func": "download_video", "params": {"url": "...", "proxy": "http://127.0.0.1:7890"}}')


if __name__ == "__main__":
    main()
