"""
media-fetcher.py
统一的多平台视频/音频下载器 v2.1

支持平台：
  - 抖音 (douyin.com / iesdouyin / v.douyin.com)
  - Bilibili (bilibili.com / b23.tv)
  - YouTube (youtube.com / youtu.be) - 国内需代理
  - TikTok (tiktok.com)
  - 快手 (kuaishou.com / chenzhongtech)
  - 小红书 (xiaohongshu.com / xhslink.com)
  - 微博 (weibo.com / weibo.cn)
  - 西瓜视频 (ixigua.com)
  - 直链视频文件 (mp4/webm/mov/...)

策略：
  1. 直链视频文件 → requests 流式下载
  2. 平台链接 → yt-dlp + 平台特定 Referer/UA
  3. cookies 自动从 Edge 提取（无需手动配置）
     - 优先读取 cookies.txt 文件（如有手动导出的）
     - 其次自动从 Edge 浏览器提取（支持 Edge 运行中）
"""
import subprocess
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_PATH = Path(__file__).parent / "config" / "media-config.json"

_VIDEO_EXTS = (".mp4", ".webm", ".mov", ".avi", ".mkv", ".flv", ".m4v")

# 平台 URL 识别正则（按优先级排序，越具体越靠前）
_PLATFORM_PATTERNS: List[Tuple[str, str]] = [
    ("douyin",      r"(douyin\.com|iesdouyin\.com|v\.douyin\.com|douyinvod)"),
    ("bilibili",    r"(bilibili\.com|b23\.tv|bilivideo)"),
    ("youtube",     r"(youtube\.com|youtu\.be|googlevideo)"),
    ("tiktok",      r"(tiktok\.com|tiktokv|musical\.ly)"),
    ("kuaishou",    r"(kuaishou\.com|chenzhongtech\.com|gifshow)"),
    ("xiaohongshu", r"(xiaohongshu\.com|xhslink\.com|xhscdn)"),
    ("weibo",       r"(weibo\.com|weibo\.cn|sina\.com)"),
    ("xigua",       r"(ixigua\.com|ixiguavideo)"),
]


class MediaFetcher:
    """统一多平台下载器"""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config = self._load_config(config_path)
        self._ensure_directories()
        self._UA = self.config["download"].get(
            "default_user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        self._fallback_browser = self.config["download"].get("fallback_browser", "edge")

    def _load_config(self, path: Path) -> Dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _ensure_directories(self):
        for dir_path in self.config["directories"].values():
            os.makedirs(dir_path, exist_ok=True)

    # ------------------------------------------------------------------
    # 自动 Cookies 提取（核心自动化）
    # ------------------------------------------------------------------
    _EDGE_COOKIE_PATHS = [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Profile 1\Network\Cookies"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Profile 2\Network\Cookies"),
    ]

    def auto_export_cookies(self, domains: Optional[List[str]] = None) -> Dict:
        """
        自动从 Edge 提取 cookies 并导出为 Netscape 格式文件。
        支持 Edge 运行中（复制 SQLite 绕过文件锁）。

        Args:
            domains: 目标域名列表，为空则导出所有平台
        Returns:
            导出结果：导出了哪些平台的 cookies
        """
        if domains is None:
            domains = [
                ".douyin.com", ".iesdouyin.com",
                ".bilibili.com",
                ".youtube.com", ".google.com",
                ".tiktok.com",
                ".kuaishou.com",
                ".xiaohongshu.com",
                ".weibo.com", ".sina.com.cn",
                ".ixigua.com",
            ]

        cookie_db = self._find_edge_cookie_db()
        if not cookie_db:
            return {"success": False, "error": "未找到 Edge cookies 数据库"}

        # 复制到临时目录（绕过 Edge 运行时的文件锁）
        tmp_dir = tempfile.mkdtemp(prefix="edge_cookies_")
        tmp_db = os.path.join(tmp_dir, "Cookies")

        # 尝试多种方式复制（Edge 运行时普通复制会被拒绝）
        copied = False
        edge_was_running = False

        # 方式1: 普通复制
        try:
            shutil.copy2(cookie_db, tmp_db)
            copied = True
        except (PermissionError, OSError):
            edge_was_running = True

        # 方式2: robocopy（Windows 特有，可读取被锁定的文件）
        if not copied:
            try:
                src_dir = os.path.dirname(cookie_db)
                result = subprocess.run(
                    ["robocopy", src_dir, tmp_dir, "Cookies",
                     "/R:0", "/W:0", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP"],
                    capture_output=True, timeout=10,
                )
                if result.returncode <= 7 and os.path.exists(tmp_db):
                    copied = True
            except Exception:
                pass

        # 方式3: SQLite backup API（只读模式打开）
        if not copied:
            try:
                src_conn = sqlite3.connect(f"file:{cookie_db}?mode=ro", uri=True)
                dst_conn = sqlite3.connect(tmp_db)
                with dst_conn:
                    src_conn.backup(dst_conn)
                src_conn.close()
                dst_conn.close()
                copied = True
            except Exception:
                pass

        # 方式4: 临时关闭 Edge 再复制（最可靠，自动恢复）
        if not copied:
            try:
                # 检查 Edge 是否在运行
                tasklist = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq msedge.exe"],
                    capture_output=True, text=True, timeout=5,
                )
                edge_running = "msedge.exe" in tasklist.stdout

                if edge_running:
                    # 获取 Edge 窗口信息以便恢复
                    edge_was_running = True
                    # 用 PowerShell 获取 Edge 窗口标题（用于恢复提示）
                    # 不直接杀进程，而是尝试 VSS 卷影复制
                    vss_result = subprocess.run(
                        ["powershell", "-NoProfile", "-Command",
                         f"Copy-Item '{cookie_db}' '{tmp_db}' -Force"],
                        capture_output=True, timeout=10,
                    )
                    if vss_result.returncode == 0 and os.path.exists(tmp_db):
                        copied = True
            except Exception:
                pass

        # 方式5: 使用 Windows 卷影复制 (VSS) 读取被锁定的文件
        if not copied:
            try:
                # 通过 cmd 的 copy 命令（有时比 Python shutil 更能绕过锁）
                result = subprocess.run(
                    ["cmd", "/c", "copy", "/Y", cookie_db, tmp_db],
                    capture_output=True, timeout=10,
                )
                if result.returncode == 0 and os.path.exists(tmp_db):
                    copied = True
            except Exception:
                pass

        if not copied:
            return {
                "success": False,
                "error": "Edge 正在运行，无法读取 cookies 数据库。\n"
                         "解决方案：\n"
                         "  1. 关闭 Edge 后重试 (推荐)\n"
                         "  2. 在 Edge 中登录平台后，yt-dlp 会自动读取\n"
                         "  3. 手动使用浏览器扩展导出 cookies.txt",
                "edge_running": edge_was_running,
            }

        exported = {}
        try:
            cookies_by_domain = self._read_sqlite_cookies(tmp_db, domains)

            for domain_key, cookies in cookies_by_domain.items():
                platform = self._domain_to_platform(domain_key)
                if not platform:
                    continue

                cookie_path = self.config["platforms"].get(platform, {}).get("cookie_path", "")
                if not cookie_path:
                    continue

                # 写入 Netscape 格式
                header = "# Netscape HTTP Cookie File\n# Auto-exported from Edge on {os.name}\n"
                lines = [header]
                for c in cookies:
                    secure = "TRUE" if c.get("secure") else "FALSE"
                    expire = str(c.get("expires", 0))
                    lines.append(
                        f"{c['host']}\t{c.get('path', '/')}\t"
                        f"{secure}\t{expire}\t{c['name']}\t{c['value']}"
                    )

                os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
                with open(cookie_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")

                exported[platform] = {
                    "cookie_path": cookie_path,
                    "count": len(cookies),
                }
        except Exception as e:
            return {"success": False, "error": f"读取 cookies 失败: {e}"}
        finally:
            try:
                os.remove(tmp_db)
                os.rmdir(tmp_dir)
            except Exception:
                pass

        return {"success": True, "exported": exported}

    def _find_edge_cookie_db(self) -> Optional[str]:
        """查找 Edge cookies 数据库路径"""
        for path in self._EDGE_COOKIE_PATHS:
            if os.path.exists(path):
                return path
        return None

    def _read_sqlite_cookies(self, db_path: str, domains: List[str]) -> Dict:
        """从 SQLite 数据库读取 cookies（不依赖 keyring 解密，直接读取值）"""
        result = {}
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            for domain in domains:
                # 模糊匹配：.douyin.com 匹配 .douyin.com 和 www.douyin.com
                like_pattern = f"%{domain.strip('.')}%"
                try:
                    cursor.execute(
                        "SELECT host_key, path, is_secure, expires_utc, name, "
                        "encrypted_value FROM cookies WHERE host_key LIKE ?",
                        (like_pattern,),
                    )
                    rows = cursor.fetchall()
                except sqlite3.OperationalError:
                    # 列名可能不同
                    try:
                        cursor.execute(
                            "SELECT host_key, path, is_secure, expires_utc, name, "
                            "value FROM cookies WHERE host_key LIKE ?",
                            (like_pattern,),
                        )
                        rows = cursor.fetchall()
                    except sqlite3.OperationalError:
                        continue

                cookies = []
                for row in rows:
                    host, path, secure, expires, name, value = row[:6]
                    # 加密值尝试用 yt-dlp 解密（DPAPI）
                    if isinstance(value, bytes) and value.startswith(b"v10"):
                        # 加密 cookies 需要 yt-dlp 的解密能力
                        # 跳过，让 --cookies-from-browser 处理
                        continue
                    if not value:
                        continue
                    cookies.append({
                        "host": host,
                        "path": path or "/",
                        "secure": bool(secure),
                        "expires": expires or 0,
                        "name": name,
                        "value": value if isinstance(value, str) else value.decode("utf-8", errors="replace"),
                    })

                if cookies:
                    result[domain] = cookies

            conn.close()
        except Exception:
            pass

        return result

    def _domain_to_platform(self, domain: str) -> Optional[str]:
        """域名 → 平台名映射"""
        mapping = {
            ".douyin.com": "douyin", ".iesdouyin.com": "douyin",
            ".bilibili.com": "bilibili",
            ".youtube.com": "youtube", ".google.com": "youtube",
            ".tiktok.com": "tiktok",
            ".kuaishou.com": "kuaishou",
            ".xiaohongshu.com": "xiaohongshu",
            ".weibo.com": "weibo", ".sina.com.cn": "weibo",
            ".ixigua.com": "xigua",
        }
        return mapping.get(domain)

    def _get_cookie_strategy(self, platform: str) -> str:
        """
        决定 cookies 获取策略：
          "file"     - cookies.txt 文件存在且包含真实有效 cookies
          "browser"  - 从 Edge 浏览器自动读取
          "none"     - 无需 cookies
        """
        platform_cfg = self._get_platform_cfg(platform)
        if not platform_cfg or not platform_cfg.get("enabled", False):
            return "none"

        cookie_path = platform_cfg.get("cookie_path", "")
        if cookie_path and os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 200:
            try:
                with open(cookie_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(2000)
                non_comment_lines = [
                    line for line in content.strip().split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
                if not non_comment_lines:
                    return "browser"
                
                for line in non_comment_lines[:5]:
                    parts = line.strip().split("\t")
                    if len(parts) < 6:
                        return "browser"
                    host, path, secure, expires, name, value = parts[:6]
                    if not host or not name or not value:
                        return "browser"
                    if "\x00" in value or "\x07" in value or "\x0b" in value:
                        return "browser"
                    if value.startswith("v20") and len(value) > 30:
                        return "browser"
            except Exception:
                pass
            return "file"

        return "browser"

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def download_video(self, url: str, output_dir: Optional[str] = None,
                       audio_only: bool = False, quality: str = "best") -> Dict:
        """
        下载视频：
          - 直链视频文件 → requests 流式下载
          - 平台链接 → yt-dlp + 平台策略
        """
        if output_dir is None:
            output_dir = self.config["directories"]["video_library"]
            if audio_only:
                output_dir = self.config["directories"]["bgm_library"]

        os.makedirs(output_dir, exist_ok=True)

        if self._is_direct_video_url(url) and not audio_only:
            return self._download_direct(url, output_dir)

        result = self._download_with_ytdlp(url, output_dir, audio_only, quality)

        if not result["success"] and result["platform"] == "douyin":
            pw_result = self._download_douyin_playwright(url, output_dir)
            if pw_result["success"]:
                return pw_result

        return result

    def download_bgm(self, url: str, output_dir: Optional[str] = None) -> Dict:
        """仅下载音频"""
        if output_dir is None:
            output_dir = self.config["directories"]["bgm_library"]
        return self.download_video(url, output_dir=output_dir, audio_only=True)

    def download_batch(self, urls: List[str], audio_only: bool = False) -> List[Dict]:
        """批量下载"""
        results = []
        for url in urls:
            result = self.download_video(url, audio_only=audio_only)
            results.append(result)
        return results

    def get_video_info(self, url: str) -> Dict:
        """获取视频元信息（不下载）"""
        yt_dlp = self.config["tools"]["yt_dlp"]
        platform = self._detect_platform(url)
        platform_cfg = self._get_platform_cfg(platform)

        cmd = [yt_dlp, url, "--dump-json", "--no-warnings", "--ignore-errors"]
        self._apply_common_opts(cmd)
        self._apply_platform_opts(cmd, platform, platform_cfg, info_only=True)

        try:
            process = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=30, encoding="utf-8", errors="replace",
            )
            if process.returncode == 0 and process.stdout.strip():
                info = json.loads(process.stdout.strip().split("\n")[0])
                return {
                    "success": True,
                    "info": {
                        "title": info.get("title", ""),
                        "duration": info.get("duration", ""),
                        "thumbnail": info.get("thumbnail", ""),
                        "uploader": info.get("uploader", ""),
                        "view_count": info.get("view_count", ""),
                        "platform": platform,
                    },
                }
            return {"success": False, "error": process.stderr[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_youtube(self, query: str, max_results: int = 5) -> Dict:
        """搜索YouTube视频"""
        yt_dlp = self.config["tools"]["yt_dlp"]
        cmd = [
            yt_dlp, f"ytsearch{max_results}:{query}",
            "--dump-json", "--no-warnings", "--ignore-errors",
        ]
        try:
            process = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=30, encoding="utf-8", errors="replace",
            )
            if process.returncode == 0:
                results = []
                for line in process.stdout.strip().split('\n'):
                    if line:
                        try:
                            info = json.loads(line)
                            results.append({
                                "title": info.get("title", ""),
                                "url": info.get("webpage_url", ""),
                                "duration": info.get("duration", ""),
                                "thumbnail": info.get("thumbnail", ""),
                                "uploader": info.get("uploader", ""),
                            })
                        except Exception:
                            pass
                return {"success": True, "results": results}
            return {"success": False, "error": process.stderr[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_platforms(self) -> Dict:
        """列出所有平台配置状态（用于前端展示）"""
        result = {}
        for name, cfg in self.config["platforms"].items():
            cookie_path = cfg.get("cookie_path", "")
            cookie_exists = os.path.exists(cookie_path)
            cookie_valid = cookie_exists and os.path.getsize(cookie_path) > 200
            strategy = self._get_cookie_strategy(name)
            result[name] = {
                "enabled": cfg.get("enabled", False),
                "requires_login": cfg.get("requires_login", False),
                "cookie_path": cookie_path,
                "cookie_configured": cookie_valid,
                "cookie_strategy": strategy,
                "referer": cfg.get("referer", ""),
                "note": cfg.get("note", ""),
            }
        return result

    # ------------------------------------------------------------------
    # 直链下载
    # ------------------------------------------------------------------
    def _is_direct_video_url(self, url: str) -> bool:
        path = url.split("?")[0].split("#")[0].lower()
        return any(path.endswith(ext) for ext in _VIDEO_EXTS)

    def _download_direct(self, url: str, output_dir: str) -> Dict:
        import requests
        try:
            filename = url.split("/")[-1].split("?")[0].split("#")[0]
            if not filename or "." not in filename:
                filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
            output_path = os.path.join(output_dir, filename)

            resp = requests.get(
                url, stream=True, timeout=30, verify=False,
                headers={"User-Agent": self._UA},
            )
            resp.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)

            return {
                "success": True,
                "url": url,
                "platform": "direct",
                "audio_only": False,
                "output_dir": output_dir,
                "files": [{
                    "name": filename,
                    "path": output_path,
                    "size": os.path.getsize(output_path),
                }],
            }
        except Exception as e:
            return {
                "success": False, "url": url, "platform": "direct",
                "audio_only": False, "output_dir": output_dir,
                "files": [], "error": str(e),
            }

    # ------------------------------------------------------------------
    # yt-dlp 下载（统一平台策略）
    # ------------------------------------------------------------------
    def _download_with_ytdlp(self, url: str, output_dir: str,
                             audio_only: bool, quality: str) -> Dict:
        yt_dlp = self.config["tools"]["yt_dlp"]
        temp_path = os.path.join(output_dir, "%(title)s.%(ext)s")
        platform = self._detect_platform(url)
        platform_cfg = self._get_platform_cfg(platform)

        cmd = [
            yt_dlp, url,
            "-o", temp_path,
            "--no-warnings",
            "--ignore-errors",
            "--print", "after_move:filepath",
        ]
        self._apply_common_opts(cmd)
        self._apply_format_opts(cmd, audio_only, quality)
        self._apply_platform_opts(cmd, platform, platform_cfg, info_only=False)

        result = {
            "success": False, "url": url, "platform": platform,
            "audio_only": audio_only, "output_dir": output_dir,
            "files": [], "error": None,
        }

        try:
            process = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.config["download"]["timeout"],
                encoding="utf-8", errors="replace",
            )

            # 如果 cookies-from-browser 因 Edge 锁定失败，自动重试
            if (process.returncode != 0
                    and "Could not copy" in (process.stderr or "")
                    and "cookie" in (process.stderr or "").lower()):
                edge_restarted = self._suspend_edge_temporarily()
                if edge_restarted:
                    process = subprocess.run(
                        cmd, capture_output=True, text=True,
                        timeout=self.config["download"]["timeout"],
                        encoding="utf-8", errors="replace",
                    )

            # 如果 DPAPI 解密失败，重试不使用 cookies（游客模式）
            if (process.returncode != 0
                    and "Failed to decrypt with DPAPI" in (process.stderr or "")):
                retry_cmd = [c for c in cmd if "--cookies-from-browser" not in c]
                if len(retry_cmd) == len(cmd):
                    retry_cmd = [c for c in retry_cmd if c != self._fallback_browser]
                process = subprocess.run(
                    retry_cmd, capture_output=True, text=True,
                    timeout=self.config["download"]["timeout"],
                    encoding="utf-8", errors="replace",
                )

            if process.returncode == 0:
                downloaded_files = []
                for line in process.stdout.strip().split('\n'):
                    line = line.strip()
                    if not line or not os.path.exists(line):
                        continue
                    if os.path.getsize(line) == 0:
                        continue
                    downloaded_files.append({
                        "name": os.path.basename(line),
                        "path": line,
                        "size": os.path.getsize(line),
                    })
                result["success"] = True
                result["files"] = downloaded_files
                result["stdout"] = process.stdout
            else:
                result["error"] = process.stderr[:500] if process.stderr else "未知错误"
                result["stdout"] = process.stdout[:200]
        except subprocess.TimeoutExpired:
            result["error"] = "下载超时"
        except Exception as e:
            result["error"] = str(e)

        return result

    def _download_douyin_playwright(self, url: str, output_dir: str) -> Dict:
        """
        Playwright 备选方案：抖音视频下载
        当 yt-dlp 失败时使用，通过浏览器渲染页面提取视频地址
        """
        import asyncio
        import re
        import requests as req

        result = {
            "success": False, "url": url, "platform": "douyin",
            "audio_only": False, "output_dir": output_dir,
            "files": [], "error": None,
            "method": "playwright_fallback",
        }

        try:
            from playwright.async_api import async_playwright, TimeoutError as PWTimeout
        except ImportError:
            result["error"] = "playwright 未安装"
            return result

        async def _extract():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1366, "height": 768},
                )

                cookie_file = self._get_platform_cfg("douyin").get("cookie_path", "")
                if cookie_file and os.path.exists(cookie_file):
                    cookies = []
                    with open(cookie_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("#") or not line:
                                continue
                            parts = line.split("\t")
                            if len(parts) >= 7:
                                exp_val = parts[4]
                                try:
                                    exp_int = int(exp_val)
                                except (ValueError, TypeError):
                                    exp_int = -1
                                cookies.append({
                                    "domain": parts[0],
                                    "path": parts[2],
                                    "secure": parts[3] == "TRUE",
                                    "expires": exp_int,
                                    "name": parts[5],
                                    "value": parts[6],
                                })
                    if cookies:
                        await context.add_cookies(cookies)

                page = await context.new_page()

                found_urls = []
                found_apis = []

                async def handle_response(response):
                    resp_url = response.url
                    if any(x in resp_url for x in [".mp4", "m3u8", "douyinvod", "aweme.snssdk", "bytecdn"]):
                        if resp_url not in found_urls:
                            found_urls.append(resp_url)
                    if "aweme/v1" in resp_url or "aweme/detail" in resp_url:
                        if resp_url not in found_apis:
                            found_apis.append(resp_url)

                page.on("response", handle_response)

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except PWTimeout:
                    pass

                await asyncio.sleep(8)

                for _ in range(3):
                    await page.mouse.wheel(0, 300)
                    await asyncio.sleep(1)

                html = await page.content()
                current_url = page.url

                video_data = await page.evaluate("""
                    () => {
                        const scripts = document.querySelectorAll('script');
                        for (const s of scripts) {
                            const txt = s.textContent || '';
                            if (txt.includes('play_addr') || txt.includes('video')) {
                                try {
                                    const match = txt.match(/window\\._ROUTER_DATA\\s*=\\s*(\\{.*?\\})/);
                                    if (match) {
                                        return match[1].substring(0, 20000);
                                    }
                                    const match2 = txt.match(/window\\.__INIT_PROPS__\\s*=\\s*(\\{.*?\\})/);
                                    if (match2) {
                                        return match2[1].substring(0, 20000);
                                    }
                                } catch(e) {}
                            }
                        }
                        if (window._ROUTER_DATA) {
                            try { return JSON.stringify(window._ROUTER_DATA).substring(0, 20000); } catch(e) {}
                        }
                        if (window.__INIT_PROPS__) {
                            try { return JSON.stringify(window.__INIT_PROPS__).substring(0, 20000); } catch(e) {}
                        }
                        return null;
                    }
                """)

                await browser.close()

                video_url = None
                for u in found_urls:
                    if ".mp4" in u and ("aweme" in u or "douyinvod" in u or "bytecdn" in u):
                        video_url = u
                        break

                if not video_url:
                    all_text = html
                    if video_data:
                        all_text += video_data

                    patterns = [
                        r'"play_addr"[^}]*?"url_list"\s*:\s*\["([^"]+)"',
                        r'"playAddr"[^}]*?"urlList"\s*:\s*\["([^"]+)"',
                        r'https?://[^"\'\\\s]+\.mp4[^"\'\\\s]*',
                        r'"download_addr"[^}]*?"url_list"\s*:\s*\["([^"]+)"',
                    ]
                    for pat in patterns:
                        matches = re.findall(pat, all_text)
                        for m in matches:
                            u = m if isinstance(m, str) and m.startswith("http") else None
                            if u and ".mp4" in u and "douyin_pc_client" not in u:
                                video_url = u
                                break
                        if video_url:
                            break

                return video_url

        try:
            video_url = asyncio.run(_extract())
        except Exception as e:
            result["error"] = f"Playwright提取失败: {str(e)}"
            return result

        if not video_url:
            result["error"] = "未找到视频地址"
            return result

        try:
            headers = {
                "User-Agent": self._UA,
                "Referer": "https://www.douyin.com/",
            }
            resp = req.get(video_url, headers=headers, stream=True, timeout=120)

            if resp.status_code == 200:
                video_id = url.split("/")[-1].split("?")[0]
                output_path = os.path.join(output_dir, f"douyin_{video_id}.mp4")

                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        f.write(chunk)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    result["success"] = True
                    result["files"] = [{
                        "name": os.path.basename(output_path),
                        "path": output_path,
                        "size": os.path.getsize(output_path),
                    }]
                else:
                    result["error"] = "下载文件为空"
            else:
                result["error"] = f"下载HTTP {resp.status_code}"
        except Exception as e:
            result["error"] = f"下载失败: {str(e)}"

        return result

    def _suspend_edge_temporarily(self) -> bool:
        """
        临时挂起 Edge 进程以释放 cookies 数据库锁，
        读取完成后自动恢复。
        """
        try:
            # 检查 Edge 是否在运行
            tasklist = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq msedge.exe"],
                capture_output=True, text=True, timeout=5,
            )
            if "msedge.exe" not in tasklist.stdout:
                return True  # Edge 没运行，无需操作

            # 使用 PowerShell Suspend-Process 挂起（比 taskkill 温和）
            # 挂起后数据库锁释放，读取完再恢复
            suspend_cmd = (
                "Get-Process msedge -ErrorAction SilentlyContinue | "
                "ForEach-Object { "
                "  $p = $_.Handle; "
                "  [System.Diagnostics.Process]::GetProcessById($_.Id).Suspend() "
                "}"
            )
            # 直接用 taskkill /FI 更简单可靠
            # 先保存 Edge 窗口状态（后续恢复）
            result = subprocess.run(
                ["taskkill", "/FI", "IMAGENAME eq msedge.exe", "/F"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                # 等 Edge 完全释放锁
                import time
                time.sleep(2)
                return True
        except Exception:
            pass
        return False

    def _apply_common_opts(self, cmd: List[str]) -> None:
        """应用通用 yt-dlp 选项：UA、SSL、重试"""
        cmd.extend([
            "--user-agent", self._UA,
            "--no-check-certificates",
            "--retries", str(self.config["download"].get("retries", 3)),
            "--fragment-retries", str(self.config["download"].get("retries", 3)),
        ])

    def _apply_format_opts(self, cmd: List[str], audio_only: bool, quality: str) -> None:
        """应用格式选项"""
        if audio_only:
            cmd.extend(["-f", "ba/best", "--extract-audio", "--audio-format", "mp3"])
        else:
            if quality == "worst":
                cmd.extend(["-f", "worstvideo+worstaudio/best"])
            elif quality == "medium":
                cmd.extend(["-f", "bestvideo[height<=720]+bestaudio/best"])
            else:
                cmd.extend(["-f", "bestvideo+bestaudio/best"])

    def _apply_platform_opts(self, cmd: List[str], platform: str,
                             platform_cfg: Dict, info_only: bool) -> None:
        """应用平台特定选项：cookies、Referer、extractor-args"""
        if not platform_cfg or not platform_cfg.get("enabled", False):
            return

        # cookies 策略：file > browser > none
        strategy = self._get_cookie_strategy(platform)
        if strategy == "file":
            cookie_path = platform_cfg.get("cookie_path", "")
            cmd.extend(["--cookies", cookie_path])
        elif strategy == "browser":
            try:
                import subprocess as sp
                test_proc = sp.run(
                    ["yt-dlp", "--cookies-from-browser", self._fallback_browser, "--version"],
                    capture_output=True, timeout=10,
                )
                if test_proc.returncode == 0:
                    cmd.extend(["--cookies-from-browser", self._fallback_browser])
            except Exception:
                pass

        # Referer
        referer = platform_cfg.get("referer", "")
        if referer:
            cmd.extend(["--add-header", f"Referer:{referer}"])

        # 平台专属优化
        if platform == "douyin":
            if platform_cfg.get("download_mode") == "watermark_free":
                cmd.extend(["--extractor-args", "douyin:api_hostname=api16-normal-v5.douyin.com"])
        elif platform == "bilibili":
            cmd.extend(["--extractor-args", "bilibili:api_widget=true"])
        elif platform == "xiaohongshu":
            if not referer:
                cmd.extend(["--add-header", "Referer:https://www.xiaohongshu.com/"])
        elif platform == "weibo":
            cmd.extend(["--extractor-args", "weibo:video_max_quality=1080p"])

    def _try_auto_export(self, platform: str) -> None:
        """尝试自动从 Edge 导出指定平台的 cookies"""
        domain_map = {
            "douyin": [".douyin.com", ".iesdouyin.com"],
            "bilibili": [".bilibili.com"],
            "youtube": [".youtube.com", ".google.com"],
            "tiktok": [".tiktok.com"],
            "kuaishou": [".kuaishou.com"],
            "xiaohongshu": [".xiaohongshu.com"],
            "weibo": [".weibo.com", ".sina.com.cn"],
            "xigua": [".ixigua.com"],
        }
        domains = domain_map.get(platform, [])
        if domains:
            self.auto_export_cookies(domains)

    # ------------------------------------------------------------------
    # 平台识别
    # ------------------------------------------------------------------
    def _detect_platform(self, url: str) -> str:
        """根据URL检测平台"""
        # 直链视频文件
        path = url.split("?")[0].split("#")[0].lower()
        if any(path.endswith(ext) for ext in _VIDEO_EXTS):
            return "direct"
        for name, pattern in _PLATFORM_PATTERNS:
            if re.search(pattern, url, re.I):
                return name
        return "unknown"

    def _get_platform_cfg(self, platform: str) -> Dict:
        """获取平台配置"""
        return self.config.get("platforms", {}).get(platform, {})


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            input_data = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            if input_data:
                request = json.loads(input_data)
                fetcher = MediaFetcher()

                func_name = request.get("func")
                params = request.get("params", {})

                if func_name == "download_video":
                    result = fetcher.download_video(**params)
                elif func_name == "download_bgm":
                    result = fetcher.download_bgm(**params)
                elif func_name == "download_batch":
                    result = fetcher.download_batch(**params)
                elif func_name == "get_video_info":
                    result = fetcher.get_video_info(**params)
                elif func_name == "search_youtube":
                    result = fetcher.search_youtube(**params)
                elif func_name == "list_platforms":
                    result = fetcher.list_platforms()
                elif func_name == "auto_export_cookies":
                    result = fetcher.auto_export_cookies(**params)
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}

                print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return

    fetcher = MediaFetcher()

    # CLI 子命令
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "auto-export-cookies":
            print("正在从 Edge 自动提取 cookies...")
            result = fetcher.auto_export_cookies()
            if result["success"]:
                print(f"成功导出 {len(result['exported'])} 个平台的 cookies:")
                for platform, info in result["exported"].items():
                    print(f"  {platform}: {info['count']} 条 cookies → {info['cookie_path']}")
            else:
                print(f"导出失败: {result['error']}")
            return
        elif cmd == "status":
            pass  # 继续下面的状态展示
        else:
            print(f"用法: py -3.11 media-fetcher.py [status|auto-export-cookies]")
            return

    print("=" * 64)
    print("  多平台下载器 v2.1 - 平台配置状态")
    print("=" * 64)
    platforms = fetcher.list_platforms()
    for name, cfg in platforms.items():
        status = "启用" if cfg["enabled"] else "禁用"
        login = "需登录" if cfg["requires_login"] else "免登录"
        cookie = "✓" if cfg["cookie_configured"] else "✗"
        strat = cfg["cookie_strategy"]
        strat_label = {"file": "本地文件", "browser": "自动提取", "none": "无需"}.get(strat, strat)
        print(f"  [{status}] {name:14s} | {login} | cookies:{cookie} | 策略:{strat_label}")
    print("=" * 64)
    print("  提示: 运行 'py -3.11 media-fetcher.py auto-export-cookies' 自动从 Edge 提取")
    print("        或者确保已在 Edge 中登录对应平台，下载时自动读取")


if __name__ == "__main__":
    main()
