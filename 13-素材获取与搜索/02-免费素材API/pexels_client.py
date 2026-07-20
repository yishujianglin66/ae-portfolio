"""
Pexels API 客户端
=================

提供对 Pexels 免费素材库的程序化访问能力，支持视频/图片搜索与下载。

API 文档：https://www.pexels.com/api/
限制：200 requests/hour，需 API Key（Authorization Header）

主要功能：
    - search_videos: 搜索视频素材
    - search_photos: 搜索图片素材
    - get_popular_videos: 获取热门视频
    - get_video: 获取单个视频详情
    - download_video: 下载视频文件

使用方式：
    1. CLI 模式：python pexels_client.py
    2. JSON 输入模式：python pexels_client.py --json-input '{"func":"search_videos","params":{...}}'
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests


# =============================================================================
# 常量定义
# =============================================================================

PEXELS_VIDEO_SEARCH_ENDPOINT = "https://api.pexels.com/videos/search"
PEXELS_VIDEO_POPULAR_ENDPOINT = "https://api.pexels.com/videos/popular"
PEXELS_VIDEO_DETAIL_ENDPOINT = "https://api.pexels.com/videos/videos"
PEXELS_PHOTO_SEARCH_ENDPOINT = "https://api.pexels.com/v1/search"
PEXELS_PHOTO_POPULAR_ENDPOINT = "https://api.pexels.com/v1/curated"

# 速率限制：200 次/小时
RATE_LIMIT_PER_HOUR = 200

# 请求超时（秒）
REQUEST_TIMEOUT = 30

# 允许的朝向
VALID_ORIENTATIONS = {"", "landscape", "portrait", "square"}
# 允许的画质
VALID_QUALITIES = {"hd", "sd", "uhd"}


# =============================================================================
# 异常定义
# =============================================================================

class PexelsError(Exception):
    """Pexels 客户端基础异常"""


class PexelsAuthError(PexelsError):
    """API Key 无效或缺失"""


class PexelsRateLimitError(PexelsError):
    """触发速率限制"""


class PexelsNotFoundError(PexelsError):
    """资源未找到"""


# =============================================================================
# 核心客户端
# =============================================================================

class PexelsClient:
    """
    Pexels API 客户端

    通过 Authorization Header 鉴权，封装视频/图片搜索与下载能力。
    """

    def __init__(self, api_key: str, output_dir: Optional[str] = None):
        """
        初始化客户端

        :param api_key: Pexels API Key
        :param output_dir: 默认下载目录
        """
        if not api_key or not isinstance(api_key, str):
            raise PexelsAuthError("Pexels API Key 不能为空")
        self.api_key = api_key
        self.output_dir = output_dir or os.getcwd()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": api_key,
            "User-Agent": "AE-Knowledge-Vault/1.0 (Pexels Client)",
        })
        self._request_timestamps: List[float] = []

    # -------------------------------------------------------------------------
    # 内部工具方法
    # -------------------------------------------------------------------------

    def _throttle(self) -> None:
        """客户端侧节流：保留最近 1 小时内的请求时间戳"""
        now = time.time()
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 3600]
        if len(self._request_timestamps) >= RATE_LIMIT_PER_HOUR:
            wait = 3600 - (now - self._request_timestamps[0])
            if wait > 0:
                raise PexelsRateLimitError(
                    f"已达速率限制 {RATE_LIMIT_PER_HOUR} req/hour，"
                    f"请等待 {int(wait)} 秒后重试"
                )
        self._request_timestamps.append(now)

    def _request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        发起 GET 请求并返回 JSON

        :param url: API 端点
        :param params: 查询参数
        :return: 解析后的 JSON 字典
        """
        self._throttle()
        try:
            response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            raise PexelsError(f"请求超时（{REQUEST_TIMEOUT}s）：{url}")
        except requests.exceptions.ConnectionError as e:
            raise PexelsError(f"网络连接失败：{e}")
        except requests.exceptions.RequestException as e:
            raise PexelsError(f"请求异常：{e}")

        if response.status_code in (401, 403):
            raise PexelsAuthError("API Key 无效或无权访问")
        if response.status_code == 429:
            # 读取 Retry-After 头
            retry_after = response.headers.get("Retry-After", "")
            raise PexelsRateLimitError(
                f"服务端返回速率限制（429），"
                f"建议等待 {retry_after or '一段时间'} 后重试"
            )
        if response.status_code == 404:
            raise PexelsNotFoundError(f"资源未找到：{url}")
        if response.status_code >= 500:
            raise PexelsError(f"Pexels 服务异常（HTTP {response.status_code}）")

        try:
            return response.json()
        except ValueError:
            raise PexelsError(f"响应解析失败（非 JSON）：{response.text[:200]}")

    def _download_file(self, url: str, output_path: str) -> Dict:
        """
        下载文件到本地

        :param url: 文件 URL
        :param output_path: 输出路径
        :return: 下载结果字典
        """
        try:
            with self.session.get(url, stream=True, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"下载失败 HTTP {resp.status_code}",
                        "url": url,
                    }
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                total = 0
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                return {
                    "success": True,
                    "url": url,
                    "path": output_path,
                    "size": total,
                }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"下载异常：{e}", "url": url}
        except OSError as e:
            return {"success": False, "error": f"文件写入失败：{e}", "url": url}

    # -------------------------------------------------------------------------
    # 视频搜索
    # -------------------------------------------------------------------------

    def search_videos(
        self,
        query: str,
        per_page: int = 15,
        page: int = 1,
        orientation: str = "",
    ) -> Dict:
        """
        搜索视频素材

        API 端点：GET https://api.pexels.com/videos/search

        :param query: 搜索关键词
        :param per_page: 每页结果数（1-80，默认 15）
        :param page: 页码
        :param orientation: 朝向：landscape/portrait/square，留空表示所有
        :return: 包含 page、per_page、total_results、url、videos 数组的字典
        """
        if not query or not isinstance(query, str):
            raise ValueError("query 不能为空")
        if not (1 <= per_page <= 80):
            raise ValueError(f"per_page 范围 1-80，当前 {per_page}")
        if page < 1:
            raise ValueError(f"page 必须 ≥ 1，当前 {page}")
        if orientation and orientation not in VALID_ORIENTATIONS:
            raise ValueError(f"orientation 非法：'{orientation}'，可选 {sorted(VALID_ORIENTATIONS)}")

        params = {"query": query, "per_page": per_page, "page": page}
        if orientation:
            params["orientation"] = orientation

        return self._request(PEXELS_VIDEO_SEARCH_ENDPOINT, params)

    def get_popular_videos(
        self,
        per_page: int = 15,
        page: int = 1,
    ) -> Dict:
        """
        获取热门视频

        API 端点：GET https://api.pexels.com/videos/popular

        :param per_page: 每页结果数（1-80）
        :param page: 页码
        :return: 热门视频列表
        """
        if not (1 <= per_page <= 80):
            raise ValueError(f"per_page 范围 1-80，当前 {per_page}")
        if page < 1:
            raise ValueError(f"page 必须 ≥ 1，当前 {page}")

        params = {"per_page": per_page, "page": page}
        return self._request(PEXELS_VIDEO_POPULAR_ENDPOINT, params)

    def get_video(self, video_id: str) -> Dict:
        """
        获取单个视频信息

        API 端点：GET https://api.pexels.com/videos/videos/{id}

        :param video_id: 视频 ID
        :return: 视频详情（包含 video_files 数组）
        """
        if not video_id:
            raise ValueError("video_id 不能为空")
        url = f"{PEXELS_VIDEO_DETAIL_ENDPOINT}/{video_id}"
        return self._request(url)

    # -------------------------------------------------------------------------
    # 图片搜索
    # -------------------------------------------------------------------------

    def search_photos(
        self,
        query: str,
        per_page: int = 15,
        page: int = 1,
        orientation: str = "",
    ) -> Dict:
        """
        搜索图片素材

        API 端点：GET https://api.pexels.com/v1/search

        :param query: 搜索关键词
        :param per_page: 每页结果数（1-80）
        :param page: 页码
        :param orientation: 朝向
        :return: 包含 photos 数组的字典
        """
        if not query or not isinstance(query, str):
            raise ValueError("query 不能为空")
        if not (1 <= per_page <= 80):
            raise ValueError(f"per_page 范围 1-80，当前 {per_page}")
        if page < 1:
            raise ValueError(f"page 必须 ≥ 1，当前 {page}")
        if orientation and orientation not in VALID_ORIENTATIONS:
            raise ValueError(f"orientation 非法：'{orientation}'")

        params = {"query": query, "per_page": per_page, "page": page}
        if orientation:
            params["orientation"] = orientation

        return self._request(PEXELS_PHOTO_SEARCH_ENDPOINT, params)

    def get_curated_photos(
        self,
        per_page: int = 15,
        page: int = 1,
    ) -> Dict:
        """
        获取编辑精选图片

        API 端点：GET https://api.pexels.com/v1/curated

        :param per_page: 每页结果数
        :param page: 页码
        :return: 精选图片列表
        """
        if not (1 <= per_page <= 80):
            raise ValueError(f"per_page 范围 1-80，当前 {per_page}")
        if page < 1:
            raise ValueError(f"page 必须 ≥ 1，当前 {page}")
        params = {"per_page": per_page, "page": page}
        return self._request(PEXELS_PHOTO_POPULAR_ENDPOINT, params)

    # -------------------------------------------------------------------------
    # 下载接口
    # -------------------------------------------------------------------------

    def download_video(
        self,
        video_id: str,
        output_dir: Optional[str] = None,
        quality: str = "hd",
    ) -> Dict:
        """
        下载视频文件

        先调用 get_video 获取 video_files，再选择符合画质要求的文件下载。

        :param video_id: 视频 ID
        :param output_dir: 输出目录，默认使用实例配置
        :param quality: 画质偏好：hd/sd/uhd（实际按可用性降级）
        :return: 下载结果字典
        """
        if not video_id:
            raise ValueError("video_id 不能为空")
        if quality not in VALID_QUALITIES:
            raise ValueError(f"quality 非法：'{quality}'，可选 {sorted(VALID_QUALITIES)}")

        # 获取视频详情
        try:
            video = self.get_video(video_id)
        except PexelsNotFoundError:
            return {"success": False, "error": f"未找到 video_id={video_id}"}

        video_files = video.get("video_files", []) or []
        if not video_files:
            return {"success": False, "error": "视频无可下载文件"}

        # 按画质优先级选择
        # uhd > hd > sd；视频文件 quality 字段可能为空
        quality_priority = {
            "uhd": ["uhd", "hd", "sd", ""],
            "hd": ["hd", "uhd", "sd", ""],
            "sd": ["sd", "hd", "uhd", ""],
        }
        preferred_order = quality_priority.get(quality, ["hd", "sd", "uhd", ""])

        selected = None
        for pref in preferred_order:
            for vf in video_files:
                vf_q = (vf.get("quality") or "").lower()
                if vf_q == pref:
                    selected = vf
                    break
            if selected:
                break

        if not selected:
            # 任意取第一个
            selected = video_files[0]

        url = selected.get("link")
        if not url:
            return {"success": False, "error": "视频 URL 缺失"}

        # 文件类型推断
        file_type = selected.get("file_type", "video/mp4")
        ext = "mp4"
        if "webm" in file_type or "webm" in url.lower():
            ext = "webm"
        elif "mov" in file_type:
            ext = "mov"
        elif "mkv" in file_type:
            ext = "mkv"

        # 描述性文件名
        vf_quality = selected.get("quality", "unknown")
        vf_w = selected.get("width", 0)
        vf_h = selected.get("height", 0)
        out_dir = output_dir or self.output_dir
        filename = f"pexels_video_{video_id}_{vf_quality}_{vf_w}x{vf_h}.{ext}"
        output_path = os.path.join(out_dir, filename)

        result = self._download_file(url, output_path)
        result["video_id"] = video_id
        result["quality"] = vf_quality
        result["width"] = vf_w
        result["height"] = vf_h
        if result.get("success"):
            result["title"] = ""
            result["author"] = (video.get("user") or {}).get("name", "")
            result["duration"] = video.get("duration", 0)
        return result


# =============================================================================
# 统一结果格式化（供 unified_search 使用）
# =============================================================================

def normalize_video_result(raw: Dict) -> Dict:
    """
    将 Pexels 视频结果归一化为统一格式

    :param raw: 单个 video 对象
    :return: 统一格式的结果字典
    """
    video_files = raw.get("video_files", []) or []
    # 优先取 hd 画质
    selected = None
    for vf in video_files:
        if (vf.get("quality") or "").lower() == "hd":
            selected = vf
            break
    if not selected and video_files:
        selected = video_files[0]

    # 取最佳预览图
    video_pictures = raw.get("video_pictures", []) or []
    thumbnail = video_pictures[0].get("picture", "") if video_pictures else ""

    user = raw.get("user", {}) or {}
    return {
        "platform": "pexels",
        "id": str(raw.get("id", "")),
        "title": "",
        "type": "video",
        "url": selected.get("link", "") if selected else "",
        "thumbnail": thumbnail,
        "duration": raw.get("duration", 0),
        "width": selected.get("width", 0) if selected else 0,
        "height": selected.get("height", 0) if selected else 0,
        "size": 0,
        "author": user.get("name", ""),
        "author_url": user.get("url", ""),
        "license": "Pexels License (free to use)",
        "page_url": raw.get("url", ""),
        "raw": raw,
    }


def normalize_photo_result(raw: Dict) -> Dict:
    """
    将 Pexels 图片结果归一化为统一格式
    """
    src = raw.get("src", {}) or {}
    return {
        "platform": "pexels",
        "id": str(raw.get("id", "")),
        "title": raw.get("alt", ""),
        "type": "image",
        "url": src.get("large2x", "") or src.get("large", "") or src.get("original", ""),
        "thumbnail": src.get("small", "") or src.get("tiny", "") or src.get("preview", ""),
        "duration": 0,
        "width": raw.get("width", 0),
        "height": raw.get("height", 0),
        "size": 0,
        "author": raw.get("photographer", ""),
        "author_url": raw.get("photographer_url", ""),
        "license": "Pexels License (free to use)",
        "page_url": raw.get("url", ""),
        "raw": raw,
    }


# =============================================================================
# 命令行入口
# =============================================================================

def _load_api_key() -> str:
    """从环境变量或配置文件加载 API Key"""
    key = os.environ.get("PEXELS_API_KEY")
    if key and not key.startswith("YOUR_"):
        return key
    keys_file = Path(__file__).parent / "api_keys.json"
    if keys_file.exists():
        try:
            with open(keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = data.get("pexels_api_key", "")
            if key and not key.startswith("YOUR_"):
                return key
        except (json.JSONDecodeError, OSError):
            pass
    template = Path(__file__).parent / "api_keys_template.json"
    if template.exists():
        try:
            with open(template, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = data.get("pexels_api_key", "")
            if key and not key.startswith("YOUR_"):
                return key
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def main() -> None:
    """
    CLI 入口

    支持 --json-input 协议：
        python pexels_client.py --json-input '{"func":"search_videos","params":{...}}'
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()

            request = json.loads(input_data) if input_data else {}
            api_key = request.get("api_key") or _load_api_key()

            if not api_key:
                print(json.dumps({
                    "success": False,
                    "error": "未提供 Pexels API Key，请在请求 params.api_key 或环境变量 PEXELS_API_KEY 中提供"
                }, ensure_ascii=False))
                return

            client = PexelsClient(api_key=api_key)
            func_name = request.get("func")
            params = request.get("params", {}) or {}

            func_map = {
                "search_videos": client.search_videos,
                "search_photos": client.search_photos,
                "get_popular_videos": client.get_popular_videos,
                "get_curated_photos": client.get_curated_photos,
                "get_video": client.get_video,
                "download_video": client.download_video,
            }

            if func_name in func_map:
                result = func_map[func_name](**params)
            else:
                result = {
                    "success": False,
                    "error": f"未知函数：{func_name}，支持：{list(func_map.keys())}"
                }

            print(json.dumps(result, ensure_ascii=False, default=str))
        except PexelsAuthError as e:
            print(json.dumps({"success": False, "error": f"鉴权失败：{e}"}, ensure_ascii=False))
        except PexelsRateLimitError as e:
            print(json.dumps({"success": False, "error": f"速率限制：{e}"}, ensure_ascii=False))
        except PexelsError as e:
            print(json.dumps({"success": False, "error": f"Pexels 错误：{e}"}, ensure_ascii=False))
        except ValueError as e:
            print(json.dumps({"success": False, "error": f"参数错误：{e}"}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": f"未知异常：{e}"}, ensure_ascii=False))
        return

    # 无参数模式
    print("=" * 70)
    print("Pexels API 客户端")
    print("=" * 70)
    print("用法：")
    print("  1. JSON 输入模式：")
    print('     python pexels_client.py --json-input \'{"func":"search_videos","params":{"query":"ocean","per_page":5}}\'')
    print("  2. 管道模式：")
    print('     echo \'{"func":"get_video","params":{"video_id":"12345"}}\' | python pexels_client.py --json-input')
    print()
    print("可用函数：")
    print("  - search_videos(query, per_page, page, orientation)")
    print("  - search_photos(query, per_page, page, orientation)")
    print("  - get_popular_videos(per_page, page)")
    print("  - get_curated_photos(per_page, page)")
    print("  - get_video(video_id)")
    print("  - download_video(video_id, output_dir, quality)")
    print()
    print("API Key 来源优先级：")
    print("  1. 请求 params.api_key")
    print("  2. 环境变量 PEXELS_API_KEY")
    print("  3. 同目录 api_keys.json")
    print("  4. 同目录 api_keys_template.json")
    print()
    print("速率限制：200 requests/hour")
    print("API 文档：https://www.pexels.com/api/")


if __name__ == "__main__":
    main()
