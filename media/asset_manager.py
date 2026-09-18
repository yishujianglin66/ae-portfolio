#!/usr/bin/env python3
"""素材管理器 - 全网免费素材搜索、下载、收藏、管理"""

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

DOWNLOAD_DIR = Path(r"D:\AE-Work\素材库")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

EXISTING_LIBRARIES = {
    "video": Path(r"D:\AE-Work\视频素材库"),
    "image": Path(r"D:\AE-Work\图片素材库"),
    "audio": Path(r"D:\AE-Work\音频素材库"),
    "sound": Path(r"D:\AE-Work\音效素材库"),
}

DB_PATH = DOWNLOAD_DIR / "asset_manager.db"

SUPPORTED_TYPES = {"video", "image", "audio"}

LICENSES = {
    "cc0": "公共领域",
    "cc-by": "署名",
    "cc-by-sa": "署名-相同方式共享",
    "cc-by-nd": "署名-禁止演绎",
    "cc-by-nc": "署名-非商业性使用",
    "cc-by-nc-sa": "署名-非商业性使用-相同方式共享",
    "cc-by-nc-nd": "署名-非商业性使用-禁止演绎",
}

class AssetManager:
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._init_db()
        self.search_providers = []
        self._register_providers()
        self._init_post_processor()

    def sync_local_library(self) -> dict:
        """同步本地素材库到数据库"""
        print("🔄 同步本地素材库...")
        
        synced_count = 0
        
        for media_type, library_path in EXISTING_LIBRARIES.items():
            if not library_path.exists():
                continue
            
            for f in library_path.rglob("*"):
                if f.is_file():
                    item = {
                        "title": f.stem,
                        "type": "video" if media_type == "video" else "image" if media_type == "image" else "audio",
                        "url": str(f),
                        "download_path": str(f),
                        "platform": "local",
                        "author": "local",
                        "license": "local",
                        "downloaded": True
                    }
                    self._save_to_db(item, str(f))
                    synced_count += 1
        
        print(f"✅ 同步完成，共 {synced_count} 个素材")
        return {"success": True, "synced_count": synced_count}

    def search_local(self, query: str, media_type: str = "all") -> dict:
        """搜索本地素材库"""
        results = []

        def _search_dir(library_path, type_name, extensions):
            if library_path.exists():
                for f in library_path.rglob("*"):
                    if f.is_file() and f.suffix.lower() in extensions:
                        if not query or query.lower() in f.stem.lower() or query.lower() in f.parent.name.lower():
                            results.append({
                                "title": f.stem,
                                "type": type_name,
                                "url": str(f),
                                "download_path": str(f),
                                "platform": "local",
                                "author": "local",
                                "license": "local",
                                "downloaded": True
                            })

        if media_type in ("video", "all"):
            _search_dir(EXISTING_LIBRARIES["video"], "video", (".mp4", ".mov", ".avi", ".mkv"))

        if media_type in ("image", "all"):
            _search_dir(EXISTING_LIBRARIES["image"], "image", (".jpg", ".jpeg", ".png", ".gif"))

        if media_type in ("audio", "all"):
            _search_dir(EXISTING_LIBRARIES["audio"], "audio", (".mp3", ".wav", ".flac", ".m4a"))
            _search_dir(EXISTING_LIBRARIES["sound"], "audio", (".mp3", ".wav", ".flac", ".m4a"))

        return {
            "success": True,
            "query": query,
            "media_type": media_type,
            "results": results,
            "total": len(results),
            "platform": "local"
        }

    def _init_post_processor(self):
        try:
            from ae_mcp_client import AECommandClient
            self.ae_client = AECommandClient(timeout=30)
        except Exception:
            self.ae_client = None

        try:
            from topaz_integration import TopazConfig, TopazEnhancer
            self.topaz_enhancer = TopazEnhancer()
        except Exception:
            self.topaz_enhancer = None

        try:
            from davinci_resolve_integration import DavinciColorist, ResolveColorConfig
            self.davinci_colorist = DavinciColorist()
        except Exception:
            self.davinci_colorist = None

        try:
            from media_preprocessor import MediaPreprocessor
            self.media_preprocessor = MediaPreprocessor()
        except Exception:
            self.media_preprocessor = None

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                thumbnail TEXT,
                download_path TEXT,
                platform TEXT NOT NULL,
                author TEXT,
                license TEXT,
                license_name TEXT,
                duration REAL,
                width INTEGER,
                height INTEGER,
                tags TEXT,
                search_query TEXT,
                downloaded INTEGER DEFAULT 0,
                downloaded_at TEXT,
                favorite INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                media_type TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                results_count INTEGER
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_downloaded ON assets(downloaded)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_assets_favorite ON assets(favorite)
        """)

        conn.commit()
        conn.close()

    def _register_providers(self):
        self.search_providers.append(PixabayProvider())
        self.search_providers.append(PexelsProvider())
        self.search_providers.append(JamendoProvider())
        self.search_providers.append(UnsplashProvider())
        self.search_providers.append(VidevoProvider())
        self.search_providers.append(FreeSoundProvider())

    def search(self, query: str, media_type: str = "all", limit: int = 20, include_local: bool = True) -> dict:
        """全网搜索素材"""
        print(f"🔍 搜索: '{query}' ({media_type})")

        results = []
        errors = {}

        def _search_with_provider(provider):
            try:
                if media_type == "all":
                    types_to_search = provider.supported_types
                else:
                    types_to_search = [media_type] if media_type in provider.supported_types else []

                for mt in types_to_search:
                    for attempt in range(3):
                        try:
                            provider_results = provider.search(query, mt, limit // len(self.search_providers))
                            for r in provider_results.get("items", []):
                                r["platform"] = provider.name
                                results.append(r)
                            break
                        except requests.exceptions.Timeout:
                            if attempt < 2:
                                time.sleep(2)
                                continue
                            else:
                                errors[provider.name] = "超时"
                            break
                        except Exception as e:
                            errors[provider.name] = str(e)
                            break
                return None
            except Exception as e:
                return {provider.name: str(e)}

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(_search_with_provider, p) for p in self.search_providers]
            for future in as_completed(futures):
                err = future.result()
                if err:
                    errors.update(err)

        results = self._deduplicate(results)

        if include_local and len(results) == 0:
            print("⚠️  网络搜索无结果，搜索本地素材库")
            local_results = self.search_local(query, media_type)
            results.extend(local_results["results"])

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("INSERT INTO searches (query, media_type, results_count) VALUES (?, ?, ?)",
                  (query, media_type, len(results)))
        conn.commit()
        conn.close()

        print(f"✅ 搜索完成: {len(results)} 个结果")
        return {
            "success": True,
            "query": query,
            "media_type": media_type,
            "results": results,
            "total": len(results),
            "errors": errors
        }

    def _deduplicate(self, results: list[dict]) -> list[dict]:
        seen_titles = set()
        deduped = []
        for r in results:
            title_key = r.get("title", "").lower().strip()[:100]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                deduped.append(r)
        return deduped

    def download_all(self, results: list[dict], force: bool = False) -> dict:
        """批量下载搜索结果"""
        downloaded = []
        skipped = []
        failed = []

        for item in results:
            result = self.download(item, force=force)
            if result["success"]:
                downloaded.append(result)
            elif result["status"] == "skipped":
                skipped.append(result)
            else:
                failed.append(result)

        return {
            "success": len(failed) == 0,
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
            "total": len(results),
            "download_count": len(downloaded)
        }

    def download(self, item: dict, force: bool = False) -> dict:
        """下载单个素材"""
        url = item.get("url")
        title = item.get("title", "untitled")
        media_type = item.get("type", "video")

        ext_map = {"video": ".mp4", "image": ".jpg", "audio": ".mp3"}
        ext = ext_map.get(media_type, ".mp4")

        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
        filename = f"{safe_title}_{int(time.time())}{ext}"
        save_dir = DOWNLOAD_DIR / media_type
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename

        if save_path.exists() and not force:
            self._save_to_db(item, str(save_path))
            return {
                "success": True,
                "status": "skipped",
                "message": f"已存在: {save_path.name}",
                "path": str(save_path)
            }

        try:
            print(f"📥 下载: {title} -> {save_path.name}")

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=60, stream=True)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self._save_to_db(item, str(save_path))

            print(f"✅ 完成: {save_path.name}")
            return {
                "success": True,
                "status": "downloaded",
                "path": str(save_path),
                "size": save_path.stat().st_size
            }
        except Exception as e:
            print(f"❌ 失败: {title} - {e}")
            return {
                "success": False,
                "status": "failed",
                "message": str(e),
                "title": title
            }

    def _save_to_db(self, item: dict, download_path: str):
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute("""
            INSERT OR REPLACE INTO assets (
                title, type, url, thumbnail, download_path, platform,
                author, license, license_name, duration, width, height, tags,
                search_query, downloaded, downloaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            item.get("title", ""),
            item.get("type", ""),
            item.get("url", ""),
            item.get("thumbnail", ""),
            download_path,
            item.get("platform", ""),
            item.get("author", ""),
            item.get("license", ""),
            LICENSES.get(item.get("license", ""), ""),
            item.get("duration", 0),
            item.get("width", 0),
            item.get("height", 0),
            json.dumps(item.get("tags", [])),
            item.get("search_query", ""),
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

    def download_from_url(self, url: str, title: str = None, media_type: str = "video") -> dict:
        """从直接链接下载素材"""
        print(f"📥 直接下载链接: {url}")

        parsed = urlparse(url)
        filename = unquote(parsed.path.split("/")[-1]) if parsed.path else f"download_{int(time.time())}"

        if not title:
            title = filename.split(".")[0] if "." in filename else f"download_{int(time.time())}"

        ext_map = {"video": ".mp4", "image": ".jpg", "audio": ".mp3"}
        ext = Path(filename).suffix.lower() if "." in filename else ext_map.get(media_type, ".mp4")

        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
        final_filename = f"{safe_title}_{int(time.time())}{ext}"
        save_dir = DOWNLOAD_DIR / media_type
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / final_filename

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Referer": parsed.scheme + "://" + parsed.netloc
            }
            response = requests.get(url, headers=headers, timeout=120, stream=True)
            response.raise_for_status()

            content_length = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if content_length > 0:
                        progress = int((downloaded / content_length) * 100)
                        print(f"\r  进度: {progress}%", end="")
            print()

            item = {
                "title": title,
                "type": media_type,
                "url": url,
                "download_path": str(save_path),
                "platform": "direct_link",
                "author": "unknown",
                "license": "unknown",
                "downloaded": True
            }
            self._save_to_db(item, str(save_path))

            print(f"✅ 完成: {save_path.name}")
            return {
                "success": True,
                "status": "downloaded",
                "path": str(save_path),
                "size": save_path.stat().st_size
            }
        except Exception as e:
            print(f"❌ 失败: {title} - {e}")
            return {
                "success": False,
                "status": "failed",
                "message": str(e),
                "title": title
            }

    def download_from_urls(self, urls: list[str], media_type: str = "video") -> dict:
        """批量从直接链接下载素材"""
        results = []
        for url in urls:
            result = self.download_from_url(url, media_type=media_type)
            results.append(result)

        downloaded = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        return {
            "success": len(failed) == 0,
            "downloaded": downloaded,
            "failed": failed,
            "total": len(urls),
            "download_count": len(downloaded)
        }

    def analyze_url(self, url: str) -> dict:
        """分析URL类型和提取信息"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        patterns = {
            "bilibili": r"(bilibili\.com|b23\.tv)",
            "youtube": r"(youtube\.com|youtu\.be)",
            "vimeo": r"vimeo\.com",
            "pixabay": r"pixabay\.com",
            "pexels": r"pexels\.com",
            "unsplash": r"unsplash\.com",
            "soundcloud": r"soundcloud\.com",
            "jamendo": r"jamendo\.com",
            "freesound": r"freesound\.org",
            "videvo": r"videvo\.net",
            "direct_file": r"\.(mp4|mov|avi|mkv|jpg|jpeg|png|gif|mp3|wav|flac|m4a)$"
        }

        platform = "unknown"
        media_type = "video"
        video_id = None
        author = None

        for name, pattern in patterns.items():
            if re.search(pattern, domain):
                platform = name
                break

        if re.search(r"\.(jpg|jpeg|png|gif)$", parsed.path, re.IGNORECASE):
            media_type = "image"
        elif re.search(r"\.(mp3|wav|flac|m4a)$", parsed.path, re.IGNORECASE):
            media_type = "audio"

        if platform == "bilibili":
            match = re.search(r"av(\d+)|BV([a-zA-Z0-9]+)", url)
            if match:
                video_id = match.group(1) or match.group(2)

            match = re.search(r"space\.bilibili\.com/(\d+)", url)
            if match:
                author = match.group(1)

        elif platform == "youtube":
            match = re.search(r"watch\?v=([^&]+)|youtu\.be/([^/]+)", url)
            if match:
                video_id = match.group(1) or match.group(2)

            match = re.search(r"channel/([^/]+)|user/([^/]+)", url)
            if match:
                author = match.group(1) or match.group(2)

        elif platform == "vimeo":
            match = re.search(r"vimeo\.com/(\d+)", url)
            if match:
                video_id = match.group(1)

        return {
            "url": url,
            "domain": domain,
            "platform": platform,
            "media_type": media_type,
            "video_id": video_id,
            "author": author
        }

    def fetch_creator_info(self, platform: str, creator_id: str) -> dict:
        """获取创作者信息"""
        if platform == "bilibili":
            return self._fetch_bilibili_creator(creator_id)
        elif platform == "youtube":
            return self._fetch_youtube_creator(creator_id)
        else:
            return {"success": False, "error": f"不支持的平台: {platform}"}

    def _fetch_bilibili_creator(self, uid: str) -> dict:
        """获取B站创作者信息"""
        try:
            url = f"https://api.bilibili.com/x/space/wbi/acc/info?mid={uid}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                info = data.get("data", {})
                return {
                    "success": True,
                    "platform": "bilibili",
                    "uid": uid,
                    "name": info.get("name", ""),
                    "avatar": info.get("face", ""),
                    "description": info.get("sign", ""),
                    "video_count": info.get("video", 0),
                    "follower_count": info.get("follower", 0),
                    "likes_count": info.get("likes", 0)
                }
            else:
                return {"success": False, "error": data.get("message", "获取失败")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _fetch_youtube_creator(self, channel_id: str) -> dict:
        """获取YouTube创作者信息"""
        return {
            "success": False,
            "error": "YouTube API需要认证，无法获取信息"
        }

    def search_creator_videos(self, platform: str, creator_id: str, limit: int = 10) -> dict:
        """搜索创作者视频"""
        if platform == "bilibili":
            return self._search_bilibili_videos(creator_id, limit)
        else:
            return {"success": False, "error": f"不支持的平台: {platform}"}

    def _search_bilibili_videos(self, uid: str, limit: int = 10) -> dict:
        """搜索B站用户视频"""
        try:
            url = f"https://api.bilibili.com/x/space/wbi/arc/search?mid={uid}&ps={limit}&pn=1"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                videos = []
                for item in data.get("data", {}).get("list", {}).get("vlist", []):
                    videos.append({
                        "title": item.get("title", ""),
                        "type": "video",
                        "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                        "thumbnail": item.get("pic", ""),
                        "author": item.get("author", ""),
                        "platform": "bilibili",
                        "duration": self._parse_duration(item.get("length", "0")),
                        "play_count": item.get("play", 0),
                        "comment_count": item.get("comment", 0),
                        "favorite_count": item.get("favorites", 0),
                        "tags": []
                    })

                return {
                    "success": True,
                    "platform": "bilibili",
                    "creator_id": uid,
                    "results": videos,
                    "total": len(videos)
                }
            else:
                return {"success": False, "error": data.get("message", "获取失败")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _parse_duration(self, duration_str: str) -> float:
        """解析时长字符串为秒"""
        try:
            parts = list(map(int, duration_str.split(":")))
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                return parts[0] * 60 + parts[1]
            elif len(parts) == 1:
                return parts[0]
        except Exception:
            pass
        return 0.0

    def add_favorite(self, url: str) -> bool:
        """收藏素材"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("UPDATE assets SET favorite = 1 WHERE url = ?", (url,))
        conn.commit()
        conn.close()
        return c.rowcount > 0

    def remove_favorite(self, url: str) -> bool:
        """取消收藏"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("UPDATE assets SET favorite = 0 WHERE url = ?", (url,))
        conn.commit()
        conn.close()
        return c.rowcount > 0

    def get_favorites(self, media_type: str = None) -> list[dict]:
        """获取收藏列表"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        if media_type:
            c.execute("SELECT * FROM assets WHERE favorite = 1 AND type = ? ORDER BY created_at DESC", (media_type,))
        else:
            c.execute("SELECT * FROM assets WHERE favorite = 1 ORDER BY created_at DESC")

        rows = c.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def get_downloaded(self, media_type: str = None) -> list[dict]:
        """获取已下载列表"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        if media_type:
            c.execute("SELECT * FROM assets WHERE downloaded = 1 AND type = ? ORDER BY downloaded_at DESC", (media_type,))
        else:
            c.execute("SELECT * FROM assets WHERE downloaded = 1 ORDER BY downloaded_at DESC")

        rows = c.fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row[0],
            "title": row[1],
            "type": row[2],
            "url": row[3],
            "thumbnail": row[4],
            "download_path": row[5],
            "platform": row[6],
            "author": row[7],
            "license": row[8],
            "license_name": row[9],
            "duration": row[10],
            "width": row[11],
            "height": row[12],
            "tags": json.loads(row[13]) if row[13] else [],
            "search_query": row[14],
            "downloaded": bool(row[15]),
            "downloaded_at": row[16],
            "favorite": bool(row[17]),
            "rating": row[18],
            "notes": row[19],
            "created_at": row[20]
        }

    def get_stats(self) -> dict:
        """获取统计信息"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM assets")
        total = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM assets WHERE downloaded = 1")
        downloaded = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM assets WHERE favorite = 1")
        favorites = c.fetchone()[0]

        c.execute("SELECT type, COUNT(*) FROM assets WHERE downloaded = 1 GROUP BY type")
        type_stats = dict(c.fetchall())

        c.execute("SELECT platform, COUNT(*) FROM assets WHERE downloaded = 1 GROUP BY platform")
        platform_stats = dict(c.fetchall())

        conn.close()

        return {
            "total_assets": total,
            "downloaded_count": downloaded,
            "favorite_count": favorites,
            "type_stats": type_stats,
            "platform_stats": platform_stats
        }

    def enhance_video(self, input_path: str, output_dir: str = None) -> dict:
        """使用Topaz Video AI增强视频"""
        if not self.topaz_enhancer or not self.topaz_enhancer.is_available():
            return {"success": False, "error": "Topaz Video AI不可用"}

        output_dir = Path(output_dir) if output_dir else DOWNLOAD_DIR / "enhanced"
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = Path(input_path).stem
        output_path = str(output_dir / f"{base_name}_enhanced.mp4")

        try:
            from topaz_integration import TopazConfig
            result = self.topaz_enhancer.enhance_video(
                input_path=input_path,
                output_path=output_path,
                config=TopazConfig(model="proteus", scale=1.0)
            )

            if result.success:
                return {
                    "success": True,
                    "input_path": input_path,
                    "output_path": result.output_path,
                    "mode": result.mode,
                    "message": "视频增强完成"
                }
            else:
                return {"success": False, "error": str(result.error)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def color_grade_video(self, input_path: str, output_dir: str = None) -> dict:
        """使用DaVinci Resolve调色"""
        if not self.davinci_colorist or not self.davinci_colorist.is_available():
            return {"success": False, "error": "DaVinci Resolve不可用"}

        output_dir = Path(output_dir) if output_dir else DOWNLOAD_DIR / "graded"
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = Path(input_path).stem
        output_path = str(output_dir / f"{base_name}_graded.mp4")

        try:
            from davinci_resolve_integration import ResolveColorConfig
            result = self.davinci_colorist.color_grade(
                input_path=input_path,
                output_path=output_path,
                config=ResolveColorConfig(color_preset="cinematic")
            )

            if result.success:
                return {
                    "success": True,
                    "input_path": input_path,
                    "output_path": result.output_path,
                    "mode": result.mode,
                    "message": "视频调色完成"
                }
            else:
                return {"success": False, "error": str(result.error)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def import_to_ae(self, file_path: str, composition_name: str = None) -> dict:
        """导入素材到AE合成"""
        if not self.ae_client:
            return {"success": False, "error": "AE MCP Bridge不可用"}

        try:
            comp_name = composition_name or f"Asset_Import_{int(time.time())}"

            result = self.ae_client.send_command("createComposition", {
                "name": comp_name,
                "width": 1920,
                "height": 1080,
                "duration": 30.0,
                "frameRate": 30.0
            })

            if result.get("status") != "success":
                return {"success": False, "error": result.get("message", "创建合成失败")}

            import_result = self.ae_client.send_command("importFootage", {
                "filePath": file_path.replace("\\", "/")
            })

            if import_result.get("status") == "success":
                return {
                    "success": True,
                    "composition": comp_name,
                    "file_path": file_path,
                    "message": "素材已导入AE"
                }
            else:
                return {"success": False, "error": import_result.get("message", "导入失败")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_workflow(self, input_path: str, workflow: str = "default") -> dict:
        """完整后期处理工作流"""
        print(f"🔄 启动工作流: {workflow}")

        steps = []

        if workflow in ("default", "video", "full"):
            steps.append({"name": "视频增强", "func": self.enhance_video, "args": (input_path,)})

        if workflow in ("default", "video", "full", "color"):
            steps.append({"name": "视频调色", "func": self.color_grade_video, "args": (input_path,)})

        if workflow in ("full", "ae"):
            steps.append({"name": "导入AE", "func": self.import_to_ae, "args": (input_path,)})

        results = {}
        for step in steps:
            print(f"  📋 {step['name']}...")
            result = step["func"](*step["args"])
            results[step["name"]] = result
            if result["success"]:
                print(f"  ✅ {step['name']}完成")
            else:
                print(f"  ❌ {step['name']}失败: {result.get('error')}")

        return {
            "success": all(r["success"] for r in results.values()),
            "workflow": workflow,
            "steps": results,
            "input_path": input_path
        }


class SearchProvider:
    name = "base"
    supported_types = []

    def search(self, query: str, media_type: str, limit: int) -> dict:
        return {"items": []}


class PixabayProvider(SearchProvider):
    name = "pixabay"
    supported_types = ["image", "video"]

    def search(self, query: str, media_type: str, limit: int) -> dict:
        api_key = os.environ.get("PIXABAY_API_KEY", "")
        if not api_key:
            _logger.warning("Pixabay API Key 未配置（环境变量 PIXABAY_API_KEY），跳过搜索")
            return {"items": []}
        endpoint = f"https://pixabay.com/api/{'videos' if media_type == 'video' else ''}"

        params = {
            "key": api_key,
            "q": query,
            "per_page": min(limit, 200),
            "safesearch": "true"
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            items = []
            for hit in data.get("hits", []):
                items.append({
                    "title": hit.get("tags", "").split(",")[0] if hit.get("tags") else hit.get("pageURL", ""),
                    "type": media_type,
                    "url": hit.get("videos", {}).get("large", {}).get("url", hit.get("largeImageURL")),
                    "thumbnail": hit.get("previewURL", hit.get("videos", {}).get("tiny", {}).get("url")),
                    "author": hit.get("user", ""),
                    "license": "cc0",
                    "width": hit.get("width", 0),
                    "height": hit.get("height", 0),
                    "duration": hit.get("duration", 0),
                    "tags": hit.get("tags", "").split(",") if hit.get("tags") else []
                })

            return {"success": True, "items": items}
        except Exception:
            return {"success": True, "items": []}


class PexelsProvider(SearchProvider):
    name = "pexels"
    supported_types = ["image", "video"]

    def search(self, query: str, media_type: str, limit: int) -> dict:
        api_key = os.environ.get("PEXELS_API_KEY", "")

        if not api_key:
            return {"success": True, "items": []}

        endpoint = f"https://api.pexels.com/v1/search{'/videos' if media_type == 'video' else ''}"

        headers = {"Authorization": api_key}
        params = {
            "query": query,
            "per_page": min(limit, 80)
        }

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            items = []
            for photo in data.get("photos", data.get("videos", [])):
                if media_type == "video":
                    video_files = photo.get("video_files", [])
                    video_url = video_files[0]["link"] if video_files else ""
                    thumbnails = photo.get("video_pictures", [])
                    thumbnail = thumbnails[0]["picture"] if thumbnails else ""
                    duration = photo.get("duration", 0)
                else:
                    video_url = photo.get("src", {}).get("original", "")
                    thumbnail = photo.get("src", {}).get("medium", "")
                    duration = 0

                items.append({
                    "title": photo.get("alt", photo.get("url", "")),
                    "type": media_type,
                    "url": video_url,
                    "thumbnail": thumbnail,
                    "author": photo.get("photographer", ""),
                    "license": "cc-by",
                    "width": photo.get("width", 0),
                    "height": photo.get("height", 0),
                    "duration": duration,
                    "tags": []
                })

            return {"success": True, "items": items}
        except Exception:
            return {"success": True, "items": []}


class JamendoProvider(SearchProvider):
    name = "jamendo"
    supported_types = ["audio"]

    def search(self, query: str, media_type: str, limit: int) -> dict:
        client_id = os.environ.get("JAMENDO_CLIENT_ID", "")

        if not client_id:
            return {"success": True, "items": []}

        endpoint = "https://api.jamendo.com/v3.0/tracks"

        params = {
            "client_id": client_id,
            "search": query,
            "limit": min(limit, 200),
            "audioformat": "mp3"
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            items = []
            for track in data.get("results", []):
                items.append({
                    "title": track.get("name", ""),
                    "type": "audio",
                    "url": track.get("audio", ""),
                    "thumbnail": track.get("album", {}).get("image", ""),
                    "author": track.get("artist_name", ""),
                    "license": track.get("license_ccurl", "").split("/")[-1] if track.get("license_ccurl") else "",
                    "duration": track.get("duration", 0),
                    "tags": track.get("tags", [])
                })

            return {"success": True, "items": items}
        except Exception:
            return {"success": True, "items": []}


class UnsplashProvider(SearchProvider):
    name = "unsplash"
    supported_types = ["image"]

    def search(self, query: str, media_type: str, limit: int) -> dict:
        api_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")

        if not api_key:
            return {"success": True, "items": []}

        endpoint = "https://api.unsplash.com/search/photos"

        headers = {"Authorization": f"Client-ID {api_key}"}
        params = {
            "query": query,
            "per_page": min(limit, 30)
        }

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            items = []
            for result in data.get("results", []):
                urls = result.get("urls", {})
                items.append({
                    "title": result.get("alt_description", result.get("description", "")),
                    "type": "image",
                    "url": urls.get("regular", urls.get("full", "")),
                    "thumbnail": urls.get("small", ""),
                    "author": result.get("user", {}).get("name", ""),
                    "license": "cc0",
                    "width": result.get("width", 0),
                    "height": result.get("height", 0),
                    "tags": [tag["title"] for tag in result.get("tags", [])]
                })

            return {"success": True, "items": items}
        except Exception:
            return {"success": True, "items": []}


class VidevoProvider(SearchProvider):
    name = "videvo"
    supported_types = ["video", "audio"]

    def search(self, query: str, media_type: str, limit: int) -> dict:
        endpoint = f"https://www.videvo.net/api/v2/{'videos' if media_type == 'video' else 'audio'}"

        params = {
            "search": query,
            "limit": min(limit, 50),
            "page": 1
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            items = []
            for item in data.get("results", []):
                download_links = item.get("download_links", {})
                url = download_links.get("mp4_720p", download_links.get("mp3", download_links.get("wav", "")))

                if not url:
                    continue

                items.append({
                    "title": item.get("title", ""),
                    "type": media_type,
                    "url": url,
                    "thumbnail": item.get("thumbnail", ""),
                    "author": item.get("author", {}).get("name", ""),
                    "license": "cc0" if item.get("isExclusive") == False else "cc-by",
                    "duration": item.get("duration", 0),
                    "width": item.get("width", 0),
                    "height": item.get("height", 0),
                    "tags": item.get("tags", [])
                })

            return {"success": True, "items": items}
        except Exception:
            return {"success": True, "items": []}


class FreeSoundProvider(SearchProvider):
    name = "freesound"
    supported_types = ["audio"]

    def search(self, query: str, media_type: str, limit: int) -> dict:
        api_key = os.environ.get("FREESOUND_API_KEY", "")

        if not api_key:
            return {"success": True, "items": []}

        endpoint = "https://freesound.org/api/v1/search"

        params = {
            "query": query,
            "token": api_key,
            "limit": min(limit, 150),
            "fields": "id,name,url,previews,username,license,duration,tags"
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            items = []
            for result in data.get("results", []):
                items.append({
                    "title": result.get("name", ""),
                    "type": "audio",
                    "url": result.get("previews", {}).get("preview-hq-mp3", ""),
                    "thumbnail": "",
                    "author": result.get("username", ""),
                    "license": result.get("license", "").split("/")[-1],
                    "duration": result.get("duration", 0),
                    "tags": result.get("tags", [])
                })

            return {"success": True, "items": items}
        except Exception:
            return {"success": True, "items": []}


def main():
    print("=" * 60)
    print("素材管理器 - 全网免费素材搜索下载系统")
    print("=" * 60)

    manager = AssetManager()

    stats = manager.get_stats()
    print("\n📊 当前素材库统计:")
    print(f"   总素材: {stats['total_assets']}")
    print(f"   已下载: {stats['downloaded_count']}")
    print(f"   收藏: {stats['favorite_count']}")

    while True:
        print("\n" + "=" * 60)
        print("操作菜单:")
        print("  1. 搜索视频素材")
        print("  2. 搜索图片素材")
        print("  3. 搜索音频素材")
        print("  4. 搜索全部类型")
        print("  5. 查看已下载列表")
        print("  6. 查看收藏列表")
        print("  7. 视频增强(Topaz)")
        print("  8. 视频调色(DaVinci)")
        print("  9. 导入素材到AE")
        print("  10. 完整后期工作流")
        print("  11. 从链接直接下载")
        print("  12. 分析URL信息")
        print("  13. 获取创作者信息")
        print("  14. 搜索创作者视频")
        print("  15. 退出")
        print("=" * 60)

        choice = input("请选择操作 [1-15]: ").strip()

        if choice == "1":
            query = input("搜索关键词: ").strip()
            results = manager.search(query, "video", 15)
            download_choice = input(f"找到 {results['total']} 个结果，是否全部下载? [Y/n]: ").strip().lower()
            if download_choice in ("", "y", "yes"):
                manager.download_all(results["results"])

        elif choice == "2":
            query = input("搜索关键词: ").strip()
            results = manager.search(query, "image", 15)
            download_choice = input(f"找到 {results['total']} 个结果，是否全部下载? [Y/n]: ").strip().lower()
            if download_choice in ("", "y", "yes"):
                manager.download_all(results["results"])

        elif choice == "3":
            query = input("搜索关键词: ").strip()
            results = manager.search(query, "audio", 15)
            download_choice = input(f"找到 {results['total']} 个结果，是否全部下载? [Y/n]: ").strip().lower()
            if download_choice in ("", "y", "yes"):
                manager.download_all(results["results"])

        elif choice == "4":
            query = input("搜索关键词: ").strip()
            results = manager.search(query, "all", 10)
            download_choice = input(f"找到 {results['total']} 个结果，是否全部下载? [Y/n]: ").strip().lower()
            if download_choice in ("", "y", "yes"):
                manager.download_all(results["results"])

        elif choice == "5":
            downloaded = manager.get_downloaded()
            print(f"\n已下载素材 ({len(downloaded)}):")
            for i, item in enumerate(downloaded[:15], 1):
                print(f"   {i}. [{item['type']}] {item['title']} - {item['platform']}")
            if len(downloaded) > 15:
                print(f"   ... 还有 {len(downloaded) - 15} 个")

        elif choice == "6":
            favorites = manager.get_favorites()
            print(f"\n收藏素材 ({len(favorites)}):")
            for i, item in enumerate(favorites[:15], 1):
                print(f"   {i}. [{item['type']}] {item['title']} - {item['platform']}")

        elif choice == "7":
            downloaded = manager.get_downloaded("video")
            if not downloaded:
                print("没有已下载的视频素材")
                continue
            print("\n选择视频进行增强:")
            for i, item in enumerate(downloaded[:10], 1):
                print(f"   {i}. {item['title']}")
            idx = int(input("请输入序号: ").strip()) - 1
            if 0 <= idx < len(downloaded):
                result = manager.enhance_video(downloaded[idx]["download_path"])
                if result["success"]:
                    print(f"✅ 增强完成: {result['output_path']}")
                else:
                    print(f"❌ 增强失败: {result['error']}")

        elif choice == "8":
            downloaded = manager.get_downloaded("video")
            if not downloaded:
                print("没有已下载的视频素材")
                continue
            print("\n选择视频进行调色:")
            for i, item in enumerate(downloaded[:10], 1):
                print(f"   {i}. {item['title']}")
            idx = int(input("请输入序号: ").strip()) - 1
            if 0 <= idx < len(downloaded):
                result = manager.color_grade_video(downloaded[idx]["download_path"])
                if result["success"]:
                    print(f"✅ 调色完成: {result['output_path']}")
                else:
                    print(f"❌ 调色失败: {result['error']}")

        elif choice == "9":
            downloaded = manager.get_downloaded()
            if not downloaded:
                print("没有已下载的素材")
                continue
            print("\n选择素材导入AE:")
            for i, item in enumerate(downloaded[:10], 1):
                print(f"   {i}. [{item['type']}] {item['title']}")
            idx = int(input("请输入序号: ").strip()) - 1
            if 0 <= idx < len(downloaded):
                result = manager.import_to_ae(downloaded[idx]["download_path"])
                if result["success"]:
                    print(f"✅ 已导入AE合成: {result['composition']}")
                else:
                    print(f"❌ 导入失败: {result['error']}")

        elif choice == "10":
            downloaded = manager.get_downloaded("video")
            if not downloaded:
                print("没有已下载的视频素材")
                continue
            print("\n选择视频进行完整后期工作流:")
            for i, item in enumerate(downloaded[:10], 1):
                print(f"   {i}. {item['title']}")
            idx = int(input("请输入序号: ").strip()) - 1
            if 0 <= idx < len(downloaded):
                workflow = input("选择工作流 [default/video/full/color/ae]: ").strip() or "default"
                result = manager.process_workflow(downloaded[idx]["download_path"], workflow)
                if result["success"]:
                    print("✅ 工作流完成")
                else:
                    print("部分步骤失败")

        elif choice == "11":
            url = input("输入下载链接: ").strip()
            media_type = input("媒体类型 [video/image/audio] (默认video): ").strip() or "video"
            title = input("自定义标题 (可选): ").strip()
            result = manager.download_from_url(url, title=title or None, media_type=media_type)
            if result["success"]:
                print(f"✅ 下载完成: {result['path']}")
            else:
                print(f"❌ 下载失败: {result['message']}")

        elif choice == "12":
            url = input("输入URL: ").strip()
            info = manager.analyze_url(url)
            print("\nURL分析结果:")
            print(f"   平台: {info['platform']}")
            print(f"   媒体类型: {info['media_type']}")
            print(f"   域名: {info['domain']}")
            if info["video_id"]:
                print(f"   视频ID: {info['video_id']}")
            if info["author"]:
                print(f"   作者ID: {info['author']}")

        elif choice == "13":
            platform = input("平台 [bilibili/youtube]: ").strip().lower()
            creator_id = input("创作者ID (UID/Channel ID): ").strip()
            result = manager.fetch_creator_info(platform, creator_id)
            if result["success"]:
                print("\n创作者信息:")
                print(f"   名称: {result['name']}")
                print(f"   签名: {result.get('description', '')}")
                print(f"   视频数: {result.get('video_count', 0)}")
                print(f"   粉丝数: {result.get('follower_count', 0)}")
            else:
                print(f"❌ 获取失败: {result['error']}")

        elif choice == "14":
            platform = input("平台 [bilibili]: ").strip().lower()
            creator_id = input("创作者UID: ").strip()
            limit = int(input("数量限制 (默认10): ").strip() or 10)
            result = manager.search_creator_videos(platform, creator_id, limit)
            if result["success"]:
                print(f"\n找到 {result['total']} 个视频:")
                for i, video in enumerate(result["results"], 1):
                    print(f"   {i}. {video['title']} ({video['duration']}秒)")
            else:
                print(f"❌ 获取失败: {result['error']}")

        elif choice == "15":
            print("退出...")
            break

        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    main()