"""
MaterialSearcher - 多平台素材搜索下载器
=====================================

工作流:
1. 从用户需求提取搜索关键词
2. 多平台并行搜索 (蜜柑计划 → 人人电影网 → B站/抖音URL → 本地库)
3. 自动调用 aria2 下载素材 (磁力链接/HTTP)
4. 质量筛选 (分辨率/时长/帧率过滤)
5. 智能裁剪 (按剧本需要的片段时长截取)
6. 不足时调用 AI 生成补充
7. 返回合格素材列表

优先级 (国内直连，无需代理):
- P0: ARK即梦 AI生成 (图片/视频) - 国内直连
- P1: 蜜柑计划 动漫资源 - 国内直连
- P1: 人人电影网 影视资源 - 国内直连
- P2: 用户提供的URL (B站/抖音/YouTube) - yt-dlp下载
- P3: 本地素材库复用
- P4: AI生成补充 (当真实素材不足时)
"""

import os
import sys
import json
import time
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output_director" / "materials"


# ── 加载 .env.doubao 中的 API Key 到环境变量 ──
def _load_env_file():
    env_path = PROJECT_ROOT / ".env.doubao"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k and v and k not in os.environ:
                    os.environ[k] = v

_load_env_file()


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  关键词提取器
# ================================================================
class KeywordExtractor:
    """从用户描述中提取搜索关键词"""

    def extract(self, user_prompt: str) -> List[str]:
        """
        提取搜索关键词列表。
        返回多个关键词用于不同平台搜索。
        """
        prompt = user_prompt.strip()
        keywords = []

        # 1. 直接使用完整描述 (Pexels/Pixabay 支持自然语言搜索)
        keywords.append(prompt)

        # 2. 提取核心名词短语
        import re
        # 去掉时间、风格描述，保留主体
        cleaned = re.sub(r"[,，]\s*(\d+秒|\d+s|竖屏|横屏|高清|4K|电影感|高燃|混剪)", "", prompt)
        cleaned = cleaned.strip()
        if cleaned and cleaned != prompt:
            keywords.append(cleaned)

        # 3. 生成英文关键词 (Pexels/Pixabay 是英文搜索)
        # 简单映射：如果是中文，尝试提取英文关键词
        english_keywords = self._to_english_keywords(prompt)
        if english_keywords:
            keywords.extend(english_keywords)

        # 去重
        seen = set()
        unique = []
        for k in keywords:
            if k and k.lower() not in seen:
                seen.add(k.lower())
                unique.append(k)

        return unique[:5]  # 最多5个关键词

    def _to_english_keywords(self, prompt: str) -> List[str]:
        """简单中文→英文关键词映射 (可扩展)"""
        mappings = {
            "利威尔": "Levi Ackerman attack on titan",
            "冰海战记": "Vinland Saga viking battle",
            "高燃": "epic intense battle",
            "混剪": "montage edit",
            "电影感": "cinematic film",
            "古风": "ancient Chinese traditional",
            "赛博朋克": "cyberpunk neon city",
            "自然": "nature landscape",
            "城市": "city urban",
            "科技": "technology futuristic",
            "美食": "food cooking",
            "旅行": "travel adventure",
            "宠物": "pet animal cute",
            "运动": "sports action",
            "音乐": "music concert",
            "舞蹈": "dance performance",
        }
        results = []
        for cn, en in mappings.items():
            if cn in prompt:
                results.append(en)
        return results


# ================================================================
#  素材下载器基类
# ================================================================
class BaseSourceAdapter:
    """素材源适配器基类"""

    name: str = ""
    priority: int = 0  # 越大优先级越高

    def is_available(self) -> bool:
        return True

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        raise NotImplementedError


# ================================================================
#  Pexels 适配器 (免费正版素材)
# ================================================================
class PexelsAdapter(BaseSourceAdapter):
    """Pexels 免费正版视频素材 (支持代理)"""

    name = "Pexels"
    priority = 100  # 最高优先级

    def is_available(self) -> bool:
        return bool(os.environ.get("PEXELS_API_KEY"))

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        api_key = os.environ.get("PEXELS_API_KEY")
        if not api_key:
            return []

        try:
            import urllib.request
            import urllib.parse

            encoded_query = urllib.parse.quote(query)
            url = f"https://api.pexels.com/videos/search?query={encoded_query}&per_page={max_results}&orientation=all"

            headers = {"Authorization": api_key}
            req = urllib.request.Request(url, headers=headers)

            opener = _get_proxy_opener()
            with opener.open(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = []
            videos = data.get("videos", [])
            log(f"  Pexels 找到 {len(videos)} 个视频: '{query[:30]}...'")

            for vid in videos[:max_results]:
                video_files = vid.get("video_files", [])
                # 选择质量最高的 MP4
                best_file = None
                for vf in video_files:
                    if vf.get("file_type") == "video/mp4":
                        if not best_file or vf.get("width", 0) > best_file.get("width", 0):
                            best_file = vf

                if not best_file:
                    continue

                video_url = best_file.get("link")
                if not video_url:
                    continue

                # 下载
                filename = f"pexels_{vid['id']}.mp4"
                filepath = output_dir / filename

                try:
                    _download_with_proxy(video_url, str(filepath))
                    results.append({
                        "success": True,
                        "path": str(filepath),
                        "name": filename,
                        "source": "Pexels",
                        "url": video_url,
                        "width": best_file.get("width", 0),
                        "height": best_file.get("height", 0),
                        "duration": vid.get("duration", 0),
                        "query": query,
                    })
                    log(f"    下载: {filename} ({best_file.get('width',0)}x{best_file.get('height',0)})")
                except Exception as e:
                    log(f"    下载失败: {e}", "WARN")

            return results

        except Exception as e:
            log(f"  Pexels 搜索失败: {e}", "WARN")
            return []


# ================================================================
#  代理配置辅助
# ================================================================
def _get_proxy_opener():
    """根据环境变量创建带代理的 URL opener (国内访问 Pixabay/Pexels 需要)"""
    import urllib.request
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("ALL_PROXY")
    if proxy_url:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        return urllib.request.build_opener(proxy_handler)
    return urllib.request.build_opener()


def _download_with_proxy(url: str, filepath: str, timeout: int = 60):
    """使用代理下载文件"""
    opener = _get_proxy_opener()
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=timeout) as resp:
        with open(filepath, "wb") as f:
            f.write(resp.read())


# ================================================================
#  Pixabay 适配器 (免费正版素材, 支持代理)
# ================================================================
class PixabayAdapter(BaseSourceAdapter):
    """Pixabay 免费正版视频素材 (支持代理)"""

    name = "Pixabay"
    priority = 90

    def is_available(self) -> bool:
        return bool(os.environ.get("PIXABAY_API_KEY"))

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        api_key = os.environ.get("PIXABAY_API_KEY")
        if not api_key:
            return []

        try:
            import urllib.parse
            import urllib.request

            encoded_query = urllib.parse.quote(query)
            url = (
                f"https://pixabay.com/api/videos/?"
                f"key={api_key}&q={encoded_query}&per_page={max_results}"
            )

            opener = _get_proxy_opener()
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = []
            videos = data.get("hits", [])
            log(f"  Pixabay 找到 {len(videos)} 个视频: '{query[:30]}...'")

            for vid in videos[:max_results]:
                video_url = vid.get("videos", {}).get("large", {}).get("url")
                if not video_url:
                    video_url = vid.get("videos", {}).get("medium", {}).get("url")
                if not video_url:
                    continue

                filename = f"pixabay_{vid['id']}.mp4"
                filepath = output_dir / filename

                try:
                    _download_with_proxy(video_url, str(filepath))
                    results.append({
                        "success": True,
                        "path": str(filepath),
                        "name": filename,
                        "source": "Pixabay",
                        "url": video_url,
                        "width": vid.get("videos", {}).get("large", {}).get("width", 0),
                        "height": vid.get("videos", {}).get("large", {}).get("height", 0),
                        "duration": vid.get("duration", 0),
                        "query": query,
                    })
                    log(f"    下载: {filename}")
                except Exception as e:
                    log(f"    下载失败: {e}", "WARN")

            return results

        except Exception as e:
            log(f"  Pixabay 搜索失败: {e}", "WARN")
            return []


# ================================================================
#  Pixabay 图片适配器 (可用于AI生图替代方案)
# ================================================================
class PixabayImageAdapter(BaseSourceAdapter):
    """Pixabay 免费正版图片素材 (支持代理)"""

    name = "Pixabay_Images"
    priority = 85

    def is_available(self) -> bool:
        return bool(os.environ.get("PIXABAY_API_KEY"))

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        api_key = os.environ.get("PIXABAY_API_KEY")
        if not api_key:
            return []

        try:
            import urllib.parse
            import urllib.request

            encoded_query = urllib.parse.quote(query)
            url = (
                f"https://pixabay.com/api/?"
                f"key={api_key}&q={encoded_query}&per_page={max_results}&image_type=photo"
            )

            opener = _get_proxy_opener()
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = []
            images = data.get("hits", [])
            log(f"  Pixabay Images 找到 {len(images)} 张图片: '{query[:30]}...'")

            for img in images[:max_results]:
                img_url = img.get("webformatURL") or img.get("largeImageURL")
                if not img_url:
                    continue

                filename = f"pixabay_img_{img['id']}.jpg"
                filepath = output_dir / filename

                try:
                    _download_with_proxy(img_url, str(filepath))
                    results.append({
                        "success": True,
                        "path": str(filepath),
                        "name": filename,
                        "source": "Pixabay_Images",
                        "url": img_url,
                        "width": img.get("imageWidth", 0),
                        "height": img.get("imageHeight", 0),
                        "query": query,
                    })
                    log(f"    下载: {filename} ({img.get('imageWidth',0)}x{img.get('imageHeight',0)})")
                except Exception as e:
                    log(f"    下载失败: {e}", "WARN")

            return results

        except Exception as e:
            log(f"  Pixabay Images 搜索失败: {e}", "WARN")
            return []


# ================================================================
#  蜜柑计划适配器 (动漫资源 - 国内可用)
# ================================================================
class MikananiAdapter(BaseSourceAdapter):
    """蜜柑计划 - 动漫RSS订阅搜索 (国内直接可用)"""

    name = "Mikanani"
    priority = 95  # 动漫资源高优先级

    BASE_URL = "https://mikanani.kas.pub"

    def is_available(self) -> bool:
        return True  # 国内直接可用

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        """搜索动漫资源，下载 .torrent 文件 (HTTP直连可用)"""
        try:
            import urllib.request
            import urllib.parse
            import re

            encoded_query = urllib.parse.quote(query)
            url = f"{self.BASE_URL}/Home/Search?searchstr={encoded_query}"

            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

            opener = _get_proxy_opener() if os.environ.get("HTTPS_PROXY") else urllib.request.build_opener()
            with opener.open(req, timeout=30) as resp:
                html = resp.read().decode("utf-8")

            # 提取 .torrent 文件下载链接 (HTTP可直接下载)
            torrent_pattern = r'href="(/Download/[^"]+\.torrent)"'
            torrents = re.findall(torrent_pattern, html)
            
            # 同时提取磁力链接作为备份
            magnet_pattern = r'magnet:\?xt=urn:btih:[a-fA-F0-9]+'
            magnets = re.findall(magnet_pattern, html)
            
            results = []
            log(f"  蜜柑计划: {len(torrents)} 个种子, {len(magnets)} 个磁力: '{query[:30]}...'")

            # 优先下载 .torrent 文件 (HTTP可用)
            for i, torrent_path in enumerate(torrents[:max_results]):
                torrent_url = f"{self.BASE_URL}{torrent_path}"
                filename = f"mikan_{query[:20].replace(' ', '_')}_{i+1}.torrent"
                filepath = output_dir / filename
                
                try:
                    # 用 aria2 下载 .torrent 文件 (HTTP直连)
                    from auto_downloader import AutoDownloader
                    dl = AutoDownloader(default_output_dir=str(output_dir))
                    if dl.aria2.start_daemon(str(output_dir)):
                        task = dl.aria2.download(torrent_url, str(output_dir), filename=filename)
                        if task.gid:
                            result = dl.aria2.wait_complete(task.gid, timeout=30)
                            if result.status == "completed" and filepath.exists():
                                results.append({
                                    "success": True,
                                    "path": str(filepath),
                                    "name": filename,
                                    "source": "Mikanani",
                                    "query": query,
                                    "type": "torrent_file",
                                    "torrent_url": torrent_url,
                                })
                                log(f"    种子下载成功: {filename}")
                                dl.cleanup()
                                continue
                    dl.cleanup()
                except Exception:
                    pass
                
                # 备用: 直接urllib下载
                try:
                    req2 = urllib.request.Request(torrent_url, headers={"User-Agent": "Mozilla/5.0"})
                    with opener.open(req2, timeout=15) as resp2:
                        with open(filepath, "wb") as f:
                            f.write(resp2.read())
                    if filepath.exists() and filepath.stat().st_size > 0:
                        results.append({
                            "success": True,
                            "path": str(filepath),
                            "name": filename,
                            "source": "Mikanani",
                            "query": query,
                            "type": "torrent_file",
                            "torrent_url": torrent_url,
                        })
                        log(f"    种子下载成功(urllib): {filename}")
                        continue
                except Exception:
                    pass

            # 如果种子下载失败，保存磁力链接作为备份
            if not results and magnets:
                for i, magnet in enumerate(magnets[:max_results]):
                    magnet_file = output_dir / f"mikan_{query[:20].replace(' ', '_')}_{i+1}_magnet.txt"
                    with open(magnet_file, "w", encoding="utf-8") as f:
                        f.write(magnet)
                    results.append({
                        "success": True,
                        "path": str(magnet_file),
                        "name": f"mikan_{i+1}_magnet.txt",
                        "source": "Mikanani",
                        "magnet": magnet,
                        "query": query,
                        "type": "magnet_link",
                    })
                    log(f"    保存磁力链接: {magnet[:50]}...")

            return results

        except Exception as e:
            log(f"  蜜柑计划 搜索失败: {e}", "WARN")
            return []


# ================================================================
#  人人电影网适配器 (影视资源 - 国内可用)
# ================================================================
class RRDYnbAdapter(BaseSourceAdapter):
    """人人电影网 - 影视资源搜索 (百度云/阿里云盘/夸克)"""

    name = "RRDYnb"
    priority = 88  # 影视资源优先级

    BASE_URL = "https://www.rrdynb.com"

    def is_available(self) -> bool:
        return True  # 国内直接可用

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        """搜索影视资源链接"""
        try:
            import urllib.request
            import urllib.parse
            import re

            # 人人电影网搜索 (通过站内搜索)
            encoded_query = urllib.parse.quote(query)
            url = f"{self.BASE_URL}/plus/search.php?kw={encoded_query}"

            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": self.BASE_URL,
            })

            opener = _get_proxy_opener() if os.environ.get("HTTPS_PROXY") else urllib.request.build_opener()
            with opener.open(req, timeout=30) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # 提取资源页面链接
            link_pattern = r'href="(/plus/view\.php\?aid=\d+)"[^>]*>([^<]+)'
            links = re.findall(link_pattern, html)

            results = []
            log(f"  人人电影网 找到 {len(links)} 个资源: '{query[:30]}...'")

            for i, (path, title) in enumerate(links[:max_results]):
                full_url = f"{self.BASE_URL}{path}"
                title = title.strip()

                # 保存资源链接
                link_file = output_dir / f"rrdynb_{query[:20].replace(' ', '_')}_{i+1}_link.txt"
                with open(link_file, "w", encoding="utf-8") as f:
                    f.write(f"标题: {title}\n")
                    f.write(f"链接: {full_url}\n")

                results.append({
                    "success": True,
                    "path": str(link_file),
                    "name": f"rrdynb_{i+1}",
                    "source": "RRDYnb",
                    "title": title,
                    "url": full_url,
                    "query": query,
                    "type": "resource_link",
                })
                log(f"    资源 {i+1}: {title[:40]}...")

            return results

        except Exception as e:
            log(f"  人人电影网 搜索失败: {e}", "WARN")
            return []


# ================================================================
#  B站搜索适配器 (国内直连，yt-dlp下载)
# ================================================================
class BilibiliAdapter(BaseSourceAdapter):
    """B站视频搜索 + yt-dlp下载 (国内直连)"""

    name = "Bilibili"
    priority = 92  # 国内高优先级

    SEARCH_API = "https://api.bilibili.com/x/web-interface/search/all/v2"
    FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"

    def is_available(self) -> bool:
        try:
            subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--version"],
                capture_output=True, check=True, timeout=5,
            )
            return True
        except Exception:
            return False

    def _search_bilibili(self, keyword: str, max_results: int = 5) -> List[Dict]:
        """通过B站API搜索视频"""
        import re as _re
        api_url = f"{self.SEARCH_API}?keyword={urllib.parse.quote(keyword)}&page=1"
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("code") != 0:
            return []

        results = []
        for item in data["data"].get("result", []):
            if item.get("result_type") == "video":
                for v in item.get("data", []):
                    title = _re.sub(r"<[^>]+>", "", v.get("title", ""))
                    bvid = v.get("bvid", "")
                    if bvid:
                        results.append({
                            "title": title,
                            "bvid": bvid,
                            "duration": v.get("duration", ""),
                            "play": v.get("play", 0),
                            "url": f"https://www.bilibili.com/video/{bvid}",
                        })
            if len(results) >= max_results:
                break
        return results

    def _merge_audio_video(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """用ffmpeg合并音视频"""
        ffmpeg = self.FFMPEG_PATH if Path(self.FFMPEG_PATH).exists() else "ffmpeg"
        try:
            cmd = [
                ffmpeg, "-y",
                "-i", video_path, "-i", audio_path,
                "-c:v", "copy", "-c:a", "aac", "-shortest",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and Path(output_path).exists():
                # 清理分离的文件
                Path(video_path).unlink(missing_ok=True)
                Path(audio_path).unlink(missing_ok=True)
                return True
        except Exception:
            pass
        return False

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        """搜索B站视频并下载"""
        try:
            # 1. 搜索
            videos = self._search_bilibili(query, max_results)
            if not videos:
                return []

            log(f"  B站: 找到 {len(videos)} 个视频: '{query[:30]}...'")
            results = []

            # 2. 下载
            for i, video in enumerate(videos[:max_results]):
                safe_title = video["title"][:40].replace(" ", "_").replace("/", "_")
                filename_base = f"bilibili_{safe_title}"
                output_template = str(output_dir / f"{filename_base}.%(ext)s")

                cmd = [
                    sys.executable, "-m", "yt_dlp",
                    "--no-playlist",
                    "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
                    "--merge-output-format", "mp4",
                    "-o", output_template,
                    "--no-check-certificates",
                    video["url"],
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace")

                # 查找下载的文件
                downloaded_files = list(output_dir.glob(f"{filename_base}.*"))
                video_files = [f for f in downloaded_files if f.suffix in (".mp4", ".mkv", ".webm")]
                audio_files = [f for f in downloaded_files if f.suffix in (".m4a", ".aac", ".opus")]

                if video_files:
                    vf = video_files[0]
                    # 尝试合并音视频
                    if audio_files and Path(self.FFMPEG_PATH).exists():
                        merged = output_dir / f"{filename_base}.mp4"
                        if self._merge_audio_video(str(vf), str(audio_files[0]), str(merged)):
                            vf = merged
                            log(f"    合并成功: {vf.name}")

                    results.append({
                        "success": True,
                        "path": str(vf),
                        "name": vf.name,
                        "source": "Bilibili",
                        "url": video["url"],
                        "query": query,
                        "title": video["title"],
                    })
                    log(f"    下载成功: {vf.name} ({vf.stat().st_size/1024/1024:.1f}MB)")

                    # 清理残留的分离文件
                    for f in downloaded_files:
                        if f != vf and f.exists():
                            f.unlink(missing_ok=True)

            return results

        except Exception as e:
            log(f"  B站 搜索/下载失败: {e}", "WARN")
            return []


# ================================================================
#  URL 下载适配器 (B站/抖音/YouTube 等)
# ================================================================
class URLDownloadAdapter(BaseSourceAdapter):
    """通过 yt-dlp 下载用户提供的URL"""

    name = "URL_Downloader"
    priority = 80

    def is_available(self) -> bool:
        try:
            subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
            return True
        except Exception:
            return False

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        """
        query 在这里应该是 URL，不是搜索词。
        如果不是URL，跳过。
        """
        if not query.startswith(("http://", "https://")):
            return []

        filename = f"url_{int(time.time())}_{hash(query) % 10000}.mp4"
        filepath = output_dir / filename

        try:
            log(f"  下载 URL: {query[:60]}...")
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "-f", "best[height<=1080][ext=mp4]/best[height<=1080]/best",
                "--merge-output-format", "mp4",
                "-o", str(filepath),
                query,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0 and filepath.exists():
                return [{
                    "success": True,
                    "path": str(filepath),
                    "name": filename,
                    "source": "URL",
                    "url": query,
                    "query": query,
                }]
            else:
                log(f"    yt-dlp 失败: {result.stderr[:200]}", "WARN")
                return []

        except Exception as e:
            log(f"    下载异常: {e}", "WARN")
            return []


# ================================================================
#  本地素材库适配器
# ================================================================
class LocalLibraryAdapter(BaseSourceAdapter):
    """扫描本地素材库"""

    name = "LocalLibrary"
    priority = 50

    def __init__(self, library_dirs: Optional[List[str]] = None):
        self.library_dirs = library_dirs or [
            r"D:\AE-Work\output",
            r"D:\AE-Work\素材库",
        ]

    def search_and_download(self, query: str, output_dir: Path,
                            max_results: int = 3) -> List[Dict]:
        """
        本地库不支持真正的搜索，只是返回最近的素材。
        如果需要语义搜索，需要额外的索引。
        """
        results = []
        for lib_dir in self.library_dirs:
            lib_path = Path(lib_dir)
            if not lib_path.exists():
                continue

            videos = []
            for ext in ("*.mp4", "*.mov", "*.avi", "*.mkv"):
                videos.extend(lib_path.glob(ext))

            # 按修改时间排序，取最新的
            videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            for v in videos[:max_results]:
                # 复制到输出目录
                dest = output_dir / v.name
                try:
                    shutil.copy2(str(v), str(dest))
                    results.append({
                        "success": True,
                        "path": str(dest),
                        "name": v.name,
                        "source": "LocalLibrary",
                        "query": query,
                    })
                except Exception:
                    continue

        if results:
            log(f"  本地库找到 {len(results)} 个素材")
        return results


# ================================================================
#  素材质量筛选器
# ================================================================
class MaterialFilter:
    """筛选和裁剪素材"""

    def __init__(self,
                 min_width: int = 720,
                 min_height: int = 720,
                 min_duration: float = 2.0,
                 max_duration: float = 60.0,
                 target_duration: Optional[float] = None):
        self.min_width = min_width
        self.min_height = min_height
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.target_duration = target_duration

    def filter(self, materials: List[Dict]) -> List[Dict]:
        """过滤不合格素材"""
        valid = []
        for m in materials:
            if not m.get("success"):
                continue

            path = m.get("path", "")
            if not path or not os.path.exists(path):
                continue

            # 使用 ffprobe 获取视频信息
            info = self._probe_video(path)
            if not info:
                continue

            width = info.get("width", 0)
            height = info.get("height", 0)
            duration = info.get("duration", 0)
            fps = info.get("fps", 0)

            # 分辨率检查
            if width < self.min_width or height < self.min_height:
                log(f"    跳过 (分辨率不足): {m['name']} ({width}x{height})", "WARN")
                continue

            # 时长检查
            if duration < self.min_duration or duration > self.max_duration:
                log(f"    跳过 (时长不符): {m['name']} ({duration:.1f}s)", "WARN")
                continue

            # 更新信息
            m.update({
                "width": width,
                "height": height,
                "duration": duration,
                "fps": fps,
                "info": info,
            })
            valid.append(m)

        log(f"  质量筛选: {len(materials)} → {len(valid)} 个合格")
        return valid

    def _probe_video(self, path: str) -> Optional[Dict]:
        """使用 ffprobe 获取视频信息"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)
            video_stream = None
            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    video_stream = s
                    break

            if not video_stream:
                return None

            duration = float(data.get("format", {}).get("duration", 0))
            if duration == 0:
                duration = float(video_stream.get("duration", 0))

            fps_str = video_stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = float(num) / float(den) if float(den) != 0 else 30
            else:
                fps = float(fps_str)

            return {
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "duration": duration,
                "fps": round(fps, 2),
                "codec": video_stream.get("codec_name", ""),
            }

        except Exception:
            return None

    def trim_clip(self, input_path: str, output_path: str,
                  start_sec: float, duration_sec: float) -> bool:
        """裁剪视频片段"""
        try:
            cmd = [
                "ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration_sec),
                "-i", input_path,
                "-c", "copy", "-avoid_negative_ts", "make_zero",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0 and os.path.exists(output_path)
        except Exception:
            return False


# ================================================================
#  主搜索器
# ================================================================
class MaterialSearcher:
    """
    多平台素材搜索下载器。

    工作流:
    1. 提取关键词
    2. 并行搜索多个平台
    3. 下载素材
    4. 质量筛选
    5. 返回合格素材列表
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.keyword_extractor = KeywordExtractor()
        self.material_filter = MaterialFilter()

        # 注册适配器 (按优先级排序，全部国内直连无需代理)
        self.adapters: List[BaseSourceAdapter] = [
            MikananiAdapter(),       # P1: 蜜柑计划动漫 (priority=95, 国内可用)
            BilibiliAdapter(),       # P1: B站视频搜索下载 (priority=92, 国内可用)
            RRDYnbAdapter(),         # P1: 人人电影网影视 (priority=88, 国内可用)
            URLDownloadAdapter(),    # P2: URL下载 (priority=80)
            LocalLibraryAdapter(),   # P3: 本地素材库
        ]
        
        # 自动下载器 (aria2 主力)
        self._downloader = None

    def search(self, user_prompt: str,
               material_urls: Optional[List[str]] = None,
               min_results: int = 3,
               max_per_source: int = 3) -> List[Dict]:
        """
        主搜索方法。

        Args:
            user_prompt: 用户描述 (如 "利威尔高燃混剪")
            material_urls: 用户提供的URL列表
            min_results: 最少需要的素材数量
            max_per_source: 每个来源最多下载数量

        Returns:
            合格素材列表，每个素材包含 path, width, height, duration 等
        """
        print(f"\n--- MaterialSearcher: 搜索素材 ---")
        log(f"需求: {user_prompt}")

        all_materials: List[Dict] = []

        # 1. 处理用户提供的URL
        if material_urls:
            log(f"处理 {len(material_urls)} 个用户URL...")
            url_adapter = URLDownloadAdapter()
            for url in material_urls:
                results = url_adapter.search_and_download(url, self.output_dir, 1)
                all_materials.extend(results)

        # 2. 提取搜索关键词
        keywords = self.keyword_extractor.extract(user_prompt)
        log(f"搜索关键词: {keywords}")

        # 3. 并行搜索各平台
        log("并行搜索多平台素材库...")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {}

            for adapter in self.adapters:
                if not adapter.is_available():
                    continue
                if isinstance(adapter, URLDownloadAdapter):
                    continue  # URL 已单独处理

                for keyword in keywords:
                    future = executor.submit(
                        adapter.search_and_download,
                        keyword, self.output_dir, max_per_source
                    )
                    futures[future] = (adapter.name, keyword)

            for future in as_completed(futures):
                adapter_name, keyword = futures[future]
                try:
                    results = future.result(timeout=60)
                    all_materials.extend(results)
                    log(f"  {adapter_name}('{keyword[:20]}...'): +{len(results)} 个")
                except Exception as e:
                    log(f"  {adapter_name} 超时/异常: {e}", "WARN")

        log(f"总搜索: {len(all_materials)} 个结果")

        # 3.5 自动下载磁力链接 (通过 aria2)
        all_materials = self._auto_download_magnets(all_materials)

        # 4. 质量筛选
        valid_materials = self.material_filter.filter(all_materials)

        # 5. 如果不足，报告缺口
        if len(valid_materials) < min_results:
            log(f"素材不足: {len(valid_materials)}/{min_results}，需要AI生成补充", "WARN")
        else:
            log(f"素材充足: {len(valid_materials)} 个合格素材")

        return valid_materials

    def get_missing_count(self, materials: List[Dict], min_results: int = 3) -> int:
        """计算还需要多少个素材"""
        valid = [m for m in materials if m.get("success")]
        return max(0, min_results - len(valid))

    def _get_downloader(self):
        """懒加载自动下载器"""
        if self._downloader is None:
            try:
                from auto_downloader import AutoDownloader
                self._downloader = AutoDownloader(
                    default_output_dir=str(self.output_dir)
                )
                log("自动下载器 (aria2) 已加载")
            except Exception as e:
                log(f"自动下载器加载失败: {e}", "WARN")
        return self._downloader

    def _auto_download_magnets(self, materials: List[Dict]) -> List[Dict]:
        """将搜索到的磁力链接通过 aria2 自动下载"""
        downloader = self._get_downloader()
        if not downloader:
            log("无可用下载器，磁力链接仅保存文件，未自动下载", "WARN")
            return materials

        downloaded = []
        for m in materials:
            if m.get("type") == "magnet_link" and m.get("magnet"):
                magnet = m["magnet"]
                log(f"  aria2 自动下载: {magnet[:50]}...")
                try:
                    task = downloader.download(magnet, str(self.output_dir))
                    if task.gid:
                        result = downloader.aria2.wait_complete(task.gid, timeout=600)
                        if result.status == "completed":
                            m["success"] = True
                            m["path"] = str(self.output_dir / (result.filename or ""))
                            m["type"] = "video_file"
                            m["source"] = f"{m.get('source', '')}+aria2"
                            log(f"    下载完成: {result.filename}")
                        else:
                            log(f"    下载失败: {result.error}", "WARN")
                    else:
                        log(f"    添加任务失败: {task.error}", "WARN")
                except Exception as e:
                    log(f"    下载异常: {e}", "WARN")
            downloaded.append(m)

        return downloaded


# ================================================================
#  快捷函数
# ================================================================
def search_materials(user_prompt: str,
                     material_urls: Optional[List[str]] = None,
                     min_results: int = 3) -> List[Dict]:
    """快捷函数：搜索素材"""
    searcher = MaterialSearcher()
    return searcher.search(user_prompt, material_urls, min_results)


if __name__ == "__main__":
    print("=" * 60)
    print("  MaterialSearcher - 素材搜索测试")
    print("=" * 60)

    # 测试关键词提取
    extractor = KeywordExtractor()
    test_prompts = [
        "利威尔高燃混剪, 30秒, 竖屏",
        "冰海战记电影感混剪",
        "古风唯美意境视频",
    ]
    for p in test_prompts:
        keywords = extractor.extract(p)
        print(f"\n'{p}' → {keywords}")

    # 测试搜索 (需要 API Key)
    print("\n--- 搜索测试 ---")
    searcher = MaterialSearcher()

    # 检查可用适配器
    for adapter in searcher.adapters:
        avail = "✅" if adapter.is_available() else "❌"
        print(f"  {avail} {adapter.name} (P{adapter.priority})")

    # 如果 Pexels API Key 存在，执行真实搜索
    if os.environ.get("PEXELS_API_KEY"):
        results = searcher.search("nature cinematic", min_results=2)
        print(f"\n搜索结果: {len(results)} 个")
        for r in results:
            print(f"  - {r.get('name')}: {r.get('width')}x{r.get('height')}, {r.get('duration',0):.1f}s")
    else:
        print("\n跳过真实搜索 (无 PEXELS_API_KEY)")
        print("请设置环境变量: PEXELS_API_KEY")
    test_prompts = [
        "利威尔高燃混剪, 30秒, 竖屏",
        "冰海战记电影感混剪",
        "古风唯美意境视频",
    ]
    for p in test_prompts:
        keywords = extractor.extract(p)
        print(f"\n'{p}' → {keywords}")

    # 测试搜索 (需要 API Key)
    print("\n--- 搜索测试 ---")
    searcher = MaterialSearcher()

    # 检查可用适配器
    for adapter in searcher.adapters:
        avail = "✅" if adapter.is_available() else "❌"
        print(f"  {avail} {adapter.name} (P{adapter.priority})")

    # 如果 Pexels API Key 存在，执行真实搜索
    if os.environ.get("PEXELS_API_KEY"):
        results = searcher.search("nature cinematic", min_results=2)
        print(f"\n搜索结果: {len(results)} 个")
        for r in results:
            print(f"  - {r.get('name')}: {r.get('width')}x{r.get('height')}, {r.get('duration',0):.1f}s")
    else:
        print("\n跳过真实搜索 (无 PEXELS_API_KEY)")
        print("请设置环境变量: PEXELS_API_KEY")
