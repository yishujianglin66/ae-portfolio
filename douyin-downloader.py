import subprocess
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

CONFIG_PATH = Path(__file__).parent / "config" / "media-config.json"

class DouyinDownloader:
    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.yt_dlp = self.config["tools"]["yt_dlp"]
        self._ensure_directories()

    def _ensure_directories(self):
        os.makedirs(self.config["directories"]["video_library"], exist_ok=True)
        os.makedirs(self.config["directories"]["bgm_library"], exist_ok=True)
        os.makedirs(os.path.dirname(self.config["platforms"]["douyin"]["cookie_path"]), exist_ok=True)

    def download_video(self, url: str, output_dir: Optional[str] = None,
                      audio_only: bool = False, watermark_free: bool = True) -> Dict:
        if output_dir is None:
            output_dir = self.config["directories"]["video_library"]
            if audio_only:
                output_dir = self.config["directories"]["bgm_library"]

        os.makedirs(output_dir, exist_ok=True)

        cmd = [
            self.yt_dlp,
            url,
            "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
            "--no-warnings",
            "--ignore-errors"
        ]

        if audio_only:
            cmd.extend(["-f", "ba/best", "--extract-audio", "--audio-format", "mp3"])
        elif watermark_free:
            cmd.extend(["-f", "best"])

        cookie_path = self.config["platforms"]["douyin"]["cookie_path"]
        if os.path.exists(cookie_path):
            cmd.extend(["--cookies", cookie_path])

        result = {
            "success": False,
            "url": url,
            "platform": "douyin",
            "audio_only": audio_only,
            "watermark_free": watermark_free,
            "output_dir": output_dir,
            "files": [],
            "error": None
        }

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config["download"]["timeout"],
                encoding="utf-8",
                errors="replace"
            )

            if process.returncode == 0:
                downloaded_files = []
                for f in os.listdir(output_dir):
                    if any(f.endswith(ext) for ext in ["mp4", "mp3", "m4a", "wav"]):
                        fpath = os.path.join(output_dir, f)
                        if os.path.getsize(fpath) > 0:
                            downloaded_files.append({
                                "name": f,
                                "path": fpath,
                                "size": os.path.getsize(fpath)
                            })

                result["success"] = True
                result["files"] = downloaded_files
            else:
                result["error"] = process.stderr[:500]

        except subprocess.TimeoutExpired:
            result["error"] = "下载超时"
        except Exception as e:
            result["error"] = str(e)

        return result

    def download_bgm(self, url: str) -> Dict:
        return self.download_video(url, audio_only=True)

    def search_and_download(self, keyword: str, max_results: int = 5,
                           audio_only: bool = False) -> List[Dict]:
        results = []

        cmd = [
            self.yt_dlp,
            f"dysearch{max_results}:{keyword}",
            "--dump-json",
            "--no-warnings",
            "--ignore-errors",
            "--skip-download"
        ]

        cookie_path = self.config["platforms"]["douyin"]["cookie_path"]
        if os.path.exists(cookie_path):
            cmd.extend(["--cookies", cookie_path])

        try:
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
                search_results = []
                for line in lines:
                    if line.strip():
                        try:
                            info = json.loads(line)
                            search_results.append({
                                "title": info.get("title", ""),
                                "url": info.get("url", ""),
                                "duration": float(info.get("duration", 0)),
                                "view_count": info.get("view_count", 0),
                                "thumbnail": info.get("thumbnail", "")
                            })
                        except:
                            continue

                for i, item in enumerate(search_results[:max_results]):
                    print(f"正在下载 [{i+1}/{max_results}]: {item['title']}")
                    download_result = self.download_video(item["url"], audio_only=audio_only)
                    download_result["search_info"] = item
                    results.append(download_result)
                    time.sleep(1)

        except Exception as e:
            results.append({"success": False, "error": str(e)})

        return results

    def download_user_videos(self, user_url: str, limit: int = 10,
                             audio_only: bool = False) -> List[Dict]:
        results = []

        cmd = [
            self.yt_dlp,
            user_url,
            "-o", os.path.join(self.config["directories"]["video_library"], "%(upload_date)s_%(title)s.%(ext)s"),
            "--playlist-end", str(limit),
            "--no-warnings",
            "--ignore-errors"
        ]

        if audio_only:
            cmd.extend(["-f", "ba/best", "--extract-audio", "--audio-format", "mp3"])

        cookie_path = self.config["platforms"]["douyin"]["cookie_path"]
        if os.path.exists(cookie_path):
            cmd.extend(["--cookies", cookie_path])

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config["download"]["timeout"] * 2,
                encoding="utf-8",
                errors="replace"
            )

            if process.returncode == 0:
                for f in os.listdir(self.config["directories"]["video_library"]):
                    if any(f.endswith(ext) for ext in ["mp4", "mp3"]):
                        fpath = os.path.join(self.config["directories"]["video_library"], f)
                        if os.path.getsize(fpath) > 0:
                            results.append({
                                "success": True,
                                "name": f,
                                "path": fpath
                            })
            else:
                results.append({"success": False, "error": process.stderr[:300]})

        except Exception as e:
            results.append({"success": False, "error": str(e)})

        return results

    def batch_extract_audio(self, video_directory: str = None) -> List[Dict]:
        if video_directory is None:
            video_directory = self.config["directories"]["video_library"]

        if not os.path.exists(video_directory):
            return [{"success": False, "error": "视频目录不存在"}]

        from ffmpeg_toolkit import FFmpegToolkit
        toolkit = FFmpegToolkit()
        bgm_dir = self.config["directories"]["bgm_library"]

        results = []
        for f in os.listdir(video_directory):
            if f.endswith((".mp4", ".mov", ".webm")):
                video_path = os.path.join(video_directory, f)
                result = toolkit.extract_audio(video_path, format="mp3")
                if result["success"]:
                    new_name = os.path.splitext(f)[0] + ".mp3"
                    new_path = os.path.join(bgm_dir, new_name)
                    if os.path.exists(result["output_file"]):
                        os.rename(result["output_file"], new_path)
                        result["output_file"] = new_path
                results.append(result)

        return results

    def extract_audio_from_douyin_video(self, video_path: str, output_dir: Optional[str] = None) -> Dict:
        from ffmpeg_toolkit import FFmpegToolkit

        if output_dir is None:
            output_dir = self.config["directories"]["bgm_library"]

        toolkit = FFmpegToolkit()
        return toolkit.extract_audio(video_path, output_file=None, format="mp3")

    def generate_cookie_template(self):
        cookie_path = self.config["platforms"]["douyin"]["cookie_path"]
        template = """# 抖音 Cookie 文件 - 使用 yt-dlp 的 Netscape 格式
# 使用方法：
# 1. 在浏览器中登录抖音网页版 (https://www.douyin.com)
# 2. 打开开发者工具 (F12) -> Application -> Cookies -> https://www.douyin.com
# 3. 导出所有 Cookie 并粘贴到下面（按 Netscape 格式）

# Netscape Cookie 格式：
# domain\tflag\tpath\tsecure\texpiration\tname\tvalue
"""

        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(template)

        return {"success": True, "cookie_path": cookie_path}

    def validate_cookie(self) -> Dict:
        cookie_path = self.config["platforms"]["douyin"]["cookie_path"]

        if not os.path.exists(cookie_path):
            return {"success": False, "error": "Cookie 文件不存在"}

        with open(cookie_path, "r", encoding="utf-8") as f:
            content = f.read()

        has_valid_cookie = len(content.strip()) > 100
        has_session_info = any(keyword in content.lower() for keyword in ["session", "sid", "ttwid"])

        return {
            "success": has_valid_cookie and has_session_info,
            "cookie_path": cookie_path,
            "has_session_info": has_session_info,
            "file_size": len(content)
        }

    def auto_manage_cookies(self):
        cookie_status = self.validate_cookie()

        if not cookie_status["success"]:
            print("Cookie 无效或不存在，生成模板...")
            self.generate_cookie_template()
            return {
                "action": "generated_template",
                "message": "Cookie 文件不存在或无效，已生成模板，请手动填写",
                "cookie_path": self.config["platforms"]["douyin"]["cookie_path"]
            }

        return {
            "action": "valid",
            "message": "Cookie 验证通过",
            "cookie_path": self.config["platforms"]["douyin"]["cookie_path"]
        }

    def download_trending_videos(self, count: int = 5, audio_only: bool = False) -> List[Dict]:
        trending_url = "https://www.douyin.com"

        cmd = [
            self.yt_dlp,
            trending_url,
            "--dump-json",
            "--no-warnings",
            "--ignore-errors",
            "--skip-download"
        ]

        cookie_path = self.config["platforms"]["douyin"]["cookie_path"]
        if os.path.exists(cookie_path):
            cmd.extend(["--cookies", cookie_path])

        try:
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
                trending_videos = []
                for line in lines[:count]:
                    if line.strip():
                        try:
                            info = json.loads(line)
                            trending_videos.append({
                                "title": info.get("title", ""),
                                "url": info.get("url", ""),
                                "duration": float(info.get("duration", 0)),
                                "view_count": info.get("view_count", 0)
                            })
                        except:
                            continue

                results = []
                for i, video in enumerate(trending_videos):
                    print(f"正在下载热门视频 [{i+1}/{len(trending_videos)}]: {video['title']}")
                    result = self.download_video(video["url"], audio_only=audio_only)
                    result["trending_rank"] = i + 1
                    results.append(result)

                return results

        except Exception as e:
            return [{"success": False, "error": str(e)}]
    
    def search_videos(self, keyword: str, count: int = 5) -> Dict:
        """搜索抖音视频（不下载）"""
        search_url = f"https://www.douyin.com/search/{keyword}"
        
        cmd = [
            self.yt_dlp,
            search_url,
            "--dump-json",
            "--no-warnings",
            "--ignore-errors",
            "--skip-download",
            "--playlist-end", str(count)
        ]

        cookie_path = self.config["platforms"]["douyin"]["cookie_path"]
        if os.path.exists(cookie_path):
            cmd.extend(["--cookies", cookie_path])

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )

            if process.returncode == 0:
                videos = []
                for line in process.stdout.strip().split("\n"):
                    if line.strip():
                        try:
                            info = json.loads(line)
                            videos.append({
                                "title": info.get("title", ""),
                                "url": info.get("webpage_url", ""),
                                "duration": float(info.get("duration", 0)),
                                "view_count": info.get("view_count", 0)
                            })
                        except:
                            continue
                return {"success": True, "videos": videos}
            else:
                return {"success": False, "error": process.stderr[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
                downloader = DouyinDownloader()

                func_name = request.get("func")
                params = request.get("params", {})

                func_map = {
                    "download_video": downloader.download_video,
                    "download_bgm": downloader.download_bgm,
                    "search_and_download": downloader.search_and_download,
                    "search_videos": downloader.search_videos,
                    "download_user_videos": downloader.download_user_videos,
                    "batch_extract_audio": downloader.batch_extract_audio,
                    "extract_audio_from_douyin_video": downloader.extract_audio_from_douyin_video,
                    "validate_cookie": downloader.validate_cookie,
                    "auto_manage_cookies": downloader.auto_manage_cookies,
                    "download_trending_videos": downloader.download_trending_videos
                }

                if func_name in func_map:
                    result = func_map[func_name](**params)
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}

                print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return

    downloader = DouyinDownloader()

    print("验证 Cookie...")
    cookie_status = downloader.validate_cookie()
    print(json.dumps(cookie_status, ensure_ascii=False, indent=2))

    if not cookie_status["success"]:
        print("\n生成 Cookie 模板...")
        downloader.generate_cookie_template()
        print("Cookie 模板已生成，请按说明填写")

    print("\n测试搜索下载功能...")
    search_results = downloader.search_and_download("高燃动漫", max_results=2)
    print(f"搜索下载完成，共 {len(search_results)} 个结果")

if __name__ == "__main__":
    main()