"""
Pixabay API 客户端
=================

提供对 Pixabay 免费素材库的程序化访问能力，支持视频、图片搜索与下载。

API 文档：https://pixabay.com/api/docs/
限制：100 requests/hour，需 API Key

主要功能：
    - search_videos: 搜索视频素材
    - search_images: 搜索图片素材
    - search_music: 搜索音乐素材（注：Pixabay 音乐 API 未公开文档）
    - download_video: 下载指定视频
    - download_image: 下载指定图片

使用方式：
    1. CLI 模式：python pixabay_client.py
    2. JSON 输入模式：python pixabay_client.py --json-input '{"func":"search_videos","params":{...}}'
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

PIXABAY_VIDEO_ENDPOINT = "https://pixabay.com/api/videos/"
PIXABAY_IMAGE_ENDPOINT = "https://pixabay.com/api/"
# Pixabay 音乐 API 端点（非官方公开，参考社区用法）
PIXABAY_MUSIC_ENDPOINT = "https://pixabay.com/api/music/"

# 速率限制：100 次/小时
RATE_LIMIT_PER_HOUR = 100

# 请求超时（秒）
REQUEST_TIMEOUT = 30

# 允许的视频类型
VALID_VIDEO_TYPES = {"all", "film", "animation"}
# 允许的朝向
VALID_ORIENTATIONS = {"all", "horizontal", "vertical"}
# 允许的排序
VALID_ORDER = {"popular", "latest"}
# 允许的图片类型
VALID_IMAGE_TYPES = {"all", "photo", "illustration", "vector"}
# Pixabay 分类列表
VALID_CATEGORIES = {
    "", "backgrounds", "fashion", "nature", "science", "education",
    "feelings", "health", "people", "religion", "places", "animals",
    "industry", "food", "computer", "sports", "transportation",
    "travel", "buildings", "business", "music"
}


# =============================================================================
# 异常定义
# =============================================================================

class PixabayError(Exception):
    """Pixabay 客户端基础异常"""


class PixabayAuthError(PixabayError):
    """API Key 无效或缺失"""


class PixabayRateLimitError(PixabayError):
    """触发速率限制"""


class PixabayNotFoundError(PixabayError):
    """资源未找到"""


# =============================================================================
# 核心客户端
# =============================================================================

class PixabayClient:
    """
    Pixabay API 客户端

    封装视频/图片搜索与下载能力，提供完善的错误处理与参数校验。
    """

    def __init__(self, api_key: str, output_dir: Optional[str] = None):
        """
        初始化客户端

        :param api_key: Pixabay API Key
        :param output_dir: 默认下载目录，未指定时使用当前目录
        """
        if not api_key or not isinstance(api_key, str):
            raise PixabayAuthError("Pixabay API Key 不能为空")
        self.api_key = api_key
        self.output_dir = output_dir or os.getcwd()
        self.session = requests.Session()
        # 记录最近请求时间，便于客户端侧节流
        self._request_timestamps: List[float] = []

    # -------------------------------------------------------------------------
    # 内部工具方法
    # -------------------------------------------------------------------------

    def _build_params(self, **kwargs) -> Dict[str, str]:
        """构造请求参数，自动附加 API Key"""
        params = {"key": self.api_key}
        for k, v in kwargs.items():
            if v is None:
                continue
            if isinstance(v, bool):
                params[k] = "true" if v else "false"
            else:
                params[k] = str(v)
        return params

    def _throttle(self) -> None:
        """客户端侧简单节流：保留最近 1 小时内的请求时间戳"""
        now = time.time()
        # 清理 1 小时前的记录
        self._request_timestamps = [t for t in self._request_timestamps if now - t < 3600]
        if len(self._request_timestamps) >= RATE_LIMIT_PER_HOUR:
            wait = 3600 - (now - self._request_timestamps[0])
            if wait > 0:
                raise PixabayRateLimitError(
                    f"已达速率限制 {RATE_LIMIT_PER_HOUR} req/hour，"
                    f"请等待 {int(wait)} 秒后重试"
                )
        self._request_timestamps.append(now)

    def _request(self, url: str, params: Dict[str, str]) -> Dict:
        """
        发起 GET 请求并返回 JSON

        :param url: API 端点
        :param params: 请求参数
        :return: 解析后的 JSON 字典
        """
        self._throttle()
        try:
            response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            raise PixabayError(f"请求超时（{REQUEST_TIMEOUT}s）：{url}")
        except requests.exceptions.ConnectionError as e:
            raise PixabayError(f"网络连接失败：{e}")
        except requests.exceptions.RequestException as e:
            raise PixabayError(f"请求异常：{e}")

        # HTTP 状态码处理
        if response.status_code == 401 or response.status_code == 403:
            raise PixabayAuthError("API Key 无效或无权访问")
        if response.status_code == 429:
            raise PixabayRateLimitError("服务端返回速率限制（429 Too Many Requests）")
        if response.status_code == 404:
            raise PixabayNotFoundError(f"资源未找到：{url}")
        if response.status_code >= 500:
            raise PixabayError(f"Pixabay 服务异常（HTTP {response.status_code}）")

        try:
            data = response.json()
        except ValueError:
            raise PixabayError(f"响应解析失败（非 JSON）：{response.text[:200]}")

        # Pixabay 错误字段
        if isinstance(data, dict) and data.get("Error"):
            raise PixabayError(f"Pixabay 返回错误：{data['Error']}")

        return data

    def _validate_choice(self, value: str, valid_set: set, name: str) -> str:
        """校验枚举值"""
        if value not in valid_set:
            raise ValueError(
                f"参数 {name} 非法：'{value}'，可选值：{sorted(valid_set)}"
            )
        return value

    # -------------------------------------------------------------------------
    # 搜索接口
    # -------------------------------------------------------------------------

    def search_videos(
        self,
        query: str,
        per_page: int = 20,
        page: int = 1,
        video_type: str = "all",
        orientation: str = "all",
        category: str = "",
        order: str = "popular",
    ) -> Dict:
        """
        搜索视频素材

        API 端点：https://pixabay.com/api/videos/

        :param query: 搜索关键词（URL 编码，最大长度 100）
        :param per_page: 每页结果数（3-200，默认 20）
        :param page: 页码（从 1 开始）
        :param video_type: 视频类型：all/film/animation
        :param orientation: 朝向：all/horizontal/vertical
        :param category: 分类，留空表示所有分类
        :param order: 排序：popular/latest
        :return: 包含 total、totalHits、hits 的字典
        """
        if not query or not isinstance(query, str):
            raise ValueError("query 不能为空")
        if not (1 <= per_page <= 200):
            raise ValueError(f"per_page 范围 1-200，当前 {per_page}")
        if page < 1:
            raise ValueError(f"page 必须 ≥ 1，当前 {page}")

        self._validate_choice(video_type, VALID_VIDEO_TYPES, "video_type")
        self._validate_choice(orientation, VALID_ORIENTATIONS, "orientation")
        self._validate_choice(order, VALID_ORDER, "order")
        if category and category not in VALID_CATEGORIES:
            raise ValueError(f"category 非法：'{category}'")

        params = self._build_params(
            q=query,
            per_page=per_page,
            page=page,
            video_type=video_type,
            orientation=orientation,
            category=category or None,
            order=order,
        )

        return self._request(PIXABAY_VIDEO_ENDPOINT, params)

    def search_images(
        self,
        query: str,
        per_page: int = 20,
        page: int = 1,
        image_type: str = "all",
        orientation: str = "all",
        category: str = "",
        order: str = "popular",
    ) -> Dict:
        """
        搜索图片素材

        API 端点：https://pixabay.com/api/

        :param query: 搜索关键词
        :param per_page: 每页结果数（3-200）
        :param page: 页码
        :param image_type: 图片类型：all/photo/illustration/vector
        :param orientation: 朝向：all/horizontal/vertical
        :param category: 分类
        :param order: 排序：popular/latest
        :return: 包含 total、totalHits、hits 的字典
        """
        if not query or not isinstance(query, str):
            raise ValueError("query 不能为空")
        if not (1 <= per_page <= 200):
            raise ValueError(f"per_page 范围 1-200，当前 {per_page}")
        if page < 1:
            raise ValueError(f"page 必须 ≥ 1，当前 {page}")

        self._validate_choice(image_type, VALID_IMAGE_TYPES, "image_type")
        self._validate_choice(orientation, VALID_ORIENTATIONS, "orientation")
        self._validate_choice(order, VALID_ORDER, "order")
        if category and category not in VALID_CATEGORIES:
            raise ValueError(f"category 非法：'{category}'")

        params = self._build_params(
            q=query,
            per_page=per_page,
            page=page,
            image_type=image_type,
            orientation=orientation,
            category=category or None,
            order=order,
        )

        return self._request(PIXABAY_IMAGE_ENDPOINT, params)

    def search_music(
        self,
        query: str,
        per_page: int = 20,
        page: int = 1,
    ) -> Dict:
        """
        搜索音乐素材

        注意：Pixabay 官方未公开音乐 API 文档，此处尝试调用社区已知的
        /api/music/ 端点；若端点不可用，将返回包含提示信息的字典。

        :param query: 搜索关键词
        :param per_page: 每页结果数
        :param page: 页码
        :return: 搜索结果或提示信息
        """
        if not query or not isinstance(query, str):
            raise ValueError("query 不能为空")
        if not (1 <= per_page <= 200):
            raise ValueError(f"per_page 范围 1-200，当前 {per_page}")
        if page < 1:
            raise ValueError(f"page 必须 ≥ 1，当前 {page}")

        params = self._build_params(
            q=query,
            per_page=per_page,
            page=page,
        )

        try:
            return self._request(PIXABAY_MUSIC_ENDPOINT, params)
        except (PixabayNotFoundError, PixabayError) as e:
            # 音乐 API 不公开时给出明确提示
            return {
                "success": False,
                "note": (
                    "Pixabay 官方未公开音乐搜索 API 端点。"
                    "如需搜索音乐，请改用 Jamendo（jamendo_client.py）。"
                    "Pixabay 音乐可通过其网站 https://pixabay.com/music/ 手动下载。"
                ),
                "error": str(e),
                "query": query,
            }

    # -------------------------------------------------------------------------
    # 详情查询
    # -------------------------------------------------------------------------

    def get_video(self, video_id: str) -> Dict:
        """
        获取单个视频信息（通过搜索 id 实现，Pixabay 无独立详情端点）

        :param video_id: 视频 ID
        :return: 视频 hit 字典，未找到则返回空字典
        """
        if not video_id:
            raise ValueError("video_id 不能为空")
        # Pixabay 无独立视频详情端点，使用 id 过滤搜索结果
        result = self.search_videos(query="", per_page=200, page=1)
        for hit in result.get("hits", []):
            if str(hit.get("id")) == str(video_id):
                return hit
        return {}

    def get_image(self, image_id: str) -> Dict:
        """
        获取单个图片信息（通过搜索 id 实现）

        :param image_id: 图片 ID
        :return: 图片 hit 字典
        """
        if not image_id:
            raise ValueError("image_id 不能为空")
        result = self.search_images(query="", per_page=200, page=1)
        for hit in result.get("hits", []):
            if str(hit.get("id")) == str(image_id):
                return hit
        return {}

    # -------------------------------------------------------------------------
    # 下载接口
    # -------------------------------------------------------------------------

    def _download_file(
        self,
        url: str,
        output_path: str,
        expected_min_size: int = 0,
    ) -> Dict:
        """
        下载文件到本地

        :param url: 文件 URL
        :param output_path: 输出路径
        :param expected_min_size: 期望最小字节数（用于校验）
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
                # 确保目录存在
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                total = 0
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                if expected_min_size > 0 and total < expected_min_size:
                    return {
                        "success": False,
                        "error": f"文件过小（{total}B < {expected_min_size}B）",
                        "url": url,
                        "path": output_path,
                    }
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

    def download_video(
        self,
        video_id: str,
        output_dir: Optional[str] = None,
        quality: str = "large",
    ) -> Dict:
        """
        下载指定视频

        :param video_id: 视频 ID
        :param output_dir: 输出目录，默认使用实例配置
        :param quality: 画质：large/medium/small/tiny
        :return: 下载结果字典
        """
        if not video_id:
            raise ValueError("video_id 不能为空")
        valid_qualities = {"large", "medium", "small", "tiny"}
        if quality not in valid_qualities:
            raise ValueError(f"quality 非法：'{quality}'，可选 {sorted(valid_qualities)}")

        hit = self.get_video(video_id)
        if not hit:
            return {
                "success": False,
                "error": f"未找到 video_id={video_id}",
            }

        videos = hit.get("videos", {})
        video_info = videos.get(quality)
        if not video_info:
            # 降级到任意可用画质
            for q in ("large", "medium", "small", "tiny"):
                if videos.get(q):
                    video_info = videos[q]
                    quality = q
                    break
        if not video_info:
            return {"success": False, "error": "视频无可下载文件"}

        url = video_info.get("url")
        if not url:
            return {"success": False, "error": "视频 URL 缺失"}

        # 文件扩展名根据 file_type 推断
        file_type = video_info.get("file_type", "video/mp4")
        ext = "mp4"
        if "webm" in file_type:
            ext = "webm"
        elif "mov" in file_type:
            ext = "mov"

        out_dir = output_dir or self.output_dir
        filename = f"pixabay_video_{video_id}_{quality}.{ext}"
        output_path = os.path.join(out_dir, filename)

        result = self._download_file(url, output_path)
        result["video_id"] = video_id
        result["quality"] = quality
        if result.get("success"):
            result["title"] = hit.get("tags", "")[:100]
            result["author"] = hit.get("user", "")
        return result

    def download_image(
        self,
        image_id: str,
        output_dir: Optional[str] = None,
        quality: str = "largeImageURL",
    ) -> Dict:
        """
        下载指定图片

        :param image_id: 图片 ID
        :param output_dir: 输出目录
        :param quality: 画质字段名：largeImageURL/webformatURL/previewURL
        :return: 下载结果字典
        """
        if not image_id:
            raise ValueError("image_id 不能为空")
        valid_fields = {"largeImageURL", "webformatURL", "previewURL"}
        if quality not in valid_fields:
            raise ValueError(f"quality 非法：'{quality}'，可选 {sorted(valid_fields)}")

        hit = self.get_image(image_id)
        if not hit:
            return {"success": False, "error": f"未找到 image_id={image_id}"}

        url = hit.get(quality)
        if not url:
            # 降级
            for q in ("largeImageURL", "webformatURL", "previewURL"):
                if hit.get(q):
                    url = hit[q]
                    quality = q
                    break
        if not url:
            return {"success": False, "error": "图片 URL 缺失"}

        # 推断扩展名
        ext = "jpg"
        url_lower = url.lower()
        if ".png" in url_lower:
            ext = "png"
        elif ".webp" in url_lower:
            ext = "webp"
        elif ".gif" in url_lower:
            ext = "gif"

        out_dir = output_dir or self.output_dir
        filename = f"pixabay_image_{image_id}_{quality.replace('URL', '')}.{ext}"
        output_path = os.path.join(out_dir, filename)

        result = self._download_file(url, output_path)
        result["image_id"] = image_id
        result["quality"] = quality
        if result.get("success"):
            result["title"] = hit.get("tags", "")[:100]
            result["author"] = hit.get("user", "")
        return result


# =============================================================================
# 统一结果格式化（供 unified_search 使用）
# =============================================================================

def normalize_video_result(raw: Dict) -> Dict:
    """
    将 Pixabay 视频结果归一化为统一格式

    :param raw: 单个 hit
    :return: 统一格式的结果字典
    """
    videos = raw.get("videos", {}) or {}
    large = videos.get("large", {}) or {}
    medium = videos.get("medium", {}) or {}
    return {
        "platform": "pixabay",
        "id": str(raw.get("id", "")),
        "title": raw.get("tags", ""),
        "type": "video",
        "url": large.get("url", "") or medium.get("url", ""),
        "thumbnail": raw.get("previewURL", ""),
        "duration": large.get("duration", 0) or medium.get("duration", 0),
        "width": large.get("width", 0) or medium.get("width", 0),
        "height": large.get("height", 0) or medium.get("height", 0),
        "size": large.get("size", 0),
        "author": raw.get("user", ""),
        "author_url": raw.get("userImageURL", ""),
        "license": "Pixabay License (CC0-like)",
        "page_url": raw.get("pageURL", ""),
        "raw": raw,
    }


def normalize_image_result(raw: Dict) -> Dict:
    """
    将 Pixabay 图片结果归一化为统一格式
    """
    return {
        "platform": "pixabay",
        "id": str(raw.get("id", "")),
        "title": raw.get("tags", ""),
        "type": "image",
        "url": raw.get("largeImageURL", "") or raw.get("webformatURL", ""),
        "thumbnail": raw.get("previewURL", ""),
        "duration": 0,
        "width": raw.get("imageWidth", 0),
        "height": raw.get("imageHeight", 0),
        "size": raw.get("imageSize", 0),
        "author": raw.get("user", ""),
        "author_url": raw.get("userImageURL", ""),
        "license": "Pixabay License (CC0-like)",
        "page_url": raw.get("pageURL", ""),
        "raw": raw,
    }


# =============================================================================
# 命令行入口
# =============================================================================

def _load_api_key() -> str:
    """从模板或环境变量加载 API Key"""
    # 1. 环境变量
    key = os.environ.get("PIXABAY_API_KEY")
    if key and not key.startswith("YOUR_"):
        return key
    # 2. api_keys.json 同目录
    keys_file = Path(__file__).parent / "api_keys.json"
    if keys_file.exists():
        try:
            with open(keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = data.get("pixabay_api_key", "")
            if key and not key.startswith("YOUR_"):
                return key
        except (json.JSONDecodeError, OSError):
            pass
    # 3. 模板文件
    template = Path(__file__).parent / "api_keys_template.json"
    if template.exists():
        try:
            with open(template, "r", encoding="utf-8") as f:
                data = json.load(f)
            key = data.get("pixabay_api_key", "")
            if key and not key.startswith("YOUR_"):
                return key
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def main() -> None:
    """
    CLI 入口

    支持 --json-input 协议：
        python pixabay_client.py --json-input '{"func":"search_videos","params":{...}}'

    无参数时打印帮助信息。
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
                    "error": "未提供 Pixabay API Key，请在请求 params.api_key 或环境变量 PIXABAY_API_KEY 中提供"
                }, ensure_ascii=False))
                return

            client = PixabayClient(api_key=api_key)
            func_name = request.get("func")
            params = request.get("params", {}) or {}

            func_map = {
                "search_videos": client.search_videos,
                "search_images": client.search_images,
                "search_music": client.search_music,
                "get_video": client.get_video,
                "get_image": client.get_image,
                "download_video": client.download_video,
                "download_image": client.download_image,
            }

            if func_name in func_map:
                result = func_map[func_name](**params)
            else:
                result = {
                    "success": False,
                    "error": f"未知函数：{func_name}，支持：{list(func_map.keys())}"
                }

            print(json.dumps(result, ensure_ascii=False, default=str))
        except PixabayAuthError as e:
            print(json.dumps({"success": False, "error": f"鉴权失败：{e}"}, ensure_ascii=False))
        except PixabayRateLimitError as e:
            print(json.dumps({"success": False, "error": f"速率限制：{e}"}, ensure_ascii=False))
        except PixabayError as e:
            print(json.dumps({"success": False, "error": f"Pixabay 错误：{e}"}, ensure_ascii=False))
        except ValueError as e:
            print(json.dumps({"success": False, "error": f"参数错误：{e}"}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": f"未知异常：{e}"}, ensure_ascii=False))
        return

    # 无参数模式：打印使用说明
    print("=" * 70)
    print("Pixabay API 客户端")
    print("=" * 70)
    print("用法：")
    print("  1. JSON 输入模式：")
    print('     python pixabay_client.py --json-input \'{"func":"search_videos","params":{"query":"sunset","per_page":5}}\'')
    print("  2. 管道模式：")
    print('     echo \'{"func":"search_images","params":{"query":"ocean"}}\' | python pixabay_client.py --json-input')
    print()
    print("可用函数：")
    print("  - search_videos(query, per_page, page, video_type, orientation, category, order)")
    print("  - search_images(query, per_page, page, image_type, orientation, category, order)")
    print("  - search_music(query, per_page, page)  # 注：Pixabay 音乐 API 非公开")
    print("  - get_video(video_id)")
    print("  - get_image(image_id)")
    print("  - download_video(video_id, output_dir, quality)")
    print("  - download_image(image_id, output_dir, quality)")
    print()
    print("API Key 来源优先级：")
    print("  1. 请求 params.api_key")
    print("  2. 环境变量 PIXABAY_API_KEY")
    print("  3. 同目录 api_keys.json")
    print("  4. 同目录 api_keys_template.json")
    print()
    print("速率限制：100 requests/hour")
    print("API 文档：https://pixabay.com/api/docs/")


if __name__ == "__main__":
    main()
