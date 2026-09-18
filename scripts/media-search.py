import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_PATH = Path(__file__).parent / "config" / "media-config.json"

@dataclass
class MediaItem:
    name: str
    path: str
    type: str
    size: int
    duration: float = 0.0
    width: int = 0
    height: int = 0
    tags: list[str] = None
    created_at: datetime = None
    platform: str = ""
    url: str = ""
    audio_features: dict = None
    similarity_score: float = 0.0

    def to_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "size": self.size,
            "duration": round(self.duration, 2),
            "width": self.width,
            "height": self.height,
            "tags": self.tags or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "platform": self.platform,
            "url": self.url,
            "audio_features": self.audio_features,
            "similarity_score": round(self.similarity_score, 3)
        }

class MediaSearchEngine:
    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.video_extensions = self.config["download"]["video_formats"]
        self.audio_extensions = self.config["download"]["audio_only_formats"]
        self._cache = {}

    def scan_library(self, force_refresh: bool = False) -> list[MediaItem]:
        cache_key = "library_scan"
        if not force_refresh and cache_key in self._cache:
            return self._cache[cache_key]

        all_items = []

        for dir_key, dir_path in self.config["directories"].items():
            if not os.path.exists(dir_path):
                continue

            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    ext = file.split(".")[-1].lower()

                    if ext in self.video_extensions:
                        media_item = self._create_media_item(file, root, "video")
                    elif ext in self.audio_extensions:
                        media_item = self._create_media_item(file, root, "audio")
                    elif ext in ["jpg", "jpeg", "png", "gif", "bmp", "webp"]:
                        media_item = self._create_media_item(file, root, "image")
                    else:
                        continue

                    media_item.tags = self._extract_tags_from_path(root, file)
                    all_items.append(media_item)

        self._cache[cache_key] = all_items
        return all_items

    def search_by_keyword(self, keyword: str, media_type: str | None = None, 
                          max_results: int = 20) -> list[MediaItem]:
        all_items = self.scan_library()
        keyword_lower = keyword.lower()

        results = []
        for item in all_items:
            if media_type and item.type != media_type:
                continue

            match_score = 0
            if keyword_lower in item.name.lower():
                match_score += 5
            if keyword_lower in item.path.lower():
                match_score += 3
            if any(keyword_lower in tag.lower() for tag in (item.tags or [])):
                match_score += 2
            if item.audio_features:
                if keyword_lower in item.audio_features.get("mood", "").lower():
                    match_score += 4
                if keyword_lower in item.audio_features.get("genre", "").lower():
                    match_score += 3

            if match_score > 0:
                item.similarity_score = match_score / 17
                results.append(item)

        return sorted(results, key=lambda x: x.similarity_score, reverse=True)[:max_results]

    def search_by_duration(self, min_duration: float = 0, max_duration: float = float('inf'),
                          media_type: str | None = None) -> list[MediaItem]:
        all_items = self.scan_library()

        results = []
        for item in all_items:
            if media_type and item.type != media_type:
                continue

            if min_duration <= item.duration <= max_duration:
                results.append(item)

        return sorted(results, key=lambda x: x.duration)

    def search_by_mood(self, mood: str, media_type: str = "audio", 
                       max_results: int = 10) -> list[MediaItem]:
        all_items = self.scan_library()
        mood_lower = mood.lower()

        results = []
        for item in all_items:
            if item.type != media_type:
                continue

            if item.audio_features:
                item_mood = item.audio_features.get("mood", "").lower()
                mood_score = item.audio_features.get("mood_score", 0)

                if item_mood == mood_lower:
                    item.similarity_score = mood_score
                    results.append(item)

        return sorted(results, key=lambda x: x.similarity_score, reverse=True)[:max_results]

    def search_by_bpm(self, target_bpm: float, tolerance: float = 10, 
                      media_type: str = "audio", max_results: int = 10) -> list[MediaItem]:
        all_items = self.scan_library()

        results = []
        for item in all_items:
            if item.type != media_type:
                continue

            if item.audio_features:
                bpm = item.audio_features.get("bpm", 0)
                if abs(bpm - target_bpm) <= tolerance:
                    item.similarity_score = 1 - abs(bpm - target_bpm) / tolerance
                    results.append(item)

        return sorted(results, key=lambda x: x.similarity_score, reverse=True)[:max_results]

    def find_bgm_for_video(self, video_duration: float, mood: str | None = None,
                           target_bpm: float | None = None, max_results: int = 5) -> list[MediaItem]:
        bgm_dir = self.config["directories"]["bgm_library"]

        if not os.path.exists(bgm_dir):
            return []

        bgm_items = []
        for root, dirs, files in os.walk(bgm_dir):
            for file in files:
                ext = file.split(".")[-1].lower()
                if ext in self.audio_extensions:
                    item = self._create_media_item(file, root, "audio")
                    bgm_items.append(item)

        results = []
        for item in bgm_items:
            score = 0.0

            duration_diff = abs(item.duration - video_duration)
            if duration_diff <= video_duration * 0.3:
                score += 0.4
            elif duration_diff <= video_duration * 0.5:
                score += 0.2

            if item.audio_features:
                if mood and item.audio_features.get("mood") == mood:
                    score += 0.3

                if target_bpm:
                    bpm = item.audio_features.get("bpm", 0)
                    if abs(bpm - target_bpm) <= 15:
                        score += 0.3
                    elif abs(bpm - target_bpm) <= 30:
                        score += 0.15

            item.similarity_score = score
            if score > 0:
                results.append(item)

        return sorted(results, key=lambda x: x.similarity_score, reverse=True)[:max_results]

    def search_online(self, query: str, platform: str | None = None, 
                      max_results: int = 10) -> list[dict]:
        yt_dlp = self.config["tools"]["yt_dlp"]
        results = []

        search_platforms = {
            "youtube": "ytsearch",
            "bilibili": "bsearch",
            "douyin": "dysearch",
            "kuaishou": "ksearch"
        }

        selected_platforms = []
        if platform:
            if platform in search_platforms:
                selected_platforms = [(platform, search_platforms[platform])]
            else:
                return [{"error": f"不支持的平台: {platform}"}]
        else:
            selected_platforms = list(search_platforms.items())

        for platform_name, prefix in selected_platforms:
            try:
                cmd = [
                    yt_dlp,
                    f"{prefix}{max_results}:{query}",
                    "--dump-json",
                    "--no-warnings",
                    "--ignore-errors",
                    "--skip-download"
                ]

                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace"
                )

                if process.returncode == 0:
                    lines = process.stdout.strip().split("\n")
                    for line in lines:
                        if line.strip():
                            try:
                                info = json.loads(line)
                                results.append({
                                    "title": info.get("title", ""),
                                    "url": info.get("url", ""),
                                    "platform": platform_name,
                                    "duration": float(info.get("duration", 0)),
                                    "view_count": info.get("view_count", 0),
                                    "thumbnail": info.get("thumbnail", ""),
                                    "uploader": info.get("uploader", ""),
                                    "upload_date": info.get("upload_date", "")
                                })
                            except:
                                continue

            except Exception as e:
                continue

        return results[:max_results]

    def get_library_stats(self) -> dict:
        all_items = self.scan_library()

        stats = {
            "total": len(all_items),
            "videos": 0,
            "audios": 0,
            "images": 0,
            "total_size": 0,
            "avg_duration": 0,
            "mood_distribution": {},
            "genre_distribution": {}
        }

        durations = []
        for item in all_items:
            stats["total_size"] += item.size
            if item.type == "video":
                stats["videos"] += 1
                durations.append(item.duration)
            elif item.type == "audio":
                stats["audios"] += 1
                durations.append(item.duration)
                if item.audio_features:
                    mood = item.audio_features.get("mood", "unknown")
                    genre = item.audio_features.get("genre", "unknown")
                    stats["mood_distribution"][mood] = stats["mood_distribution"].get(mood, 0) + 1
                    stats["genre_distribution"][genre] = stats["genre_distribution"].get(genre, 0) + 1
            elif item.type == "image":
                stats["images"] += 1

        if durations:
            stats["avg_duration"] = round(sum(durations) / len(durations), 2)

        stats["total_size_human"] = self._format_size(stats["total_size"])

        return stats

    def _create_media_item(self, filename: str, root: str, media_type: str) -> MediaItem:
        full_path = os.path.join(root, filename)
        size = os.path.getsize(full_path)

        duration = 0
        width, height = 0, 0
        audio_features = None

        try:
            from ffmpeg_toolkit import FFmpegToolkit
            toolkit = FFmpegToolkit()
            info = toolkit.get_media_info(full_path)
            duration = info.get("duration", 0)
            streams = info.get("info", {}).get("streams", [])

            for stream in streams:
                if stream.get("codec_type") == "video":
                    width = stream.get("width", 0)
                    height = stream.get("height", 0)
                    break
        except:
            pass

        if media_type == "audio":
            try:
                from audio_analyzer import AudioAnalyzer
                analyzer = AudioAnalyzer()
                analysis = analyzer.analyze_audio(full_path)
                if analysis["success"]:
                    audio_features = analysis["features"]
            except:
                pass

        mtime = os.path.getmtime(full_path)
        created_at = datetime.fromtimestamp(mtime)

        platform = self._infer_platform_from_path(root)

        return MediaItem(
            name=filename,
            path=full_path,
            type=media_type,
            size=size,
            duration=duration,
            width=width,
            height=height,
            tags=[],
            created_at=created_at,
            platform=platform,
            url="",
            audio_features=audio_features,
            similarity_score=0.0
        )

    def _infer_platform_from_path(self, path: str) -> str:
        path_lower = path.lower()
        if "douyin" in path_lower or "tiktok" in path_lower:
            return "douyin"
        elif "bilibili" in path_lower or "b站" in path_lower:
            return "bilibili"
        elif "youtube" in path_lower:
            return "youtube"
        elif "kuaishou" in path_lower or "快手" in path_lower:
            return "kuaishou"
        else:
            return "local"

    def _extract_tags_from_path(self, root: str, filename: str) -> list[str]:
        tags = []

        parts = root.replace("\\", "/").split("/")
        for part in parts:
            if len(part) > 2 and not part.startswith("."):
                tags.append(part)

        name_without_ext = os.path.splitext(filename)[0]
        if "_" in name_without_ext:
            for part in name_without_ext.split("_"):
                if len(part) > 1 and part.isalpha():
                    tags.append(part.lower())

        return list(set(tags))

    def _format_size(self, bytes_size: int) -> str:
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 ** 2:
            return f"{bytes_size / 1024:.2f} KB"
        elif bytes_size < 1024 ** 3:
            return f"{bytes_size / (1024 ** 2):.2f} MB"
        else:
            return f"{bytes_size / (1024 ** 3):.2f} GB"

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()
            
            if input_data:
                request = json.loads(input_data)
                engine = MediaSearchEngine()
                
                func_name = request.get("func")
                params = request.get("params", {})
                
                func_map = {
                    "scan_library": engine.scan_library,
                    "search_by_keyword": engine.search_by_keyword,
                    "search_by_duration": engine.search_by_duration,
                    "search_by_mood": engine.search_by_mood,
                    "search_by_bpm": engine.search_by_bpm,
                    "find_bgm_for_video": engine.find_bgm_for_video,
                    "search_online": engine.search_online,
                    "get_library_stats": engine.get_library_stats
                }
                
                if func_name in func_map:
                    result = func_map[func_name](**params)
                    if isinstance(result, list):
                        result = [item.to_dict() if hasattr(item, 'to_dict') else item for item in result]
                        result = {"success": True, "results": result}
                    elif hasattr(result, 'to_dict'):
                        result = result.to_dict()
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}
                
                if isinstance(result, dict) and "success" not in result:
                    result = {"success": True, "data": result}
                
                print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return
    
    engine = MediaSearchEngine()

    print("素材库统计...")
    stats = engine.get_library_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    print("\n搜索 '高燃' 相关素材...")
    results = engine.search_by_keyword("高燃")
    for item in results:
        audio_info = ""
        if item.audio_features:
            audio_info = f" | BPM:{item.audio_features['bpm']} | 情绪:{item.audio_features['mood']}"
        print(f"  - {item.name} ({item.type}, {item.duration:.2f}s{audio_info})")

    print("\n在线搜索 'anime epic music'...")
    online_results = engine.search_online("anime epic music", platform="youtube", max_results=5)
    for item in online_results:
        print(f"  - {item['title']} ({item['platform']}, {item['duration']:.1f}s)")

if __name__ == "__main__":
    main()