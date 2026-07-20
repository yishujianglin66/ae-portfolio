"""
Jamendo 音乐 API 客户端
========================

提供对 Jamendo 免费音乐库的程序化访问能力，支持曲目搜索、详情查询与下载。

API 文档：https://developer.jamendo.com/v3.0
限制：需 Client ID（免费注册），无明确速率限制

主要功能：
    - search_tracks: 按关键词、曲风、情绪、BPM 搜索曲目
    - get_track: 获取单曲信息
    - download_track: 下载音乐文件
    - search_by_mood: 按情绪搜索
    - get_genres: 获取所有曲风列表

使用方式：
    1. CLI 模式：python jamendo_client.py
    2. JSON 输入模式：python jamendo_client.py --json-input '{"func":"search_tracks","params":{...}}'
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

import requests


# =============================================================================
# 常量定义
# =============================================================================

JAMENDO_BASE_URL = "https://api.jamendo.com/v3.0"
JAMENDO_TRACKS_ENDPOINT = f"{JAMENDO_BASE_URL}/tracks"
JAMENDO_TRACKS_FILE_ENDPOINT = f"{JAMENDO_BASE_URL}/tracks/file"
JAMENDO_GENRES_ENDPOINT = f"{JAMENDO_BASE_URL}/genres"
JAMENDO_ALBUMS_ENDPOINT = f"{JAMENDO_BASE_URL}/albums"
JAMENDO_ARTISTS_ENDPOINT = f"{JAMENDO_BASE_URL}/artists"

# 请求超时（秒）
REQUEST_TIMEOUT = 30

# 每页最大结果数
MAX_LIMIT = 200

# 允许的音频格式
VALID_AUDIO_FORMATS = {"mp31", "mp32", "ogg", "flac"}

# 允许的情绪值（参考官方 musicinfo.moodtags）
VALID_MOODS = {
    "happy", "sad", "relaxing", "aggressive",
    "emotional", "dark", "upbeat", "party",
    "calm", "energetic", "melancholic", "optimistic",
    "pensive", "angry", "dreamy", "romantic",
}

# 允许的图片尺寸
VALID_IMAGE_SIZES = {"30", "35", "50", "60", "75", "85", "100", "130", "150", "200", "250", "300", "350", "400", "450", "500", "600"}


# =============================================================================
# 异常定义
# =============================================================================

class JamendoError(Exception):
    """Jamendo 客户端基础异常"""


class JamendoAuthError(JamendoError):
    """Client ID 无效或缺失"""


class JamendoNotFoundError(JamendoError):
    """资源未找到"""


class JamendoAPIError(JamendoError):
    """API 返回业务错误"""


# =============================================================================
# 核心客户端
# =============================================================================

class JamendoClient:
    """
    Jamendo 音乐 API 客户端

    通过 client_id 鉴权，封装曲目搜索、详情查询、下载能力。
    """

    def __init__(self, client_id: str, output_dir: Optional[str] = None):
        """
        初始化客户端

        :param client_id: Jamendo Client ID
        :param output_dir: 默认下载目录
        """
        if not client_id or not isinstance(client_id, str):
            raise JamendoAuthError("Jamendo Client ID 不能为空")
        self.client_id = client_id
        self.output_dir = output_dir or os.getcwd()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AE-Knowledge-Vault/1.0 (Jamendo Client)",
            "Accept": "application/json",
        })

    # -------------------------------------------------------------------------
    # 内部工具方法
    # -------------------------------------------------------------------------

    def _build_params(self, **kwargs) -> Dict[str, str]:
        """构造请求参数，自动附加 client_id"""
        params = {"client_id": self.client_id, "format": "json"}
        for k, v in kwargs.items():
            if v is None:
                continue
            if isinstance(v, bool):
                params[k] = "true" if v else "false"
            elif isinstance(v, (list, tuple)):
                # 多值参数用逗号分隔
                params[k] = ",".join(str(x) for x in v)
            else:
                params[k] = str(v)
        return params

    def _request(
        self,
        url: str,
        params: Optional[Dict] = None,
        method: str = "GET",
    ) -> Dict:
        """
        发起 HTTP 请求并返回 JSON

        :param url: API 端点
        :param params: 查询参数
        :param method: HTTP 方法
        :return: 解析后的 JSON 字典
        """
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            else:
                response = self.session.request(method, url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            raise JamendoError(f"请求超时（{REQUEST_TIMEOUT}s）：{url}")
        except requests.exceptions.ConnectionError as e:
            raise JamendoError(f"网络连接失败：{e}")
        except requests.exceptions.RequestException as e:
            raise JamendoError(f"请求异常：{e}")

        if response.status_code == 401 or response.status_code == 403:
            raise JamendoAuthError("Client ID 无效或无权访问")
        if response.status_code == 404:
            raise JamendoNotFoundError(f"资源未找到：{url}")
        if response.status_code == 429:
            raise JamendoError("触发速率限制（429 Too Many Requests）")
        if response.status_code >= 500:
            raise JamendoError(f"Jamendo 服务异常（HTTP {response.status_code}）")

        try:
            data = response.json()
        except ValueError:
            raise JamendoError(f"响应解析失败（非 JSON）：{response.text[:200]}")

        # Jamendo 错误结构：{"headers": {"error": "...", "code": "..."}, "results": []}
        headers = data.get("headers", {}) or {}
        error_msg = headers.get("error_message") or headers.get("error")
        error_code = headers.get("code") or headers.get("status")
        # status_string 可能为 "failed"
        status_string = headers.get("status_string", "")
        full_status = headers.get("status_full", "")

        # Jamendo 成功状态码：0 或 "success"
        # 失败状态码非 0 或 status_string 为 "failed"
        if error_msg or status_string == "failed" or (error_code not in (None, 0, "0", "success")):
            # 部分响应即使有 error 也包含 results，按业务错误处理
            if not data.get("results") and not data.get("results_count"):
                raise JamendoAPIError(
                    f"Jamendo API 错误：code={error_code}, message={error_msg or full_status or status_string}"
                )

        return data

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
    # 曲目搜索
    # -------------------------------------------------------------------------

    def search_tracks(
        self,
        query: str = "",
        limit: int = 20,
        offset: int = 0,
        genre: str = "",
        mood: str = "",
        bpm_min: int = 0,
        bpm_max: int = 300,
        audioformat: str = "mp32",
        include: str = "musicinfo+licenses",
        imagesize: str = "200",
        order: str = "popularity_total",
    ) -> Dict:
        """
        搜索曲目

        API 端点：GET https://api.jamendo.com/v3.0/tracks

        :param query: 搜索关键词（按曲名/艺术家/专辑名匹配）
        :param limit: 每页结果数（1-200）
        :param offset: 偏移量（用于分页）
        :param genre: 曲风，如 "rock", "pop", "electronic"
        :param mood: 情绪，可选值见 VALID_MOODS
        :param bpm_min: 最小 BPM
        :param bpm_max: 最大 BPM
        :param audioformat: 音频格式：mp31(128k)/mp32(256k)/ogg/flac
        :param include: 附加字段，如 "musicinfo+licenses"
        :param imagesize: 图片尺寸（像素，30-600）
        :param order: 排序字段，默认按总人气降序
        :return: 包含 headers、results 的字典
        """
        if not (1 <= limit <= MAX_LIMIT):
            raise ValueError(f"limit 范围 1-{MAX_LIMIT}，当前 {limit}")
        if offset < 0:
            raise ValueError(f"offset 必须 ≥ 0，当前 {offset}")
        if audioformat not in VALID_AUDIO_FORMATS:
            raise ValueError(f"audioformat 非法：'{audioformat}'，可选 {sorted(VALID_AUDIO_FORMATS)}")
        if mood and mood not in VALID_MOODS:
            raise ValueError(f"mood 非法：'{mood}'，可选 {sorted(VALID_MOODS)}")
        if not (0 <= bpm_min <= bpm_max <= 300):
            raise ValueError(f"BPM 范围非法：min={bpm_min}, max={bpm_max}")

        params = self._build_params(
            limit=limit,
            offset=offset,
            audioformat=audioformat,
            include=include,
            imagesize=imagesize,
            order=order,
        )
        if query:
            params["name"] = query
        if genre:
            params["fuzzydate"] = ""
            params["tags"] = genre
            # 直接使用 genre 参数（Jamendo 支持 genre 过滤）
            params["genre"] = genre
        if mood:
            params["tags"] = mood if not genre else f"{genre},{mood}"
        if bpm_min > 0:
            params["bpm"] = f"{bpm_min}_{bpm_max}"

        return self._request(JAMENDO_TRACKS_ENDPOINT, params)

    def get_track(self, track_id: str, audioformat: str = "mp32") -> Dict:
        """
        获取单曲信息

        :param track_id: 曲目 ID
        :param audioformat: 音频格式
        :return: 包含单曲信息的字典
        """
        if not track_id:
            raise ValueError("track_id 不能为空")
        if audioformat not in VALID_AUDIO_FORMATS:
            raise ValueError(f"audioformat 非法：'{audioformat}'")

        params = self._build_params(
            id=track_id,
            audioformat=audioformat,
            include="musicinfo+licenses+stats",
            imagesize="200",
        )
        result = self._request(JAMENDO_TRACKS_ENDPOINT, params)
        results = result.get("results", []) or []
        if not results:
            raise JamendoNotFoundError(f"未找到 track_id={track_id}")
        # 返回完整响应以保留 headers
        return result

    def search_by_mood(
        self,
        mood: str,
        limit: int = 20,
        offset: int = 0,
        audioformat: str = "mp32",
    ) -> Dict:
        """
        按情绪搜索曲目

        mood 可选值：happy, sad, relaxing, aggressive, emotional, dark, upbeat, party,
                    calm, energetic, melancholic, optimistic, pensive, angry, dreamy, romantic

        :param mood: 情绪关键词
        :param limit: 每页结果数
        :param offset: 偏移量
        :param audioformat: 音频格式
        :return: 搜索结果
        """
        if mood not in VALID_MOODS:
            raise ValueError(f"mood 非法：'{mood}'，可选 {sorted(VALID_MOODS)}")
        return self.search_tracks(
            query="",
            limit=limit,
            offset=offset,
            mood=mood,
            audioformat=audioformat,
        )

    def search_by_genre(
        self,
        genre: str,
        limit: int = 20,
        offset: int = 0,
        audioformat: str = "mp32",
    ) -> Dict:
        """
        按曲风搜索曲目

        :param genre: 曲风，如 "rock", "pop", "electronic", "jazz", "classical"
        :param limit: 每页结果数
        :param offset: 偏移量
        :param audioformat: 音频格式
        :return: 搜索结果
        """
        if not genre:
            raise ValueError("genre 不能为空")
        return self.search_tracks(
            query="",
            limit=limit,
            offset=offset,
            genre=genre,
            audioformat=audioformat,
        )

    def search_by_bpm(
        self,
        bpm_min: int,
        bpm_max: int,
        limit: int = 20,
        offset: int = 0,
        audioformat: str = "mp32",
    ) -> Dict:
        """
        按 BPM 范围搜索曲目

        :param bpm_min: 最小 BPM
        :param bpm_max: 最大 BPM
        :param limit: 每页结果数
        :param offset: 偏移量
        :param audioformat: 音频格式
        :return: 搜索结果
        """
        if not (0 <= bpm_min <= bpm_max <= 300):
            raise ValueError(f"BPM 范围非法：min={bpm_min}, max={bpm_max}")
        return self.search_tracks(
            query="",
            limit=limit,
            offset=offset,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            audioformat=audioformat,
        )

    # -------------------------------------------------------------------------
    # 曲风列表
    # -------------------------------------------------------------------------

    def get_genres(self, limit: int = 100) -> Dict:
        """
        获取所有曲风列表

        API 端点：GET https://api.jamendo.com/v3.0/genres

        :param limit: 返回数量
        :return: 包含 results 的字典，每个元素包含 id、name、idstr
        """
        if not (1 <= limit <= MAX_LIMIT):
            raise ValueError(f"limit 范围 1-{MAX_LIMIT}，当前 {limit}")
        params = self._build_params(limit=limit)
        return self._request(JAMENDO_GENRES_ENDPOINT, params)

    # -------------------------------------------------------------------------
    # 下载接口
    # -------------------------------------------------------------------------

    def download_track(
        self,
        track_id: str,
        output_dir: Optional[str] = None,
        audioformat: str = "mp32",
    ) -> Dict:
        """
        下载音乐文件

        通过获取曲目详情拿到 audio URL，再下载到本地。

        :param track_id: 曲目 ID
        :param output_dir: 输出目录，默认使用实例配置
        :param audioformat: 音频格式：mp31(128k)/mp32(256k)/ogg/flac
        :return: 下载结果字典
        """
        if not track_id:
            raise ValueError("track_id 不能为空")
        if audioformat not in VALID_AUDIO_FORMATS:
            raise ValueError(f"audioformat 非法：'{audioformat}'，可选 {sorted(VALID_AUDIO_FORMATS)}")

        # 获取曲目详情（包含 audio URL）
        try:
            detail = self.get_track(track_id, audioformat=audioformat)
        except JamendoNotFoundError:
            return {"success": False, "error": f"未找到 track_id={track_id}"}

        results = detail.get("results", []) or []
        if not results:
            return {"success": False, "error": f"未找到 track_id={track_id}"}

        track = results[0]
        audio_url = track.get("audio")
        if not audio_url:
            return {"success": False, "error": "曲目无 audio URL"}

        # 文件扩展名映射
        ext_map = {"mp31": "mp3", "mp32": "mp3", "ogg": "ogg", "flac": "flac"}
        ext = ext_map.get(audioformat, "mp3")

        # 文件名：艺术家 - 曲目名
        artist = track.get("artist_name", "unknown")
        name = track.get("name", "unknown")
        # 清理非法文件名字符
        safe_artist = "".join(c for c in artist if c not in r'\/:*?"<>|')[:50]
        safe_name = "".join(c for c in name if c not in r'\/:*?"<>|')[:80]
        filename = f"jamendo_{track_id}_{safe_artist} - {safe_name}.{ext}"

        out_dir = output_dir or self.output_dir
        output_path = os.path.join(out_dir, filename)

        result = self._download_file(audio_url, output_path)
        result["track_id"] = track_id
        result["audioformat"] = audioformat
        if result.get("success"):
            result["title"] = name
            result["artist"] = artist
            result["album"] = track.get("album_name", "")
            result["duration"] = track.get("duration", 0)
            result["bpm"] = track.get("bpm", -1)
            result["license"] = track.get("license_ccurl", "")
        return result


# =============================================================================
# 统一结果格式化（供 unified_search 使用）
# =============================================================================

def normalize_track_result(raw: Dict) -> Dict:
    """
    将 Jamendo 曲目结果归一化为统一格式

    :param raw: 单个 track 对象
    :return: 统一格式的结果字典
    """
    musicinfo = raw.get("musicinfo", {}) or {}
    tags = musicinfo.get("tags", {}) or {}
    return {
        "platform": "jamendo",
        "id": str(raw.get("id", "")),
        "title": raw.get("name", ""),
        "type": "music",
        "url": raw.get("audio", ""),
        "thumbnail": raw.get("image", "") or raw.get("album_image", ""),
        "duration": raw.get("duration", 0),
        "width": 0,
        "height": 0,
        "size": 0,
        "author": raw.get("artist_name", ""),
        "author_url": raw.get("artist_idstr", ""),
        "album": raw.get("album_name", ""),
        "bpm": raw.get("bpm", -1),
        "genre": tags.get("genres", []) if isinstance(tags, dict) else [],
        "instruments": tags.get("instruments", []) if isinstance(tags, dict) else [],
        "vocal": tags.get("vocal", "") if isinstance(tags, dict) else (musicinfo.get("vocal") or ""),
        "license": raw.get("license_ccurl", "") or raw.get("license", ""),
        "page_url": raw.get("shareurl", ""),
        "raw": raw,
    }


# =============================================================================
# 命令行入口
# =============================================================================

def _load_client_id() -> str:
    """从环境变量或配置文件加载 Client ID"""
    cid = os.environ.get("JAMENDO_CLIENT_ID")
    if cid and not cid.startswith("YOUR_"):
        return cid
    keys_file = Path(__file__).parent / "api_keys.json"
    if keys_file.exists():
        try:
            with open(keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cid = data.get("jamendo_client_id", "")
            if cid and not cid.startswith("YOUR_"):
                return cid
        except (json.JSONDecodeError, OSError):
            pass
    template = Path(__file__).parent / "api_keys_template.json"
    if template.exists():
        try:
            with open(template, "r", encoding="utf-8") as f:
                data = json.load(f)
            cid = data.get("jamendo_client_id", "")
            if cid and not cid.startswith("YOUR_"):
                return cid
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def main() -> None:
    """
    CLI 入口

    支持 --json-input 协议：
        python jamendo_client.py --json-input '{"func":"search_tracks","params":{...}}'
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()

            request = json.loads(input_data) if input_data else {}
            client_id = request.get("client_id") or _load_client_id()

            if not client_id:
                print(json.dumps({
                    "success": False,
                    "error": "未提供 Jamendo Client ID，请在请求 params.client_id 或环境变量 JAMENDO_CLIENT_ID 中提供"
                }, ensure_ascii=False))
                return

            client = JamendoClient(client_id=client_id)
            func_name = request.get("func")
            params = request.get("params", {}) or {}

            func_map = {
                "search_tracks": client.search_tracks,
                "search_by_mood": client.search_by_mood,
                "search_by_genre": client.search_by_genre,
                "search_by_bpm": client.search_by_bpm,
                "get_track": client.get_track,
                "get_genres": client.get_genres,
                "download_track": client.download_track,
            }

            if func_name in func_map:
                result = func_map[func_name](**params)
            else:
                result = {
                    "success": False,
                    "error": f"未知函数：{func_name}，支持：{list(func_map.keys())}"
                }

            print(json.dumps(result, ensure_ascii=False, default=str))
        except JamendoAuthError as e:
            print(json.dumps({"success": False, "error": f"鉴权失败：{e}"}, ensure_ascii=False))
        except JamendoNotFoundError as e:
            print(json.dumps({"success": False, "error": f"资源未找到：{e}"}, ensure_ascii=False))
        except JamendoAPIError as e:
            print(json.dumps({"success": False, "error": f"API 错误：{e}"}, ensure_ascii=False))
        except JamendoError as e:
            print(json.dumps({"success": False, "error": f"Jamendo 错误：{e}"}, ensure_ascii=False))
        except ValueError as e:
            print(json.dumps({"success": False, "error": f"参数错误：{e}"}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": f"未知异常：{e}"}, ensure_ascii=False))
        return

    # 无参数模式
    print("=" * 70)
    print("Jamendo 音乐 API 客户端")
    print("=" * 70)
    print("用法：")
    print("  1. JSON 输入模式：")
    print('     python jamendo_client.py --json-input \'{"func":"search_tracks","params":{"query":"chill","limit":5}}\'')
    print("  2. 管道模式：")
    print('     echo \'{"func":"search_by_mood","params":{"mood":"happy"}}\' | python jamendo_client.py --json-input')
    print()
    print("可用函数：")
    print("  - search_tracks(query, limit, offset, genre, mood, bpm_min, bpm_max, audioformat)")
    print("  - search_by_mood(mood, limit, offset, audioformat)")
    print("  - search_by_genre(genre, limit, offset, audioformat)")
    print("  - search_by_bpm(bpm_min, bpm_max, limit, offset, audioformat)")
    print("  - get_track(track_id, audioformat)")
    print("  - get_genres(limit)")
    print("  - download_track(track_id, output_dir, audioformat)")
    print()
    print("音频格式：")
    print("  - mp31: 128kbps MP3")
    print("  - mp32: 256kbps MP3（默认）")
    print("  - ogg:  Ogg Vorbis")
    print("  - flac: FLAC 无损")
    print()
    print("情绪可选值：")
    print(f"  {', '.join(sorted(VALID_MOODS))}")
    print()
    print("Client ID 来源优先级：")
    print("  1. 请求 params.client_id")
    print("  2. 环境变量 JAMENDO_CLIENT_ID")
    print("  3. 同目录 api_keys.json")
    print("  4. 同目录 api_keys_template.json")
    print()
    print("API 文档：https://developer.jamendo.com/v3.0")


if __name__ == "__main__":
    main()
