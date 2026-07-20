"""抖音专业下载器 - 使用 httpx 直接调用抖音 Web API

参考 TikTokDownloader 思路，独立实现避免 GPL 传染。
不依赖 yt-dlp，使用 httpx 异步 HTTP 客户端直接调用抖音 API。

核心特性：
- 短链接解析（重定向跟踪获取 video_id）
- 无水印视频下载（替换 playwm → play）
- 视频元数据获取
- 音频提取（FFmpeg）
- Cookie 自动管理（Netscape 格式 + 字符串）

调用方式：
    python douyin_downloader_pro.py --json-input '{"func": "download_bgm", "params": {"url": "https://v.douyin.com/xxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}'

依赖：
    pip install httpx
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    httpx = None  # 延迟到调用时报错，便于 --json-input 协议输出友好错误

# ==================== 常量配置 ====================

# 抖音 Web API 端点
DOUYIN_DETAIL_API = "https://www.douyin.com/aweme/v1/web/aweme/detail/"

# 默认请求头
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.douyin.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Cookie 关键字段
COOKIE_REQUIRED_FIELDS = ["ttwid"]
COOKIE_OPTIONAL_FIELDS = ["sessionid", "sessionid_ss", "uid_tt", "sid_tt"]

# ==================== 配置加载（支持环境变量） ====================

# 项目根目录（用于计算相对路径）
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])


def _resolve_project_path(relative_path: str) -> str:
    """将相对路径解析为项目根目录下的绝对路径。"""
    return os.path.join(_PROJECT_ROOT, relative_path.replace("./", "").replace(".\\", ""))


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


# 默认 Cookie 路径（优先使用项目内路径，回退到 D 盘）
_PROJECT_COOKIE_PATH = os.path.join(_PROJECT_ROOT, "cookies", "douyin_cookies.txt")
DEFAULT_COOKIE_PATH = _get_env_or_default(
    "DOUYIN_COOKIE_PATH",
    _PROJECT_COOKIE_PATH
)

# 从环境变量读取 Cookie 字符串（优先于文件）
ENV_COOKIE = os.environ.get("DOUYIN_COOKIE", "")

# 默认输出目录
DEFAULT_OUTPUT_DIR = _get_env_or_default(
    "AEK_VIDEO_LIBRARY",
    "D:/AE-Work/视频素材库"
)
DEFAULT_BGM_DIR = _get_env_or_default(
    "AEK_BGM_LIBRARY",
    "D:/AE-Work/音频素材库/BGM"
)

# FFmpeg 命令
FFMPEG_CMD = _get_env_or_default("AEK_FFMPEG", "ffmpeg")

# 重试参数
MAX_RETRIES = 3
RETRY_DELAY = 1.5  # 秒

# 请求超时（秒）
REQUEST_TIMEOUT = 30.0
DOWNLOAD_TIMEOUT = 300.0


# ==================== 异常定义 ====================


class DouyinError(Exception):
    """抖音下载器基础异常"""


class CookieExpiredError(DouyinError):
    """Cookie 过期或无效"""


class VideoDeletedError(DouyinError):
    """视频已删除或不可访问"""


class NetworkError(DouyinError):
    """网络请求失败"""


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
        return "douyin_video"
    # 移除 Windows 文件系统非法字符
    cleaned = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", name)
    # 移除首尾空格和点
    cleaned = cleaned.strip(" .")
    # 截断长度
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned or "douyin_video"


def _parse_netscape_cookie(cookie_path: str) -> Dict[str, str]:
    """解析 Netscape 格式 cookie 文件。

    Args:
        cookie_path: cookie 文件路径

    Returns:
        cookie 字典 {name: value}
    """
    cookies: Dict[str, str] = {}
    if not os.path.exists(cookie_path):
        return cookies

    with open(cookie_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith("#"):
                continue
            # Netscape 格式: domain  flag  path  secure  expiration  name  value
            parts = line.split("\t")
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6]
                if name:
                    cookies[name] = value
    return cookies


def _parse_cookie_string(cookie_str: str) -> Dict[str, str]:
    """解析 cookie 字符串（key=value; key=value 格式）。

    Args:
        cookie_str: cookie 字符串

    Returns:
        cookie 字典
    """
    cookies: Dict[str, str] = {}
    if not cookie_str:
        return cookies
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            name, _, value = item.partition("=")
            name = name.strip()
            if name:
                cookies[name] = value.strip()
    return cookies


def _cookies_to_header(cookies: Dict[str, str]) -> str:
    """将 cookie 字典转换为 HTTP Cookie 头格式。

    Args:
        cookies: cookie 字典

    Returns:
        Cookie 头字符串
    """
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _resolve_cookie_source(
    cookie: Optional[str] = None,
    cookie_path: Optional[str] = None,
) -> Tuple[Dict[str, str], Optional[str]]:
    """从多种来源解析 cookie。

    优先级（从高到低）：
    1. cookie 字符串（直接传入）
    2. 环境变量 DOUYIN_COOKIE
    3. 环境变量 DOUYIN_COOKIE_PATH 指定的文件
    4. cookie_path 参数指定文件
    5. 项目默认 cookie 路径
    6. 项目内 cookies/douyin_cookies.txt

    Args:
        cookie: cookie 字符串
        cookie_path: cookie 文件路径

    Returns:
        (cookies_dict, used_path_or_None)
    """
    if cookie:
        return _parse_cookie_string(cookie), None

    # 环境变量中的 Cookie 字符串
    env_cookie = os.environ.get("DOUYIN_COOKIE", "")
    if env_cookie:
        return _parse_cookie_string(env_cookie), None

    # 尝试用户指定的路径
    candidates: List[str] = []
    if cookie_path:
        candidates.append(cookie_path)
    
    # 动态获取默认路径（支持运行时环境变量）
    default_path = os.environ.get("DOUYIN_COOKIE_PATH", DEFAULT_COOKIE_PATH)
    candidates.append(default_path)

    # 项目内 cookies 目录回退（B03 修复：确保项目相对路径始终可用）
    project_cookie_path = os.path.join(
        Path(__file__).resolve().parents[2], "cookies", "douyin_cookies.txt"
    )
    if project_cookie_path not in candidates:
        candidates.append(project_cookie_path)

    for path in candidates:
        if path and os.path.exists(path):
            cookies = _parse_netscape_cookie(path)
            if cookies:
                return cookies, path

    return {}, None


def _validate_cookies_dict(cookies: Dict[str, str]) -> Dict[str, Any]:
    """校验 cookie 字典是否包含必需字段。

    Args:
        cookies: cookie 字典

    Returns:
        校验结果字典
    """
    missing_required = [f for f in COOKIE_REQUIRED_FIELDS if f not in cookies]
    missing_optional = [f for f in COOKIE_OPTIONAL_FIELDS if f not in cookies]
    has_required = len(missing_required) == 0
    has_session = any(f in cookies for f in COOKIE_OPTIONAL_FIELDS)

    return {
        "valid": has_required,
        "has_required_fields": has_required,
        "has_session": has_session,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "field_count": len(cookies),
    }


# ==================== 核心下载器类 ====================


class DouyinDownloaderPro:
    """抖音专业下载器

    使用 httpx 异步 HTTP 客户端直接调用抖音 Web API，
    支持短链接解析、无水印视频下载、音频提取等功能。
    """

    def __init__(
        self,
        cookie: Optional[str] = None,
        cookie_path: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> None:
        """初始化下载器。

        Args:
            cookie: cookie 字符串（可选）
            cookie_path: cookie 文件路径（可选）
            proxy: 代理地址（可选，如 http://127.0.0.1:7890）
        """
        if httpx is None:
            raise DouyinError("缺少依赖 httpx，请运行: pip install httpx")

        self.cookies, self.used_cookie_path = _resolve_cookie_source(cookie, cookie_path)
        self.proxy = proxy

    # ---------- 请求辅助 ----------

    def _build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """构建请求头。

        Args:
            extra: 额外的头字段

        Returns:
            完整请求头字典
        """
        headers = dict(DEFAULT_HEADERS)
        if self.cookies:
            headers["Cookie"] = _cookies_to_header(self.cookies)
        if extra:
            headers.update(extra)
        return headers

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        follow_redirects: bool = True,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """带重试的 HTTP 请求。

        Args:
            method: HTTP 方法（GET/POST）
            url: 请求 URL
            params: 查询参数
            headers: 额外请求头
            follow_redirects: 是否跟踪重定向
            timeout: 超时时间

        Returns:
            httpx.Response 对象

        Raises:
            NetworkError: 网络请求失败
        """
        last_error: Optional[Exception] = None
        merged_headers = self._build_headers(headers)
        request_timeout = timeout or REQUEST_TIMEOUT

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    proxy=self.proxy,
                    follow_redirects=follow_redirects,
                    timeout=request_timeout,
                ) as client:
                    response = await client.request(
                        method,
                        url,
                        params=params,
                        headers=merged_headers,
                    )
                    return response
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)
                continue
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)
                continue

        raise NetworkError(f"请求失败（重试 {MAX_RETRIES} 次）: {last_error}")

    async def _download_stream(
        self,
        url: str,
        output_path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """异步流式下载文件。

        Args:
            url: 下载 URL
            output_path: 输出文件路径
            headers: 额外请求头

        Returns:
            下载完成的文件路径

        Raises:
            NetworkError: 下载失败
        """
        last_error: Optional[Exception] = None
        merged_headers = self._build_headers(headers)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    proxy=self.proxy,
                    follow_redirects=True,
                    timeout=DOWNLOAD_TIMEOUT,
                ) as client:
                    async with client.stream(
                        "GET", url, headers=merged_headers
                    ) as response:
                        response.raise_for_status()
                        # 确保输出目录存在
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        with open(output_path, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=65536):
                                f.write(chunk)
                        return output_path
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)
                continue

        raise NetworkError(f"下载失败（重试 {MAX_RETRIES} 次）: {last_error}")

    # ---------- 核心功能 ----------

    async def parse_share_url(self, share_url: str) -> Dict[str, Any]:
        """解析抖音短链接，跟踪重定向获取完整 URL 和 video_id。

        Args:
            share_url: 抖音分享链接（短链或长链）

        Returns:
            解析结果字典：
            - original_url: 原始 URL
            - final_url: 重定向后的最终 URL
            - video_id: 视频 ID
            - success: 是否成功
            - error: 错误信息（失败时）
        """
        result: Dict[str, Any] = {
            "original_url": share_url,
            "final_url": None,
            "video_id": None,
            "success": False,
            "error": None,
        }

        try:
            # 短链接需要跟踪重定向
            if "v.douyin.com" in share_url or "iesdouyin.com" in share_url:
                response = await self._request_with_retry(
                    "GET", share_url, follow_redirects=True
                )
                final_url = str(response.url)
            else:
                final_url = share_url

            result["final_url"] = final_url

            # 从 URL 中提取 video_id
            # 模式1: /video/{id}
            match = re.search(r"/video/(\d+)", final_url)
            if match:
                result["video_id"] = match.group(1)
                result["success"] = True
                return result

            # 模式2: modal_id={id}
            match = re.search(r"modal_id=(\d+)", final_url)
            if match:
                result["video_id"] = match.group(1)
                result["success"] = True
                return result

            # 模式3: URL 末尾的纯数字 ID
            match = re.search(r"/(\d{15,})(?:\?|$)", final_url)
            if match:
                result["video_id"] = match.group(1)
                result["success"] = True
                return result

            # 兜底：尝试从页面内容中提取
            if "v.douyin.com" in share_url or "iesdouyin.com" in share_url:
                # 已获取 response.url，但未匹配到 ID，尝试从页面 HTML 提取
                text = response.text
                match = re.search(r'"aweme_id"\s*:\s*"?(\d+)"?', text)
                if match:
                    result["video_id"] = match.group(1)
                    result["success"] = True
                    return result

            result["error"] = "无法从 URL 中提取 video_id"
            return result

        except Exception as e:
            result["error"] = f"解析短链接失败: {e}"
            return result

    async def get_video_info(
        self,
        video_id_or_url: str,
        cookie: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取视频元数据。

        Args:
            video_id_or_url: 视频 ID 或完整 URL
            cookie: 临时 cookie 字符串（可选，覆盖实例 cookie）

        Returns:
            视频信息字典：
            - success: 是否成功
            - video_id: 视频 ID
            - title: 视频标题
            - author: 作者昵称
            - author_id: 作者 ID
            - duration: 时长（秒）
            - video_url: 无水印视频 URL
            - video_url_watermark: 有水印视频 URL
            - cover_url: 封面 URL
            - play_count: 播放量
            - digg_count: 点赞数
            - comment_count: 评论数
            - create_time: 创建时间戳
            - error: 错误信息（失败时）
        """
        result: Dict[str, Any] = {
            "success": False,
            "video_id": None,
            "title": "",
            "author": "",
            "author_id": "",
            "duration": 0.0,
            "video_url": "",
            "video_url_watermark": "",
            "cover_url": "",
            "play_count": 0,
            "digg_count": 0,
            "comment_count": 0,
            "create_time": 0,
            "error": None,
        }

        # 临时使用传入的 cookie
        original_cookies = self.cookies
        if cookie:
            self.cookies = _parse_cookie_string(cookie)

        try:
            # 如果传入的是 URL，先解析获取 video_id
            video_id = video_id_or_url
            if not video_id.isdigit() and (
                "http" in video_id_or_url or "/" in video_id_or_url
            ):
                parse_result = await self.parse_share_url(video_id_or_url)
                if not parse_result.get("success"):
                    result["error"] = parse_result.get(
                        "error", "无法解析 video_id"
                    )
                    return result
                video_id = parse_result["video_id"]

            result["video_id"] = video_id

            # 调用抖音 API
            params = {
                "aweme_id": video_id,
                "aid": "1128",
                "device_platform": "web",
                "channel": "channel_pc_web",
            }
            response = await self._request_with_retry(
                "GET", DOUYIN_DETAIL_API, params=params
            )

            if response.status_code != 200:
                result["error"] = f"API 返回状态码 {response.status_code}"
                return result

            try:
                data = response.json()
            except Exception as e:
                result["error"] = f"解析 API 响应失败: {e}"
                return result

            # 检查视频状态
            aweme_detail = data.get("aweme_detail")
            if not aweme_detail:
                # 检查状态码判断视频是否删除
                status_code = data.get("status_code", -1)
                if status_code == 9:
                    raise VideoDeletedError(f"视频已删除或不存在: {video_id}")
                result["error"] = (
                    f"API 未返回视频详情（status_code={status_code}），"
                    "可能是 Cookie 失效或视频被删除"
                )
                # 检查 cookie 是否有效
                cookie_validation = _validate_cookies_dict(self.cookies)
                if not cookie_validation["valid"]:
                    raise CookieExpiredError(
                        "Cookie 缺少必需字段 ttwid，请刷新 Cookie"
                    )
                return result

            # 提取元数据
            result["title"] = aweme_detail.get("desc", "") or ""
            result["duration"] = float(
                aweme_detail.get("duration", 0)
            ) / 1000.0  # 抖音返回毫秒

            # 作者信息
            author_info = aweme_detail.get("author", {}) or {}
            result["author"] = author_info.get("nickname", "")
            result["author_id"] = author_info.get("uid", "") or author_info.get(
                "short_id", ""
            )

            # 视频地址
            video_info = aweme_detail.get("video", {}) or {}
            play_addr = video_info.get("play_addr", {}) or {}
            url_list = play_addr.get("url_list", []) or []

            if url_list:
                # 有水印 URL
                watermark_url = url_list[0]
                # 无水印 URL：替换 playwm → play
                no_watermark_url = watermark_url.replace("playwm", "play")
                result["video_url_watermark"] = watermark_url
                result["video_url"] = no_watermark_url

            # 封面
            cover_info = video_info.get("cover", {}) or {}
            cover_url_list = cover_info.get("url_list", []) or []
            if cover_url_list:
                result["cover_url"] = cover_url_list[0]

            # 统计信息
            statistics = aweme_detail.get("statistics", {}) or {}
            result["play_count"] = int(statistics.get("play_count", 0) or 0)
            result["digg_count"] = int(statistics.get("digg_count", 0) or 0)
            result["comment_count"] = int(
                statistics.get("comment_count", 0) or 0
            )

            # 创建时间
            result["create_time"] = int(
                aweme_detail.get("create_time", 0) or 0
            )

            result["success"] = True
            return result

        except (CookieExpiredError, VideoDeletedError):
            raise
        except Exception as e:
            result["error"] = f"获取视频信息失败: {e}"
            return result
        finally:
            # 恢复原始 cookie
            self.cookies = original_cookies

    async def download_video(
        self,
        url: str,
        output_dir: Optional[str] = None,
        cookie: Optional[str] = None,
        watermark_free: bool = True,
    ) -> Dict[str, Any]:
        """下载抖音视频。

        Args:
            url: 抖音分享链接或视频 ID
            output_dir: 输出目录（默认使用 D:/AE-Work/视频素材库）
            cookie: 临时 cookie 字符串（可选）
            watermark_free: 是否下载无水印版本

        Returns:
            下载结果字典：
            - success: 是否成功
            - file_path: 下载文件路径
            - title: 视频标题
            - author: 作者
            - duration: 时长
            - video_url: 视频 URL
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
            "video_url": "",
            "platform": "douyin",
            "error": None,
        }

        try:
            # 获取视频信息
            info = await self.get_video_info(url, cookie=cookie)
            if not info.get("success"):
                result["error"] = info.get(
                    "error", "获取视频信息失败"
                )
                return result

            # 选择视频 URL
            if watermark_free:
                video_url = info.get("video_url") or info.get(
                    "video_url_watermark", ""
                )
            else:
                video_url = info.get("video_url_watermark") or info.get(
                    "video_url", ""
                )

            if not video_url:
                result["error"] = "无法获取视频下载 URL"
                return result

            # 构建输出文件名
            title = info.get("title", "")
            safe_name = _safe_filename(title) if title else f"douyin_{info['video_id']}"
            file_path = os.path.join(output_dir, f"{safe_name}.mp4")

            # 流式下载
            await self._download_stream(video_url, file_path)

            # 验证文件
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                result["error"] = "下载文件为空或不存在"
                return result

            result["success"] = True
            result["file_path"] = file_path
            result["title"] = info.get("title", "")
            result["author"] = info.get("author", "")
            result["duration"] = info.get("duration", 0.0)
            result["video_url"] = video_url
            return result

        except (CookieExpiredError, VideoDeletedError) as e:
            result["error"] = str(e)
            return result
        except Exception as e:
            result["error"] = f"下载视频失败: {e}"
            return result

    async def download_bgm(
        self,
        url: str,
        output_dir: Optional[str] = None,
        cookie: Optional[str] = None,
    ) -> Dict[str, Any]:
        """下载视频并提取音频为 MP3。

        流程：下载无水印视频 → FFmpeg 提取音频

        Args:
            url: 抖音分享链接或视频 ID
            output_dir: 输出目录（默认使用 D:/AE-Work/音频素材库/BGM）
            cookie: 临时 cookie 字符串（可选）

        Returns:
            下载结果字典：
            - success: 是否成功
            - file_path: MP3 文件路径
            - video_path: 中间视频文件路径（删除失败时保留）
            - title: 视频标题
            - author: 作者
            - duration: 时长
            - error: 错误信息（失败时）
        """
        if output_dir is None:
            output_dir = DEFAULT_BGM_DIR

        result: Dict[str, Any] = {
            "success": False,
            "file_path": None,
            "video_path": None,
            "title": "",
            "author": "",
            "duration": 0.0,
            "platform": "douyin",
            "error": None,
        }

        # 临时目录用于存放中间视频
        temp_dir = os.path.join(output_dir, ".tmp")
        os.makedirs(temp_dir, exist_ok=True)
        video_path: Optional[str] = None

        try:
            # 步骤1：下载视频
            video_result = await self.download_video(
                url, output_dir=temp_dir, cookie=cookie, watermark_free=True
            )

            if not video_result.get("success"):
                result["error"] = f"下载视频失败: {video_result.get('error')}"
                return result

            video_path = video_result["file_path"]
            result["video_path"] = video_path
            result["title"] = video_result.get("title", "")
            result["author"] = video_result.get("author", "")
            result["duration"] = video_result.get("duration", 0.0)

            # 步骤2：FFmpeg 提取音频
            os.makedirs(output_dir, exist_ok=True)
            title = video_result.get("title", "")
            safe_name = _safe_filename(title) if title else os.path.splitext(
                os.path.basename(video_path)
            )[0]
            mp3_path = os.path.join(output_dir, f"{safe_name}.mp3")

            # ffmpeg -y -i input.mp4 -vn -acodec libmp3lame -ab 192k output.mp3
            cmd = [
                FFMPEG_CMD,
                "-y",
                "-i",
                video_path,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-ab",
                "192k",
                mp3_path,
            ]

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )

            if process.returncode != 0:
                result["error"] = (
                    f"FFmpeg 提取音频失败: {process.stderr[:500]}"
                )
                return result

            if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
                result["error"] = "MP3 文件生成失败或为空"
                return result

            # 清理中间视频文件
            try:
                os.remove(video_path)
                result["video_path"] = None
            except Exception:
                # 清理失败不影响主流程
                pass

            result["success"] = True
            result["file_path"] = mp3_path
            return result

        except subprocess.TimeoutExpired:
            result["error"] = "FFmpeg 提取音频超时"
            return result
        except Exception as e:
            result["error"] = f"提取音频失败: {e}"
            return result
        finally:
            # 清理临时目录中的残留文件
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception:
                    pass

    # ---------- Cookie 管理 ----------

    def validate_cookie(
        self, cookie_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """验证 Cookie 文件有效性。

        检查关键字段：ttwid（必需）、sessionid 等（可选）

        Args:
            cookie_path: cookie 文件路径（默认使用实例配置）

        Returns:
            验证结果字典：
            - valid: 是否有效
            - cookie_path: 使用的 cookie 路径
            - has_required_fields: 是否有必需字段
            - has_session: 是否有 session 字段
            - missing_required: 缺失的必需字段
            - missing_optional: 缺失的可选字段
            - field_count: 字段总数
            - error: 错误信息（失败时）
        """
        path = cookie_path or self.used_cookie_path or DEFAULT_COOKIE_PATH

        result: Dict[str, Any] = {
            "valid": False,
            "cookie_path": path,
            "has_required_fields": False,
            "has_session": False,
            "missing_required": [],
            "missing_optional": [],
            "field_count": 0,
            "error": None,
        }

        if not os.path.exists(path):
            result["error"] = f"Cookie 文件不存在: {path}"
            return result

        try:
            cookies = _parse_netscape_cookie(path)
        except Exception as e:
            result["error"] = f"解析 Cookie 文件失败: {e}"
            return result

        if not cookies:
            result["error"] = "Cookie 文件为空或格式错误"
            return result

        validation = _validate_cookies_dict(cookies)
        result.update(validation)
        return result

    def auto_manage_cookies(
        self, cookie_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """自动检测 Cookie 状态，如失效则提示刷新。

        Args:
            cookie_path: cookie 文件路径

        Returns:
            管理结果字典：
            - action: 执行的动作（valid/refresh_needed/generated_template）
            - message: 描述信息
            - cookie_path: cookie 路径
            - validation: 验证详情
        """
        path = cookie_path or self.used_cookie_path or DEFAULT_COOKIE_PATH
        validation = self.validate_cookie(path)

        if validation.get("valid"):
            return {
                "action": "valid",
                "message": "Cookie 验证通过",
                "cookie_path": path,
                "validation": validation,
            }

        # Cookie 失效，提示刷新
        return {
            "action": "refresh_needed",
            "message": (
                "Cookie 已失效或缺少必需字段 ttwid。"
                "请按以下步骤刷新：\n"
                "1. 在浏览器中登录 https://www.douyin.com\n"
                "2. 打开开发者工具 (F12) → Application → Cookies\n"
                "3. 复制 ttwid 等关键字段\n"
                "4. 更新 Netscape 格式的 cookie 文件"
            ),
            "cookie_path": path,
            "validation": validation,
        }


# ==================== 同步包装器（用于 --json-input 协议） ====================


def _run_async(coro):
    """同步运行异步协程。

    在 Windows 上使用 asyncio.run 处理 ProactorEventLoop。
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已在事件循环中，使用 future
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)
    except RuntimeError:
        return asyncio.run(coro)


_SENSITIVE_PATTERNS = ["cookie", "sessionid", "ttwid", "sid_tt", "uid_tt", "token", "api_key", "secret"]


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
    if "cookie" in params:
        init_kwargs["cookie"] = params.pop("cookie")
    if "cookie_path" in params:
        init_kwargs["cookie_path"] = params.pop("cookie_path")
    if "proxy" in params:
        init_kwargs["proxy"] = params.pop("proxy")

    try:
        downloader = DouyinDownloaderPro(**init_kwargs)
    except DouyinError as e:
        return {"success": False, "error": str(e)}

    # 异步函数映射
    async_func_map = {
        "parse_share_url": downloader.parse_share_url,
        "get_video_info": downloader.get_video_info,
        "download_video": downloader.download_video,
        "download_bgm": downloader.download_bgm,
    }

    # 同步函数映射
    sync_func_map = {
        "validate_cookie": downloader.validate_cookie,
        "auto_manage_cookies": downloader.auto_manage_cookies,
    }

    try:
        if func_name in async_func_map:
            coro = async_func_map[func_name](**params)
            return _run_async(coro)
        elif func_name in sync_func_map:
            return sync_func_map[func_name](**params)
        else:
            return {
                "success": False,
                "error": f"未知函数: {func_name}，"
                f"支持的函数: {list(async_func_map.keys()) + list(sync_func_map.keys())}",
            }
    except TypeError as e:
        return {"success": False, "error": _sanitize_error(f"参数错误: {e}")}
    except (CookieExpiredError, VideoDeletedError) as e:
        return {"success": False, "error": _sanitize_error(str(e))}
    except Exception as e:
        return {"success": False, "error": _sanitize_error(f"执行失败: {e}")}


# ==================== 主入口 ====================


def main() -> None:
    """主入口函数，支持 --json-input 参数。

    调用方式：
        python douyin_downloader_pro.py --json-input '{"func": "download_bgm", "params": {...}}'
        echo '{"func": "...", "params": {...}}' | python douyin_downloader_pro.py --json-input
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            # 优先从 argv 读取，其次从 stdin 读取
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
                    {"success": False, "error": _sanitize_error(f"内部错误: {e}")},
                    ensure_ascii=False,
                )
            )
        return

    # 交互模式：打印帮助信息
    print("抖音专业下载器 - 使用 httpx 直接调用抖音 Web API")
    print()
    print("使用方式：")
    print('  python douyin_downloader.py --json-input \'{"func": "download_bgm", "params": {"url": "https://v.douyin.com/xxx", "output_dir": "D:/AE-Work/音频素材库/BGM"}}\'')
    print()
    print("支持的函数：")
    print("  - parse_share_url(share_url): 解析短链接获取 video_id")
    print("  - get_video_info(video_id_or_url, cookie?): 获取视频元数据")
    print("  - download_video(url, output_dir?, cookie?, watermark_free?): 下载视频")
    print("  - download_bgm(url, output_dir?, cookie?): 下载并提取音频为 MP3")
    print("  - validate_cookie(cookie_path?): 验证 Cookie 文件")
    print("  - auto_manage_cookies(cookie_path?): 自动检测 Cookie 状态")
    print()
    print("输出格式示例：")
    print(json.dumps(
        {
            "success": True,
            "file_path": "D:/AE-Work/音频素材库/BGM/xxx.mp3",
            "title": "视频标题",
            "author": "作者",
            "duration": 55.52,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
