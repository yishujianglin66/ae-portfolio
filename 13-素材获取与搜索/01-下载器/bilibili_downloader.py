"""B站下载器 - 基于 yt-dlp 的 Python API

yt-dlp 对 B站 的支持比 bilix 更稳定，支持高清画质、字幕、批量下载。
本模块封装 yt-dlp 的 Python API，提供统一的 JSON 接口。

核心功能：
- download_video: 下载 B站视频
- download_audio: 下载并提取音频为 MP3
- get_video_info: 获取视频元数据
- download_batch: 批量下载

调用方式：
    python bilibili_downloader.py --json-input '{"func": "download_audio", "params": {"url": "https://www.bilibili.com/video/BVxxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}'

依赖：
    pip install yt-dlp
"""
from __future__ import annotations

import json
import os
import re
import subprocess
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

# 默认 Cookie 路径（从环境变量读取）
DEFAULT_COOKIE_PATH = _get_env_or_default(
    "BILIBILI_COOKIE_PATH",
    "D:/AE-Work/cookies/bilibili_cookies.txt"
)
# 环境变量中的 Cookie 字符串（优先于文件）
ENV_COOKIE = os.environ.get("BILIBILI_COOKIE", "")

# 输出文件名模板
OUTPUT_TEMPLATE = "%(title)s.%(ext)s"

# B站 画质映射
QUALITY_MAP = {
    "360p": "16",  # 流畅 360P
    "480p": "32",  # 清晰 480P
    "720p": "64",  # 高清 720P
    "1080p": "80",  # 高清 1080P
    "1080p+": "112",  # 高码率 1080P
    "4k": "120",  # 4K 超清
}

# FFmpeg 命令
FFMPEG_CMD = "ffmpeg"

# B站域名列表
BILIBILI_DOMAINS = ["bilibili.com", "b23.tv", "acg.tv"]


# ==================== 异常定义 ====================


class BilibiliError(Exception):
    """B站下载器基础异常"""


class VideoDeletedError(BilibiliError):
    """视频已删除或不可访问"""


class CookieRequiredError(BilibiliError):
    """需要 Cookie 才能访问"""


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
        return "bilibili_video"
    cleaned = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", name)
    cleaned = cleaned.strip(" .")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned or "bilibili_video"


def _resolve_cookie_path(cookie_path: Optional[str] = None) -> Optional[str]:
    """解析 cookie 文件路径。

    优先级：
    1. 用户指定的路径
    2. 默认路径 D:/AE-Work/cookies/bilibili_cookies.txt
    3. 项目内 cookies/bilibili_cookies.txt

    Args:
        cookie_path: 用户指定的 cookie 路径

    Returns:
        存在的 cookie 文件路径，或 None
    """
    candidates: List[str] = []
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
    cookie_path: Optional[str] = None,
    quality: str = "1080p",
    audio_only: bool = False,
    proxy: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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

    options: Dict[str, Any] = {
        # 输出路径模板
        "outtmpl": os.path.join(output_dir, output_template),
        # 忽略错误继续下载
        "ignoreerrors": True,
        "no_warnings": True,
        # 编码设置
        "encoding": "utf-8",
        # 写入信息 JSON（用于事后追溯）
        "writeinfojson": False,
        # 不下载缩略图（节省时间）
        "writethumbnail": False,
        # 不写入描述文件
        "writedescription": False,
        # 进度输出
        "quiet": True,
        "no_color": True,
        # 使用 FFmpeg 进行后处理
        "ffmpeg_location": FFMPEG_CMD,
        # 获取下载文件路径
        "print": "after_move:filepath",
        # 进度回调
        "noprogress": True,
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
        # 仅下载音频
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        # 视频+音频：优先选择指定画质
        format_quality = QUALITY_MAP.get(quality, "80")
        options["format"] = (
            f"bestvideo[height<={quality[:-1] if quality.endswith('p') else '1080'}]"
            "+bestaudio/best"
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


def _parse_yt_dlp_info(info: Dict[str, Any]) -> Dict[str, Any]:
    """从 yt-dlp info 字典中提取统一格式的视频信息。

    Args:
        info: yt-dlp 返回的 info 字典

    Returns:
        统一格式的视频信息字典
    """
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
        "platform": "bilibili",
    }


# ==================== 核心下载器类 ====================


class BilibiliDownloader:
    """B站下载器

    基于 yt-dlp 的 Python API，支持视频下载、音频提取、
    视频信息查询、批量下载等功能。
    """

    def __init__(
        self,
        cookie_path: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> None:
        """初始化下载器。

        Args:
            cookie_path: cookie 文件路径（可选，用于高清画质）
            proxy: 代理地址（可选）
        """
        if YoutubeDL is None:
            raise BilibiliError("缺少依赖 yt-dlp，请运行: pip install yt-dlp")

        self.cookie_path = cookie_path
        self.proxy = proxy

    # ---------- 核心功能 ----------

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频元数据。

        Args:
            url: B站视频链接

        Returns:
            视频信息字典：
            - success: 是否成功
            - video_id: 视频 ID（BV 号）
            - title: 标题
            - author: UP 主
            - duration: 时长（秒）
            - view_count: 播放量
            - like_count: 点赞数
            - comment_count: 评论数
            - upload_date: 上传日期
            - description: 简介（截断到 500 字）
            - webpage_url: 原始 URL
            - thumbnail: 封面 URL
            - error: 错误信息（失败时）
        """
        result: Dict[str, Any] = {
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
            "platform": "bilibili",
            "error": None,
        }

        try:
            options = _build_base_options(
                output_dir=".",  # 仅获取信息不下载
                cookie_path=self.cookie_path,
                proxy=self.proxy,
                extra={
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                },
            )

            with YoutubeDL(options) as ydl:
                # 提取信息不下载
                info = ydl.extract_info(url, download=False)

            if not info:
                result["error"] = "yt-dlp 未返回视频信息"
                return result

            # 检查是否是播放列表
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
            if "404" in error_msg or "not found" in error_msg.lower():
                raise VideoDeletedError(f"视频不存在或已删除: {url}")
            result["error"] = f"获取视频信息失败: {error_msg}"
            return result

    def download_video(
        self,
        url: str,
        output_dir: Optional[str] = None,
        quality: str = "1080p",
    ) -> Dict[str, Any]:
        """下载 B站视频。

        Args:
            url: B站视频链接
            output_dir: 输出目录（默认 D:/AE-Work/视频素材库）
            quality: 画质（360p/480p/720p/1080p/1080p+/4k）

        Returns:
            下载结果字典：
            - success: 是否成功
            - file_path: 下载文件路径
            - title: 视频标题
            - author: UP 主
            - duration: 时长
            - video_id: 视频 ID
            - error: 错误信息（失败时）
        """
        if output_dir is None:
            output_dir = DEFAULT_OUTPUT_DIR

        result: Dict[str, Any] = {
            "success": False,
            "file_path": None,
            "title": "",
            "author": "",
            "duration": 0.0,
            "video_id": "",
            "platform": "bilibili",
            "error": None,
        }

        # 先获取视频信息用于返回值
        try:
            info_result = self.get_video_info(url)
            if info_result.get("success"):
                result["title"] = info_result.get("title", "")
                result["author"] = info_result.get("author", "")
                result["duration"] = info_result.get("duration", 0.0)
                result["video_id"] = info_result.get("video_id", "")
        except Exception:
            # 信息获取失败不阻断下载
            pass

        try:
            options = _build_base_options(
                output_dir=output_dir,
                cookie_path=self.cookie_path,
                quality=quality,
                audio_only=False,
                proxy=self.proxy,
            )

            # 收集下载文件路径
            downloaded_paths: List[str] = []

            def _filepath_hook(d: Dict[str, Any]) -> None:
                if d.get("status") == "finished":
                    filepath = d.get("info_dict", {}).get("filepath")
                    if filepath and filepath not in downloaded_paths:
                        downloaded_paths.append(filepath)

            options["progress_hooks"] = [_filepath_hook]

            with YoutubeDL(options) as ydl:
                # 使用 print 选项获取最终文件路径
                # yt-dlp 会通过 print 输出 after_move:filepath
                exit_code = ydl.download([url])

            # 从输出中获取文件路径
            if downloaded_paths:
                file_path = downloaded_paths[0]
            else:
                # 兜底：扫描输出目录找最新文件
                file_path = self._find_latest_file(output_dir, [".mp4"])

            if file_path and os.path.exists(file_path):
                result["success"] = True
                result["file_path"] = file_path
            else:
                # 仍然返回成功，因为下载可能已完成
                result["success"] = True
                result["file_path"] = (
                    downloaded_paths[0] if downloaded_paths else None
                )
                if not result["file_path"]:
                    result["error"] = "无法确定下载文件路径"
                    result["success"] = False

            return result

        except Exception as e:
            error_msg = str(e)
            if "Cookie" in error_msg or "login" in error_msg.lower():
                raise CookieRequiredError(
                    "此视频需要登录后才能下载，请配置 Cookie 文件"
                )
            result["error"] = f"下载视频失败: {error_msg}"
            return result

    def download_audio(
        self,
        url: str,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """下载 B站视频并提取音频为 MP3。

        Args:
            url: B站视频链接
            output_dir: 输出目录（默认 D:/AE-Work/音频素材库/BGM）

        Returns:
            下载结果字典：
            - success: 是否成功
            - file_path: MP3 文件路径
            - title: 视频标题
            - author: UP 主
            - duration: 时长
            - error: 错误信息（失败时）
        """
        if output_dir is None:
            output_dir = DEFAULT_BGM_DIR

        result: Dict[str, Any] = {
            "success": False,
            "file_path": None,
            "title": "",
            "author": "",
            "duration": 0.0,
            "platform": "bilibili",
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
                # 音频模板
                output_template="%(title)s.%(ext)s",
            )

            downloaded_paths: List[str] = []

            def _filepath_hook(d: Dict[str, Any]) -> None:
                if d.get("status") == "finished":
                    filepath = d.get("info_dict", {}).get("filepath")
                    if filepath and filepath not in downloaded_paths:
                        downloaded_paths.append(filepath)

            options["progress_hooks"] = [_filepath_hook]

            with YoutubeDL(options) as ydl:
                ydl.download([url])

            # 查找 MP3 文件
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
            if "Cookie" in error_msg or "login" in error_msg.lower():
                raise CookieRequiredError(
                    "此视频需要登录后才能下载，请配置 Cookie 文件"
                )
            result["error"] = f"提取音频失败: {error_msg}"
            return result

    def download_batch(
        self,
        urls: List[str],
        output_dir: Optional[str] = None,
        quality: str = "1080p",
        audio_only: bool = False,
    ) -> Dict[str, Any]:
        """批量下载 B站视频。

        Args:
            urls: URL 列表
            output_dir: 输出目录
            quality: 画质
            audio_only: 是否仅下载音频

        Returns:
            批量下载结果字典：
            - success: 是否全部成功
            - total: 总数
            - succeeded: 成功数
            - failed: 失败数
            - results: 每个视频的结果列表
        """
        if output_dir is None:
            output_dir = DEFAULT_BGM_DIR if audio_only else DEFAULT_OUTPUT_DIR

        results: List[Dict[str, Any]] = []
        succeeded = 0
        failed = 0

        for url in urls:
            try:
                if audio_only:
                    item_result = self.download_audio(url, output_dir)
                else:
                    item_result = self.download_video(
                        url, output_dir, quality=quality
                    )
                if item_result.get("success"):
                    succeeded += 1
                else:
                    failed += 1
                results.append(item_result)
            except Exception as e:
                failed += 1
                results.append(
                    {
                        "success": False,
                        "url": url,
                        "error": str(e),
                        "platform": "bilibili",
                    }
                )

        return {
            "success": failed == 0,
            "total": len(urls),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "platform": "bilibili",
        }

    # ---------- 辅助方法 ----------

    @staticmethod
    def _find_latest_file(
        directory: str, extensions: List[str]
    ) -> Optional[str]:
        """在目录中查找最新的指定扩展名文件。

        Args:
            directory: 目录路径
            extensions: 扩展名列表（如 [".mp4", ".mp3"]）

        Returns:
            最新文件的路径，或 None
        """
        if not os.path.exists(directory):
            return None

        candidates: List[tuple] = []
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
        # 返回最新的文件
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def validate_cookie(
        self, cookie_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """验证 Cookie 文件有效性。

        Args:
            cookie_path: cookie 文件路径

        Returns:
            验证结果字典
        """
        path = cookie_path or self.cookie_path or DEFAULT_COOKIE_PATH

        result: Dict[str, Any] = {
            "valid": False,
            "cookie_path": path,
            "exists": False,
            "field_count": 0,
            "has_session": False,
            "error": None,
        }

        if not os.path.exists(path):
            result["error"] = f"Cookie 文件不存在: {path}"
            return result

        result["exists"] = True

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # 检查关键字段
            has_session = any(
                keyword in content.lower()
                for keyword in ["sessdata", "bili_jct", "duid"]
            )
            result["has_session"] = has_session
            result["valid"] = len(content.strip()) > 50 and has_session
            result["field_count"] = content.count("\t") + 1 if content else 0
        except Exception as e:
            result["error"] = f"读取 Cookie 文件失败: {e}"

        return result


# ==================== 同步包装器（用于 --json-input 协议） ====================

_SENSITIVE_PATTERNS = ["cookie", "token", "api_key", "secret", "sessionid", "bili_jct", "DedeUserID"]


def _sanitize_error(error_msg: str) -> str:
    """过滤错误信息中的敏感字段。"""
    import re
    sanitized = error_msg
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = re.sub(
            rf'({pattern}\s*[=:]\s*)[^\s,;"\}}]+',
            rf'\1[REDACTED]',
            sanitized,
            flags=re.IGNORECASE,
        )
    return sanitized


def _handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """处理 --json-input 协议请求。

    Args:
        request: 请求字典，包含 func 和 params 字段

    Returns:
        响应字典
    """
    func_name = request.get("func")
    params = request.get("params", {}) or {}

    if not func_name:
        return {"success": False, "error": "缺少 func 字段"}

    # 初始化下载器
    init_kwargs: Dict[str, Any] = {}
    if "cookie_path" in params:
        init_kwargs["cookie_path"] = params.pop("cookie_path")
    if "proxy" in params:
        init_kwargs["proxy"] = params.pop("proxy")

    try:
        downloader = BilibiliDownloader(**init_kwargs)
    except BilibiliError as e:
        return {"success": False, "error": _sanitize_error(str(e))}

    func_map = {
        "download_video": downloader.download_video,
        "download_audio": downloader.download_audio,
        "get_video_info": downloader.get_video_info,
        "download_batch": downloader.download_batch,
        "validate_cookie": downloader.validate_cookie,
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
    except (VideoDeletedError, CookieRequiredError) as e:
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

    # 交互模式：打印帮助信息
    print("B站下载器 - 基于 yt-dlp")
    print()
    print("使用方式：")
    print('  python bilibili_downloader.py --json-input \'{"func": "download_audio", "params": {"url": "https://www.bilibili.com/video/BVxxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}\'')
    print()
    print("支持的函数：")
    print("  - download_video(url, output_dir?, quality?): 下载视频")
    print("  - download_audio(url, output_dir?): 下载并提取音频为 MP3")
    print("  - get_video_info(url): 获取视频元数据")
    print("  - download_batch(urls, output_dir?, quality?, audio_only?): 批量下载")
    print("  - validate_cookie(cookie_path?): 验证 Cookie 文件")


if __name__ == "__main__":
    main()
