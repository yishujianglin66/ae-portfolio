"""
统一素材搜索入口
=================

跨平台素材搜索与下载，聚合 Pixabay、Pexels、Jamendo 三大免费素材源。

主要功能：
    - search_all: 跨平台搜索（all/videos/images/music）
    - search_videos: 跨平台视频搜索
    - search_images: 跨平台图片搜索
    - search_music: 跨平台音乐搜索
    - download_media: 统一下载接口

设计要点：
    - 使用 concurrent.futures.ThreadPoolExecutor 并行调用多个 API
    - 单平台失败不影响其他平台结果（容错降级）
    - 基于标题相似度的结果去重
    - 统一返回格式，便于上层消费

使用方式：
    1. CLI 模式：python unified_search.py
    2. JSON 输入模式：python unified_search.py --json-input '{"func":"search_all","params":{...}}'

统一返回格式：
    {
      "success": true,
      "results": [
        {
          "platform": "pixabay",
          "id": "12345",
          "title": "...",
          "type": "video",
          "url": "https://...",
          "thumbnail": "https://...",
          "duration": 30,
          "width": 1920,
          "height": 1080,
          "author": "...",
          "license": "..."
        }
      ],
      "total": 30
    }
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from difflib import SequenceMatcher

# 将本文件所在目录加入 sys.path，便于导入同级模块
_THIS_DIR = Path(__file__).parent.resolve()
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# 导入三个客户端
import pixabay_client
import pexels_client
import jamendo_client
from pixabay_client import PixabayClient, PixabayError
from pexels_client import PexelsClient, PexelsError
from jamendo_client import JamendoClient, JamendoError


# =============================================================================
# 常量定义
# =============================================================================

# 并发线程数
MAX_WORKERS = 3

# 单个平台请求超时（秒）
PER_PLATFORM_TIMEOUT = 60

# 标题相似度阈值（高于此值视为重复）
TITLE_SIMILARITY_THRESHOLD = 0.85

# 支持的平台
SUPPORTED_PLATFORMS = ("pixabay", "pexels", "jamendo")

# 支持的媒体类型
SUPPORTED_MEDIA_TYPES = ("all", "videos", "images", "music")


# =============================================================================
# 异常定义
# =============================================================================

class UnifiedSearchError(Exception):
    """统一搜索基础异常"""


class InvalidPlatformError(UnifiedSearchError):
    """不支持的平台"""


class MissingAPIKeyError(UnifiedSearchError):
    """缺少 API Key"""


# =============================================================================
# 工具函数
# =============================================================================

def _load_api_keys() -> Dict[str, str]:
    """
    从环境变量或配置文件加载所有 API Key

    :return: 包含 pixabay_api_key、pexels_api_key、jamendo_client_id 的字典
    """
    keys = {
        "pixabay_api_key": os.environ.get("PIXABAY_API_KEY", ""),
        "pexels_api_key": os.environ.get("PEXELS_API_KEY", ""),
        "jamendo_client_id": os.environ.get("JAMENDO_CLIENT_ID", ""),
    }

    # 配置文件加载（api_keys.json 优先于模板）
    for config_name in ("api_keys.json", "api_keys_template.json"):
        config_path = _THIS_DIR / config_name
        if not config_path.exists():
            continue
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in keys:
                v = data.get(k, "")
                # 仅当环境变量未设置或配置值非占位符时覆盖
                if not keys[k] and v and not str(v).startswith("YOUR_"):
                    keys[k] = v
        except (json.JSONDecodeError, OSError):
            continue

    return keys


def _normalize_title_similarity(a: str, b: str) -> float:
    """
    计算两个标题的相似度（0-1）

    使用 difflib.SequenceMatcher，先做小写化与去标点处理。

    :param a: 标题 A
    :param b: 标题 B
    :return: 相似度，0-1
    """
    if not a or not b:
        return 0.0
    # 简单清洗：小写、去除常见标点
    clean_a = "".join(c.lower() for c in a if c.isalnum() or c.isspace()).strip()
    clean_b = "".join(c.lower() for c in b if c.isalnum() or c.isspace()).strip()
    if not clean_a or not clean_b:
        return 0.0
    if clean_a == clean_b:
        return 1.0
    return SequenceMatcher(None, clean_a, clean_b).ratio()


def _dedup_results(results: List[Dict], threshold: float = TITLE_SIMILARITY_THRESHOLD) -> List[Dict]:
    """
    基于标题相似度去重

    保留首次出现的条目，后续相似度高于阈值者视为重复。

    :param results: 待去重结果列表
    :param threshold: 相似度阈值
    :return: 去重后的列表
    """
    deduped: List[Dict] = []
    seen_titles: List[str] = []
    for item in results:
        title = (item.get("title") or "").strip()
        is_dup = False
        if title:
            for seen in seen_titles:
                clean_title = "".join(c.lower() for c in title if c.isalnum() or c.isspace()).strip()
                clean_seen = "".join(c.lower() for c in seen if c.isalnum() or c.isspace()).strip()
                if len(clean_title) < 8 or len(clean_seen) < 8:
                    if clean_title == clean_seen:
                        is_dup = True
                        break
                elif _normalize_title_similarity(title, seen) >= threshold:
                    is_dup = True
                    break
        if not is_dup:
            deduped.append(item)
            if title:
                seen_titles.append(title)
    return deduped


def _safe_call(
    fn: Callable,
    *args,
    timeout: float = PER_PLATFORM_TIMEOUT,
    **kwargs,
) -> Dict:
    """
    安全调用单个平台函数，捕获所有异常

    :param fn: 可调用对象
    :param timeout: 超时秒数
    :return: 包含 success 与 platform 的结果字典
    """
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn, *args, **kwargs)
    try:
        result = future.result(timeout=timeout)
        return result
    except FuturesTimeoutError:
        future.cancel()
        return {"success": False, "error": f"调用超时（{timeout}s）"}
    except (PixabayError, PexelsError, JamendoError) as e:
        return {"success": False, "error": f"平台错误：{e}"}
    except Exception as e:
        return {"success": False, "error": f"未知异常：{e}"}
    finally:
        # 不阻塞等待：with 语句退出会调用 shutdown(wait=True) 阻塞至线程结束，
        # 使 timeout 失效。此处用 wait=False 立即返回，避免拖住调用方。
        pool.shutdown(wait=False)


# =============================================================================
# 平台搜索封装
# =============================================================================

def _search_pixabay(
    api_key: str,
    query: str,
    media_type: str,
    per_page: int,
) -> Dict:
    """
    Pixabay 平台搜索封装

    :param api_key: Pixabay API Key
    :param query: 关键词
    :param media_type: all/videos/images/music
    :param per_page: 每页数量
    :return: 包含 platform、items、error 的字典
    """
    if not api_key:
        return {"platform": "pixabay", "items": [], "error": "缺少 API Key"}
    client = PixabayClient(api_key=api_key)
    items: List[Dict] = []
    error = ""
    try:
        if media_type in ("videos", "all"):
            raw = client.search_videos(query=query, per_page=per_page)
            for hit in raw.get("hits", []) or []:
                items.append(pixabay_client.normalize_video_result(hit))
        if media_type in ("images", "all"):
            raw = client.search_images(query=query, per_page=per_page)
            for hit in raw.get("hits", []) or []:
                items.append(pixabay_client.normalize_image_result(hit))
        if media_type == "music":
            raw = client.search_music(query=query, per_page=per_page)
            # 音乐 API 不可用时不报错
            if not raw.get("success", True):
                error = raw.get("note", "Pixabay 音乐 API 不可用")
    except PixabayError as e:
        error = str(e)
    except Exception as e:
        error = f"异常：{e}"
    return {"platform": "pixabay", "items": items, "error": error}


def _search_pexels(
    api_key: str,
    query: str,
    media_type: str,
    per_page: int,
) -> Dict:
    """
    Pexels 平台搜索封装
    """
    if not api_key:
        return {"platform": "pexels", "items": [], "error": "缺少 API Key"}
    client = PexelsClient(api_key=api_key)
    items: List[Dict] = []
    error = ""
    try:
        if media_type in ("videos", "all"):
            raw = client.search_videos(query=query, per_page=min(per_page, 80))
            for v in raw.get("videos", []) or []:
                items.append(pexels_client.normalize_video_result(v))
        if media_type in ("images", "all"):
            raw = client.search_photos(query=query, per_page=min(per_page, 80))
            for p in raw.get("photos", []) or []:
                items.append(pexels_client.normalize_photo_result(p))
        if media_type == "music":
            error = "Pexels 不支持音乐搜索"
    except PexelsError as e:
        error = str(e)
    except Exception as e:
        error = f"异常：{e}"
    return {"platform": "pexels", "items": items, "error": error}


def _search_jamendo(
    client_id: str,
    query: str,
    media_type: str,
    per_page: int,
) -> Dict:
    """
    Jamendo 平台搜索封装（仅音乐）
    """
    if not client_id:
        return {"platform": "jamendo", "items": [], "error": "缺少 Client ID"}
    # Jamendo 仅支持音乐
    if media_type not in ("music", "all"):
        return {"platform": "jamendo", "items": [], "error": "Jamendo 仅支持音乐搜索"}
    client = JamendoClient(client_id=client_id)
    items: List[Dict] = []
    error = ""
    try:
        raw = client.search_tracks(query=query, limit=min(per_page, 200))
        for t in raw.get("results", []) or []:
            items.append(jamendo_client.normalize_track_result(t))
    except JamendoError as e:
        error = str(e)
    except Exception as e:
        error = f"异常：{e}"
    return {"platform": "jamendo", "items": items, "error": error}


# =============================================================================
# 统一搜索接口
# =============================================================================

class UnifiedSearch:
    """
    跨平台统一搜索引擎

    通过 ThreadPoolExecutor 并行调用各平台 API，结果聚合后去重。
    单平台失败不影响其他平台结果。
    """

    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """
        初始化

        :param api_keys: 包含 pixabay_api_key、pexels_api_key、jamendo_client_id 的字典；
                         为 None 时自动从环境变量与配置文件加载
        """
        self.api_keys = api_keys if api_keys is not None else _load_api_keys()

    def search_all(
        self,
        query: str,
        media_type: str = "all",
        per_page: int = 10,
    ) -> Dict:
        """
        跨平台搜索

        :param query: 搜索关键词
        :param media_type: 媒体类型 all/videos/images/music
        :param per_page: 每个平台每个类型返回的最大数量
        :return: 统一格式结果字典
        """
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise ValueError(f"media_type 非法：'{media_type}'，可选 {list(SUPPORTED_MEDIA_TYPES)}")
        if not query or not isinstance(query, str):
            raise ValueError("query 不能为空")
        if not (1 <= per_page <= 200):
            raise ValueError(f"per_page 范围 1-200，当前 {per_page}")

        # 构造任务列表
        tasks: Dict[str, Callable[[], Dict]] = {}
        if media_type in ("videos", "images", "all"):
            if self.api_keys.get("pixabay_api_key"):
                tasks["pixabay"] = lambda: _search_pixabay(
                    self.api_keys["pixabay_api_key"], query, media_type, per_page
                )
            if self.api_keys.get("pexels_api_key"):
                tasks["pexels"] = lambda: _search_pexels(
                    self.api_keys["pexels_api_key"], query, media_type, per_page
                )
        if media_type in ("music", "all"):
            if self.api_keys.get("jamendo_client_id"):
                tasks["jamendo"] = lambda: _search_jamendo(
                    self.api_keys["jamendo_client_id"], query, media_type, per_page
                )

        if not tasks:
            return {
                "success": False,
                "error": "未配置任何可用的 API Key",
                "configured_platforms": [],
                "results": [],
                "total": 0,
            }

        # 并行执行
        results: List[Dict] = []
        errors: Dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(tasks))) as pool:
            future_map = {pool.submit(_safe_call, fn): name for name, fn in tasks.items()}
            for future in as_completed(future_map):
                platform_name = future_map[future]
                try:
                    platform_result = future.result()
                except Exception as e:
                    errors[platform_name] = f"任务异常：{e}"
                    continue
                # _safe_call 已经捕获了内部异常
                if "items" in platform_result:
                    if platform_result.get("error"):
                        errors[platform_name] = platform_result["error"]
                    results.extend(platform_result.get("items", []))
                elif not platform_result.get("success", True):
                    errors[platform_name] = platform_result.get("error", "未知错误")

        # 去重
        deduped = _dedup_results(results)

        return {
            "success": True,
            "query": query,
            "media_type": media_type,
            "results": deduped,
            "total": len(deduped),
            "platforms_searched": list(tasks.keys()),
            "platforms_with_errors": errors,
            "raw_count_before_dedup": len(results),
        }

    def search_videos(self, query: str, per_page: int = 10) -> Dict:
        """
        跨平台视频搜索

        覆盖 Pixabay 与 Pexels，Jamendo 不参与。

        :param query: 关键词
        :param per_page: 每平台返回数量
        :return: 统一格式结果
        """
        return self.search_all(query, media_type="videos", per_page=per_page)

    def search_images(self, query: str, per_page: int = 10) -> Dict:
        """
        跨平台图片搜索

        覆盖 Pixabay 与 Pexels。

        :param query: 关键词
        :param per_page: 每平台返回数量
        :return: 统一格式结果
        """
        return self.search_all(query, media_type="images", per_page=per_page)

    def search_music(self, query: str, per_page: int = 10) -> Dict:
        """
        跨平台音乐搜索

        覆盖 Jamendo（Pixabay 音乐 API 非公开）。

        :param query: 关键词
        :param per_page: 每平台返回数量
        :return: 统一格式结果
        """
        return self.search_all(query, media_type="music", per_page=per_page)

    def download_media(
        self,
        platform: str,
        media_id: str,
        output_dir: str,
        quality: str = "hd",
    ) -> Dict:
        """
        统一下载接口

        :param platform: 平台名：pixabay/pexels/jamendo
        :param media_id: 媒体 ID
        :param output_dir: 输出目录
        :param quality: 画质/音质偏好（视平台含义不同）
        :return: 下载结果字典
        """
        if platform not in SUPPORTED_PLATFORMS:
            raise InvalidPlatformError(
                f"不支持的平台：'{platform}'，可选 {list(SUPPORTED_PLATFORMS)}"
            )
        if not media_id:
            raise ValueError("media_id 不能为空")
        if not output_dir:
            raise ValueError("output_dir 不能为空")
        os.makedirs(output_dir, exist_ok=True)

        if platform == "pixabay":
            api_key = self.api_keys.get("pixabay_api_key")
            if not api_key:
                raise MissingAPIKeyError("缺少 Pixabay API Key")
            client = PixabayClient(api_key=api_key, output_dir=output_dir)
            # 视频与图片分别尝试
            video_result = _safe_call(
                client.download_video,
                video_id=media_id,
                output_dir=output_dir,
                quality=quality if quality in ("large", "medium", "small", "tiny") else "large",
            )
            if video_result.get("success"):
                return video_result
            image_result = _safe_call(
                client.download_image,
                image_id=media_id,
                output_dir=output_dir,
                quality=quality if quality in ("largeImageURL", "webformatURL", "previewURL") else "largeImageURL",
            )
            return image_result

        if platform == "pexels":
            api_key = self.api_keys.get("pexels_api_key")
            if not api_key:
                raise MissingAPIKeyError("缺少 Pexels API Key")
            client = PexelsClient(api_key=api_key, output_dir=output_dir)
            return _safe_call(
                client.download_video,
                video_id=media_id,
                output_dir=output_dir,
                quality=quality if quality in ("hd", "sd", "uhd") else "hd",
            )

        if platform == "jamendo":
            client_id = self.api_keys.get("jamendo_client_id")
            if not client_id:
                raise MissingAPIKeyError("缺少 Jamendo Client ID")
            client = JamendoClient(client_id=client_id, output_dir=output_dir)
            return _safe_call(
                client.download_track,
                track_id=media_id,
                output_dir=output_dir,
                audioformat=quality if quality in ("mp31", "mp32", "ogg", "flac") else "mp32",
            )

        # 不可达
        return {"success": False, "error": f"平台 {platform} 未实现"}


# =============================================================================
# 便捷函数
# =============================================================================

def search_all(api_keys: Dict[str, str], query: str, media_type: str = "all", per_page: int = 10) -> Dict:
    """
    便捷函数：跨平台搜索（一次性调用）

    :param api_keys: API Key 字典
    :param query: 关键词
    :param media_type: 媒体类型
    :param per_page: 每平台返回数量
    :return: 统一格式结果
    """
    engine = UnifiedSearch(api_keys=api_keys)
    return engine.search_all(query=query, media_type=media_type, per_page=per_page)


def search_videos(api_keys: Dict[str, str], query: str, per_page: int = 10) -> Dict:
    """便捷函数：跨平台视频搜索"""
    engine = UnifiedSearch(api_keys=api_keys)
    return engine.search_videos(query=query, per_page=per_page)


def search_music(api_keys: Dict[str, str], query: str, per_page: int = 10) -> Dict:
    """便捷函数：跨平台音乐搜索"""
    engine = UnifiedSearch(api_keys=api_keys)
    return engine.search_music(query=query, per_page=per_page)


def download_media(
    api_keys: Dict[str, str],
    platform: str,
    media_id: str,
    output_dir: str,
    quality: str = "hd",
) -> Dict:
    """
    便捷函数：统一下载

    :param api_keys: API Key 字典
    :param platform: 平台名
    :param media_id: 媒体 ID
    :param output_dir: 输出目录
    :param quality: 画质/音质
    :return: 下载结果
    """
    engine = UnifiedSearch(api_keys=api_keys)
    return engine.download_media(
        platform=platform,
        media_id=media_id,
        output_dir=output_dir,
        quality=quality,
    )


# =============================================================================
# 命令行入口
# =============================================================================

def main() -> None:
    """
    CLI 入口

    支持 --json-input 协议：
        python unified_search.py --json-input '{"func":"search_all","params":{"query":"sunset"}}'
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()

            request = json.loads(input_data) if input_data else {}

            # API Key 加载优先级：请求中显式传入 > 环境变量 > 配置文件
            api_keys = _load_api_keys()
            req_keys = request.get("api_keys") or {}
            if isinstance(req_keys, dict):
                for k, v in req_keys.items():
                    if v and not str(v).startswith("YOUR_"):
                        api_keys[k] = v

            engine = UnifiedSearch(api_keys=api_keys)
            func_name = request.get("func")
            params = request.get("params", {}) or {}

            func_map = {
                "search_all": engine.search_all,
                "search_videos": engine.search_videos,
                "search_images": engine.search_images,
                "search_music": engine.search_music,
                "download_media": engine.download_media,
                # 便捷函数（不依赖 engine 实例，但 API Keys 一致）
                "get_genres": None,  # 占位，下方特殊处理
            }

            if func_name == "get_genres":
                # Jamendo 曲风列表
                cid = api_keys.get("jamendo_client_id")
                if not cid:
                    result = {"success": False, "error": "缺少 Jamendo Client ID"}
                else:
                    client = JamendoClient(client_id=cid)
                    result = _safe_call(client.get_genres)
                    if not isinstance(result, dict):
                        result = {"success": False, "error": str(result)}
            elif func_name in func_map and func_map[func_name] is not None:
                result = func_map[func_name](**params)
            else:
                result = {
                    "success": False,
                    "error": f"未知函数：{func_name}，支持：{[k for k, v in func_map.items() if v is not None or k == 'get_genres']}"
                }

            print(json.dumps(result, ensure_ascii=False, default=str))
        except InvalidPlatformError as e:
            print(json.dumps({"success": False, "error": f"平台错误：{e}"}, ensure_ascii=False))
        except MissingAPIKeyError as e:
            print(json.dumps({"success": False, "error": f"缺少 API Key：{e}"}, ensure_ascii=False))
        except UnifiedSearchError as e:
            print(json.dumps({"success": False, "error": f"统一搜索错误：{e}"}, ensure_ascii=False))
        except ValueError as e:
            print(json.dumps({"success": False, "error": f"参数错误：{e}"}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": f"未知异常：{e}"}, ensure_ascii=False))
        return

    # 无参数模式
    print("=" * 70)
    print("统一素材搜索入口（Pixabay + Pexels + Jamendo）")
    print("=" * 70)
    print("用法：")
    print("  1. JSON 输入模式：")
    print('     python unified_search.py --json-input \'{"func":"search_all","params":{"query":"sunset","media_type":"all","per_page":5}}\'')
    print("  2. 管道模式：")
    print('     echo \'{"func":"search_videos","params":{"query":"ocean"}}\' | python unified_search.py --json-input')
    print()
    print("可用函数：")
    print("  - search_all(query, media_type, per_page)")
    print("  - search_videos(query, per_page)")
    print("  - search_images(query, per_page)")
    print("  - search_music(query, per_page)")
    print("  - download_media(platform, media_id, output_dir, quality)")
    print("  - get_genres()  # Jamendo 曲风列表")
    print()
    print("media_type 取值：all / videos / images / music")
    print("platform 取值：pixabay / pexels / jamendo")
    print()
    print("统一返回格式：")
    print("  {")
    print("    \"success\": true,")
    print("    \"results\": [{ platform, id, title, type, url, thumbnail, ... }],")
    print("    \"total\": 30")
    print("  }")
    print()
    print("API Key 来源优先级：")
    print("  1. 请求 params.api_keys（对象，可覆盖单个 key）")
    print("  2. 环境变量 PIXABAY_API_KEY / PEXELS_API_KEY / JAMENDO_CLIENT_ID")
    print("  3. 同目录 api_keys.json")
    print("  4. 同目录 api_keys_template.json")
    print()
    print("特性：")
    print(f"  - 并行调用（ThreadPoolExecutor, max_workers={MAX_WORKERS}）")
    print(f"  - 标题相似度去重（阈值 {TITLE_SIMILARITY_THRESHOLD}）")
    print("  - 单平台失败不影响其他平台")


if __name__ == "__main__":
    main()
