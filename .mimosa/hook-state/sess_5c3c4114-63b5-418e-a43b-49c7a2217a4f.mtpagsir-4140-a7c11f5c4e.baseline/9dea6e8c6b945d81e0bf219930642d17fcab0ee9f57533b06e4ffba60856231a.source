"""
Bilibili Creator Analyzer - UP 主视频知识解构器
==================================================

通过视觉模型分析和解构 UP 主的视频内容，学习其视频知识和生产逻辑技巧。

工作流程:
1. 解析 UP 主主页 → 获取视频列表和元数据
2. 下载代表性视频 → 抽取关键帧
3. 调用视觉模型分析 → 画面内容/风格/结构
4. 汇总分析 → 视频生产逻辑技巧总结

核心分析维度:
- 内容主题与叙事结构
- 视觉风格与调色
- 剪辑节奏与转场
- 镜头语言与构图
- BGM 与音效运用
- 封面/标题策略

依赖:
- yt-dlp (B站视频下载)
- OpenCV (关键帧抽取)
- ARK/DuckMiss/SiliconFlow 视觉模型 (画面分析)
- LLM 网关 (内容总结)
"""
from __future__ import annotations

import os
import sys
import json
import time
import base64
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).resolve().parent))


def log(msg: str, level: str = "INFO", indent: int = 0):
    ts = time.strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"{prefix}[{ts}][{level}] {msg}")


class AnalysisLevel(Enum):
    """分析深度级别"""
    LIGHT = "light"       # 仅获取元数据和封面分析
    MEDIUM = "medium"     # 下载1-2个代表性视频深度分析
    DEEP = "deep"         # 下载多个视频，全面解构


@dataclass
class VideoInfo:
    """视频元数据"""
    bv_id: str
    title: str
    url: str
    thumbnail: str
    duration: float
    view_count: int
    like_count: int
    comment_count: int
    upload_date: str
    description: str
    tags: List[str] = field(default_factory=list)
    extracted_keyframes: List[str] = field(default_factory=list)
    visual_analysis: Dict[str, Any] = field(default_factory=dict)
    style_fingerprint: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CreatorProfile:
    """UP 主档案"""
    name: str
    uid: str
    url: str
    avatar: str
    description: str
    subscribers: int
    total_videos: int
    total_views: int
    videos: List[VideoInfo] = field(default_factory=list)


@dataclass
class ProductionTechnique:
    """生产技巧总结"""
    category: str
    description: str
    evidence: str
    priority: int = 3


@dataclass
class AnalysisReport:
    """分析报告"""
    creator: CreatorProfile
    analysis_level: str
    total_videos_analyzed: int
    overall_summary: str
    content_strategy: Dict[str, Any] = field(default_factory=dict)
    visual_style: Dict[str, Any] = field(default_factory=dict)
    editing_patterns: Dict[str, Any] = field(default_factory=dict)
    production_techniques: List[ProductionTechnique] = field(default_factory=list)
    suggested_improvements: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


class BilibiliCreatorAnalyzer:
    """UP 主视频知识解构器"""

    def __init__(
        self,
        output_base_dir: Optional[str] = None,
        max_videos: int = 5,
        analysis_level: AnalysisLevel = AnalysisLevel.MEDIUM,
    ):
        # 输出目录收口到 core/paths.py（AE_WORK_DIR 主变量一键迁移）
        try:
            from core.paths import work_root
            _default_out = os.path.join(work_root(), "creator_analysis")
        except ImportError:
            _default_out = r"D:\AE-Work\creator_analysis"
        self.output_base_dir = Path(output_base_dir or _default_out)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        self.max_videos = max_videos
        self.analysis_level = analysis_level
        self._creator_name_cache = ""
        self._load_config()

    def _load_config(self):
        """加载 API 配置"""
        from core import config as core_config
        self.config = core_config.load_config()

    async def analyze_creator(self, home_url: str, bv_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """分析 UP 主

        Args:
            home_url: UP 主主页链接 (如 https://space.bilibili.com/xxx)
            bv_ids: 可选的 BV 号列表（当 API 被风控时直接使用）

        Returns:
            Dict - 包含分析报告和风格知识整合结果
        """
        log(f"开始分析 UP 主: {home_url}", "INFO")

        # Step 1: 获取 UP 主档案和视频列表
        log("Step 1: 获取 UP 主档案和视频列表...", indent=1)
        if bv_ids:
            log(f"  使用传入的 {len(bv_ids)} 个 BV 号", indent=2)
            profile = self._fetch_via_bv_list(bv_ids, home_url)
        else:
            profile = await self._fetch_creator_profile(home_url)
        log(f"  获取到 {len(profile.videos)} 个视频", indent=2)

        # Step 2: 选择代表性视频
        selected_videos = self._select_representative_videos(profile.videos)
        log(f"  选择 {len(selected_videos)} 个代表性视频进行深度分析", indent=2)

        # Step 3: 下载并分析视频
        log("Step 2: 下载视频并进行视觉分析...", indent=1)
        for video in selected_videos:
            await self._analyze_single_video(video)

        # Step 4: 汇总分析生成报告
        log("Step 3: 汇总分析生成报告...", indent=1)
        report = await self._generate_report(profile, selected_videos)

        # Step 5: 风格知识整合（新）
        log("Step 4: 风格知识整合...", indent=1)
        style_knowledge = self._integrate_style_knowledge(report, selected_videos)

        # Step 6: 保存报告
        report_path = self._save_report(report, style_knowledge)
        log(f"  报告已保存: {report_path}", indent=2)

        return {
            "report": report,
            "style_knowledge": style_knowledge,
            "analyzed_videos": selected_videos,
        }

    def _fetch_via_bv_list(self, bv_ids: List[str], home_url: str) -> CreatorProfile:
        """直接用 BV 号列表 + view API 获取视频信息"""
        uid = self._extract_uid(home_url) or ""
        videos = []
        total_views = 0

        for bv_id in bv_ids[:self.max_videos + 5]:
            video_info = self._fetch_video_detail(bv_id)
            if video_info:
                videos.append(video_info)
                total_views += video_info.view_count

        name = self._creator_name_cache or ""
        log(f"  UP 主: {name} | 获取到 {len(videos)} 个视频", indent=2)

        return CreatorProfile(
            name=name,
            uid=uid,
            url=home_url,
            avatar="",
            description="",
            subscribers=0,
            total_videos=len(bv_ids),
            total_views=total_views,
            videos=videos,
        )

    async def _fetch_creator_profile(self, home_url: str) -> CreatorProfile:
        """获取 UP 主档案和视频列表（优先 view API，降级到 yt-dlp）"""
        uid = self._extract_uid(home_url)
        if not uid:
            raise ValueError(f"无法从 URL 提取 UID: {home_url}")

        log(f"  UP 主 UID: {uid}", indent=2)

        # 优先用 view API（从主页 HTML 提取 BV 号 + view API 获取详情）
        profile = self._fetch_via_api(uid, home_url)
        if profile.videos:
            return profile

        # 降级到 yt-dlp
        log("  view API 未获取到视频，尝试 yt-dlp...", "WARN", indent=2)
        profile = self._fetch_via_ytdlp(uid, home_url)
        if profile.videos:
            # yt-dlp 获取到 BV 号但可能缺标题，用 view API 补充
            if not profile.videos[0].title:
                log("  yt-dlp 视频缺标题，用 view API 补充...", indent=2)
                enriched = self._enrich_via_view_api(profile)
                if enriched.videos[0].title:
                    return enriched
            return profile

        return profile

    def _enrich_via_view_api(self, profile: CreatorProfile) -> CreatorProfile:
        """用 view API 补充 yt-dlp 获取的视频信息"""
        videos = []
        for v in profile.videos:
            if v.bv_id and not v.title:
                detail = self._fetch_video_detail(v.bv_id)
                if detail:
                    videos.append(detail)
                    continue
            videos.append(v)
        profile.videos = videos
        if self._creator_name_cache:
            profile.name = self._creator_name_cache
        profile.total_views = sum(v.view_count for v in videos)
        return profile

    def _fetch_via_ytdlp(self, uid: str, home_url: str) -> CreatorProfile:
        """使用 yt-dlp 获取 UP 主视频列表"""
        try:
            from yt_dlp import YoutubeDL

            playlist_url = f"https://space.bilibili.com/{uid}/video"
            cookie_path = self._find_bilibili_cookie()
            options = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                "playlistend": self.max_videos + 10,
            }
            if cookie_path:
                options["cookiefile"] = cookie_path
                log(f"  使用 Cookie: {cookie_path}", indent=2)

            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(playlist_url, download=False)

            if not info:
                return CreatorProfile(name="", uid=uid, url=home_url, avatar="", description="", subscribers=0, total_videos=0, total_views=0)

            entries = []
            if info.get("_type") == "playlist":
                entries = info.get("entries", []) or []
            elif "entries" in info:
                entries = info.get("entries", []) or []

            videos = []
            for entry in entries[:self.max_videos + 5]:
                if not entry:
                    continue
                bv_id = entry.get("id", "")
                videos.append(VideoInfo(
                    bv_id=bv_id,
                    title=entry.get("title", ""),
                    url=entry.get("url", entry.get("webpage_url", f"https://www.bilibili.com/video/{bv_id}")),
                    thumbnail=entry.get("thumbnail", entry.get("thumbnails", [{}])[0].get("url", "") if entry.get("thumbnails") else ""),
                    duration=float(entry.get("duration", 0) or 0),
                    view_count=int(entry.get("view_count", 0) or 0),
                    like_count=int(entry.get("like_count", 0) or 0),
                    comment_count=int(entry.get("comment_count", 0) or 0),
                    upload_date=entry.get("upload_date", ""),
                    description=(entry.get("description") or "")[:500],
                    tags=entry.get("tags", []),
                ))

            name = info.get("uploader", "") or info.get("channel", "")
            log(f"  UP 主: {name} | 获取到 {len(videos)} 个视频", indent=2)

            return CreatorProfile(
                name=name,
                uid=uid,
                url=home_url,
                avatar="",
                description="",
                subscribers=0,
                total_videos=len(videos),
                total_views=sum(v.view_count for v in videos),
                videos=videos,
            )
        except Exception as e:
            log(f"  yt-dlp 获取失败: {e}", "WARN", indent=2)
            return CreatorProfile(name="", uid=uid, url=home_url, avatar="", description="", subscribers=0, total_videos=0, total_views=0)

    def _fetch_via_api(self, uid: str, home_url: str) -> CreatorProfile:
        """使用 B 站 view API 获取视频信息（通过 UP 主主页 HTML 提取 BV 号）"""
        import urllib.request

        # Step A: 获取 UP 主基本信息
        name, avatar, description = "野喵要吃草_", "", ""
        try:
            info_url = f"https://api.bilibili.com/x/web-interface/view?bvid="
            # 先用 nav API 获取 UP 主名称
            nav_req = urllib.request.Request(
                f"https://api.bilibili.com/x/web-interface/zone?mid={uid}",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            )
            try:
                with urllib.request.urlopen(nav_req, timeout=10) as resp:
                    pass
            except Exception:
                pass
        except Exception:
            pass

        # Step B: 从 UP 主主页 HTML 提取 BV 号
        bv_ids = self._extract_bv_ids_from_page(uid)
        if not bv_ids:
            log("  无法从主页获取 BV 号", "WARN", indent=2)
            return CreatorProfile(name=name, uid=uid, url=home_url, avatar=avatar, description=description, subscribers=0, total_videos=0, total_views=0)

        log(f"  获取到 {len(bv_ids)} 个 BV 号", indent=2)

        # Step C: 用 view API 获取每个视频的详细信息
        videos = []
        total_views = 0
        for bv_id in bv_ids[:self.max_videos + 5]:
            video_info = self._fetch_video_detail(bv_id)
            if video_info:
                videos.append(video_info)
                total_views += video_info.view_count

        if videos and self._creator_name_cache:
            name = self._creator_name_cache

        log(f"  获取到 {len(videos)} 个视频详细信息", indent=2)

        return CreatorProfile(
            name=name,
            uid=uid,
            url=home_url,
            avatar=avatar,
            description=description,
            subscribers=0,
            total_videos=len(bv_ids),
            total_views=total_views,
            videos=videos,
        )

    def _extract_bv_ids_from_page(self, uid: str) -> List[str]:
        """从 UP 主主页 HTML 中提取 BV 号"""
        import urllib.request
        import re as regex

        try:
            url = f"https://space.bilibili.com/{uid}/video"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # 从 HTML 中提取 BV 号
            bv_pattern = r'/video/(BV[0-9A-Za-z]{10})'
            matches = regex.findall(bv_pattern, html)
            # 去重保持顺序
            seen = set()
            bv_ids = []
            for bv in matches:
                if bv not in seen:
                    seen.add(bv)
                    bv_ids.append(bv)
            return bv_ids
        except Exception as e:
            log(f"  从主页提取 BV 号失败: {e}", "WARN", indent=2)
            return []

    def _fetch_video_detail(self, bv_id: str) -> Optional[VideoInfo]:
        """用 view API 获取单个视频的详细信息"""
        import urllib.request

        try:
            url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": f"https://www.bilibili.com/video/{bv_id}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if data.get("code") != 0:
                return None

            d = data["data"]
            stat = d.get("stat", {})
            owner_name = d.get("owner", {}).get("name", "")
            if owner_name:
                self._creator_name_cache = owner_name
            return VideoInfo(
                bv_id=d.get("bvid", bv_id),
                title=d.get("title", ""),
                url=f"https://www.bilibili.com/video/{bv_id}",
                thumbnail=d.get("pic", ""),
                duration=float(d.get("duration", 0) or 0),
                view_count=int(stat.get("view", 0) or 0),
                like_count=int(stat.get("like", 0) or 0),
                comment_count=int(stat.get("reply", 0) or 0),
                upload_date=str(d.get("pubdate", "")),
                description=(d.get("desc") or "")[:500],
                tags=[],
            )
        except Exception as e:
            log(f"  获取视频 {bv_id} 信息失败: {e}", "WARN", indent=3)
            return None

    def _find_bilibili_cookie(self) -> Optional[str]:
        """查找 B 站 Cookie 文件（AE_WORK_DIR / BILIBILI_COOKIE_PATH 可覆盖）"""
        try:
            from core.paths import cookies_dir
            _default_cookie = os.path.join(cookies_dir(), "bilibili_cookies.txt")
        except ImportError:
            _default_cookie = r"D:\AE-Work\cookies\bilibili_cookies.txt"
        candidates = [
            os.environ.get("BILIBILI_COOKIE_PATH", ""),
            _default_cookie,
            str(Path(__file__).parent / "cookies" / "bilibili_cookies.txt"),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _get_wbi_mixin_key(self) -> Optional[str]:
        """获取 B 站 wbi 签名所需的 mixin_key"""
        import urllib.request

        try:
            req = urllib.request.Request(
                "https://api.bilibili.com/x/web-interface/nav",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                nav_data = json.loads(resp.read().decode("utf-8"))

            if nav_data.get("code") != 0:
                return None

            wbi_img = nav_data.get("data", {}).get("wbi_img", {})
            img_url = wbi_img.get("img_url", "")
            sub_url = wbi_img.get("sub_url", "")

            # 从 URL 提取 key（文件名去后缀）
            img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
            sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]

            # 混淆表
            mixin_key_enc_tab = [
                46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
                60, 24, 44, 21, 1, 28, 39, 12, 30, 55, 16, 5, 57, 7, 4, 36,
                25, 63, 47, 51, 42, 33, 11, 29, 37, 48, 17, 54, 61, 40, 9, 38,
                56, 52, 22, 49, 20, 41, 62, 14, 34, 26, 13, 6, 43, 27, 59, 19,
            ]

            # 拼接并重排
            raw = img_key + sub_key
            mixin_key = "".join(raw[i] for i in mixin_key_enc_tab[:32])
            return mixin_key
        except Exception as e:
            log(f"  获取 wbi key 失败: {e}", "WARN", indent=2)
            return None

    def _sign_wbi(self, params: Dict[str, str], mixin_key: str) -> Dict[str, str]:
        """对请求参数进行 wbi 签名"""
        import hashlib

        params = dict(params)
        params["wts"] = str(int(time.time()))

        # 按 key 排序后拼接
        query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        w_rid = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
        params["w_rid"] = w_rid
        return params

    def _extract_uid(self, url: str) -> Optional[str]:
        """从 UP 主主页 URL 提取 UID"""
        patterns = [
            r"space\.bilibili\.com/(\d+)",
            r"bilibili\.com/\d+/(\d+)",
            r"uid=(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _select_representative_videos(self, videos: List[VideoInfo]) -> List[VideoInfo]:
        """选择代表性视频（按播放量排序，兼顾多样性）"""
        if not videos:
            return []

        # 按播放量排序
        sorted_by_views = sorted(videos, key=lambda v: v.view_count, reverse=True)

        if self.analysis_level == AnalysisLevel.LIGHT:
            return sorted_by_views[:2]
        elif self.analysis_level == AnalysisLevel.MEDIUM:
            return sorted_by_views[:3]
        else:
            return sorted_by_views[:5]

    async def _analyze_single_video(self, video: VideoInfo):
        """分析单个视频"""
        log(f"  分析视频: {video.title[:30]}...", indent=2)

        # 创建视频输出目录
        video_dir = self.output_base_dir / video.bv_id
        video_dir.mkdir(parents=True, exist_ok=True)

        if self.analysis_level == AnalysisLevel.LIGHT:
            video.visual_analysis = await self._analyze_thumbnail(video)
            return

        # Medium/Deep: 下载视频并抽帧分析
        try:
            download_result = await self._download_video(video, video_dir)
            if not download_result.get("success"):
                log(f"    下载失败，尝试封面分析: {download_result.get('error')}", "WARN", indent=3)
                video.visual_analysis = await self._analyze_thumbnail(video)
                return

            video_path = download_result.get("file_path")
            log(f"    视频下载完成: {Path(video_path).name}", indent=3)

            # 抽取关键帧
            keyframes = await self._extract_keyframes(video_path, video_dir)
            video.extracted_keyframes = keyframes
            log(f"    抽取 {len(keyframes)} 帧", indent=3)

            # 视觉分析
            analysis = await self._analyze_frames(keyframes, video)
            video.visual_analysis = analysis
            log(f"    视觉分析完成", indent=3)

            # 风格指纹提取（新）
            fingerprint = await self._extract_style_fingerprint(video_path, video)
            video.style_fingerprint = fingerprint
            log(f"    风格指纹提取完成", indent=3)

        except Exception as e:
            log(f"    分析失败: {e}", "ERROR", indent=3)
            video.visual_analysis = await self._analyze_thumbnail(video)

    async def _download_video(self, video: VideoInfo, output_dir: Path) -> Dict[str, Any]:
        """下载 B 站视频"""
        from bilibili_downloader import BilibiliDownloader

        try:
            downloader = BilibiliDownloader()
            result = downloader.download_video(
                url=video.url,
                output_dir=str(output_dir),
                quality="720p",
            )
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _extract_keyframes(self, video_path: str, output_dir: Path) -> List[str]:
        """从视频抽取关键帧"""
        try:
            from media.media_preprocessor import MediaPreprocessor

            pp = MediaPreprocessor()
            interval = max(2.0, float(pp.get_info(video_path).duration) / 8)
            result = pp.extract_thumbnails(
                video_path=video_path,
                output_dir=str(output_dir / "keyframes"),
                interval=interval,
                width=640,
            )
            return result.output_paths if result.success else []
        except Exception as e:
            log(f"      抽帧失败: {e}", "WARN", indent=4)
            return []

    async def _analyze_frames(self, frame_paths: List[str], video: VideoInfo) -> Dict[str, Any]:
        """调用视觉模型分析帧"""
        try:
            from analysis.visual_content_analyzer import VisualContentAnalyzer

            analyzer = VisualContentAnalyzer()
            custom_prompt = f"""分析视频《{video.title}》的关键帧，重点关注：
1. 画面构图和镜头语言
2. 调色风格和色彩运用
3. 剪辑节奏和转场方式
4. 字幕/文字设计
5. 整体视觉风格

视频描述: {video.description}
标签: {', '.join(video.tags[:5])}
"""
            result = analyzer._call_vision_api(frame_paths, custom_prompt) or {}
            result["raw_frames"] = frame_paths
            return result
        except Exception as e:
            log(f"      视觉分析失败: {e}", "WARN", indent=4)
            return await self._analyze_thumbnail(video)

    async def _extract_style_fingerprint(self, video_path: str, video: VideoInfo) -> Dict[str, Any]:
        """提取视频风格指纹"""
        try:
            from video.style_extractor import VideoStyleExtractor

            extractor = VideoStyleExtractor(sampling_rate=100)
            fingerprint = extractor.extract(
                video_path=video_path,
                visual_analysis=video.visual_analysis if video.visual_analysis else None,
            )

            return fingerprint.to_dict()
        except Exception as e:
            log(f"      风格指纹提取失败: {e}", "WARN", indent=4)
            return {}

    async def _analyze_thumbnail(self, video: VideoInfo) -> Dict[str, Any]:
        """分析视频封面（降级方案）"""
        try:
            import urllib.request
            from analysis.visual_content_analyzer import VisualContentAnalyzer

            # 下载封面
            temp_dir = self.output_base_dir / "temp_thumbnails"
            temp_dir.mkdir(parents=True, exist_ok=True)
            thumb_path = temp_dir / f"{video.bv_id}_thumb.jpg"

            try:
                urllib.request.urlretrieve(video.thumbnail, str(thumb_path))
            except Exception:
                return {"analysis_mode": "thumbnail_only", "summary": "无法获取封面"}

            analyzer = VisualContentAnalyzer()
            custom_prompt = f"""分析视频《{video.title}》的封面图，分析：
1. 封面构图和视觉焦点
2. 色彩搭配和风格
3. 标题文字设计（如果有）
4. 封面与视频内容的关联性

视频描述: {video.description}
"""
            result = analyzer._call_vision_api([str(thumb_path)], custom_prompt) or {}
            result["analysis_mode"] = "thumbnail_only"
            return result
        except Exception as e:
            log(f"      封面分析失败: {e}", "WARN", indent=4)
            return {"analysis_mode": "fallback", "summary": "无法进行视觉分析"}

    async def _generate_report(self, profile: CreatorProfile, analyzed_videos: List[VideoInfo]) -> AnalysisReport:
        """生成完整分析报告"""
        all_visual_analyses = [v.visual_analysis for v in analyzed_videos if v.visual_analysis]
        all_tags = [tag for v in analyzed_videos for tag in v.tags]

        style_fingerprints = [v.style_fingerprint for v in analyzed_videos if v.style_fingerprint]

        style_summary = ""
        if style_fingerprints:
            style_summary = json.dumps(style_fingerprints, ensure_ascii=False, indent=2)

        summary_prompt = f"""你是一位专业的视频内容分析专家。请根据以下 UP 主的视频数据，总结其视频生产逻辑和技巧。

UP 主信息:
- 名称: {profile.name}
- 视频数量: {len(profile.videos)}
- 总播放量: {profile.total_views:,}

代表性视频:
{json.dumps([{
    "title": v.title,
    "views": v.view_count,
    "tags": v.tags[:5],
    "duration": round(v.duration, 1),
    "visual_analysis": v.visual_analysis.get("summary", "") if v.visual_analysis else "",
    "style_fingerprint": v.style_fingerprint.get("style_tags", []) if v.style_fingerprint else [],
} for v in analyzed_videos], ensure_ascii=False, indent=2)}

风格指纹数据:
{style_summary}

请从以下维度进行深度分析并返回 JSON:
{{
  "overall_summary": "整体评价（50字）",
  "content_strategy": {{
    "themes": ["主题1", "主题2"],
    "narrative_pattern": "叙事模式描述",
    "title_strategy": "标题策略",
    "cover_strategy": "封面策略"
  }},
  "visual_style": {{
    "color_palette": "调色风格",
    "composition": "构图特点",
    "camera_movement": "镜头运动",
    "text_style": "文字风格"
  }},
  "editing_patterns": {{
    "pace": "节奏特点",
    "transitions": "转场方式",
    "timing": "剪辑时机",
    "effects": "特效运用"
  }},
  "production_techniques": [
    {{"category": "类别", "description": "技巧描述", "evidence": "证据", "priority": 1}}
  ],
  "suggested_improvements": ["改进建议1", "改进建议2"]
}}

只返回 JSON，不要其他内容。"""

        summary = await self._call_llm_for_summary(summary_prompt)

        report = AnalysisReport(
            creator=profile,
            analysis_level=self.analysis_level.value,
            total_videos_analyzed=len(analyzed_videos),
            overall_summary=summary.get("overall_summary", ""),
            content_strategy=summary.get("content_strategy", {}),
            visual_style=summary.get("visual_style", {}),
            editing_patterns=summary.get("editing_patterns", {}),
            production_techniques=[
                ProductionTechnique(**t) for t in summary.get("production_techniques", [])
            ],
            suggested_improvements=summary.get("suggested_improvements", []),
        )

        return report

    def _integrate_style_knowledge(self, report: AnalysisReport, analyzed_videos: List[VideoInfo]) -> Dict[str, Any]:
        """整合风格知识并生成AE脚本"""
        from video.style_knowledge_integrator import StyleKnowledgeIntegrator

        fingerprints = [v.style_fingerprint for v in analyzed_videos if v.style_fingerprint]
        if not fingerprints:
            log("  没有风格指纹数据，跳过风格知识整合", "WARN", indent=2)
            return {}

        integrator = StyleKnowledgeIntegrator()
        knowledge = integrator.integrate(fingerprints, report.creator.name)

        outputs = integrator.save_knowledge(knowledge, str(self.output_base_dir))

        integrator.export_to_style_library(knowledge)

        log(f"  风格知识整合完成!", indent=2)
        log(f"    独特风格元素: {', '.join(knowledge.unique_style_elements)}", indent=3)
        log(f"    风格标签: {', '.join(knowledge.aggregated_fingerprint.get('style_tags', []))}", indent=3)

        return {
            "knowledge": knowledge,
            "outputs": outputs,
            "unique_elements": knowledge.unique_style_elements,
            "ae_effect_preset": knowledge.ae_effect_preset,
        }

    async def _call_llm_for_summary(self, prompt: str) -> Dict[str, Any]:
        """调用 LLM 生成总结（多 Provider 降级）"""
        providers = self._get_llm_providers()

        for provider in providers:
            try:
                result = await self._call_llm_provider(provider, prompt)
                if result:
                    return result
            except Exception as e:
                log(f"    {provider['name']} 调用失败: {e}", "WARN", indent=3)
                continue

        return self._empty_summary()

    def _get_llm_providers(self) -> List[Dict[str, str]]:
        """获取可用的 LLM Provider 列表"""
        # 从 .env.doubao 读取配置
        env_path = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.env.doubao")
        env_vars = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()

        providers = [
            {"name": "ARK", "base_url": "https://ark.cn-beijing.volces.com/api/v3",
             "model": env_vars.get("ARK_MODEL_FLASH", "deepseek-v4-flash-260425"),
             "api_key": env_vars.get("DOUBAO_API_KEY", "")},
            {"name": "DuckMiss", "base_url": "https://duckmiss.site/v1",
             "model": "claude-sonnet-4-6",
             "api_key": env_vars.get("DUCK_MISS_API_KEY", "")},
        ]
        return [p for p in providers if p["api_key"]]

    async def _call_llm_provider(self, provider: Dict[str, str], prompt: str) -> Optional[Dict[str, Any]]:
        """调用单个 LLM Provider"""
        import urllib.request

        payload = json.dumps({
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": "你是一位专业的视频内容分析专家，擅长分析UP主的视频生产逻辑和创作技巧。只返回JSON，不要其他内容。"},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.7,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{provider['base_url']}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {provider['api_key']}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content:
            log(f"    {provider['name']} 响应: {len(content)} 字符", indent=3)
            return self._parse_json_response(content)
        return None

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            "overall_summary": "无法生成详细分析，需配置 LLM API Key",
            "content_strategy": {},
            "visual_style": {},
            "editing_patterns": {},
            "production_techniques": [],
            "suggested_improvements": [],
        }

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """解析 JSON 响应"""
        try:
            return json.loads(text)
        except Exception:
            pass

        import re
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass

        return {}

    def _save_report(self, report: AnalysisReport, style_knowledge: Dict[str, Any] = None) -> str:
        """保存分析报告"""
        safe_name = re.sub(r'[\\/:*?"<>|\n\r]', "_", report.creator.name)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = self.output_base_dir / f"analysis_{safe_name}_{timestamp}.json"

        report_dict = {
            "creator": {
                "name": report.creator.name,
                "uid": report.creator.uid,
                "url": report.creator.url,
                "total_videos": report.creator.total_videos,
                "total_views": report.creator.total_views,
            },
            "analysis_level": report.analysis_level,
            "total_videos_analyzed": report.total_videos_analyzed,
            "timestamp": report.timestamp,
            "overall_summary": report.overall_summary,
            "content_strategy": report.content_strategy,
            "visual_style": report.visual_style,
            "editing_patterns": report.editing_patterns,
            "production_techniques": [
                {
                    "category": t.category,
                    "description": t.description,
                    "evidence": t.evidence,
                    "priority": t.priority,
                } for t in report.production_techniques
            ],
            "suggested_improvements": report.suggested_improvements,
            "style_knowledge": style_knowledge or {},
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

        return str(report_path)

    def print_report(self, report: AnalysisReport):
        """打印报告摘要"""
        print("\n" + "=" * 80)
        print(f" UP 主视频知识解构报告")
        print("=" * 80)
        print(f"\n📌 UP 主: {report.creator.name}")
        print(f"   主页: {report.creator.url}")
        print(f"   视频总数: {report.creator.total_videos} | 总播放: {report.creator.total_views:,}")
        print(f"   分析深度: {report.analysis_level} | 分析视频数: {report.total_videos_analyzed}")
        print(f"   生成时间: {report.timestamp}")

        print(f"\n📊 整体评价:")
        print(f"   {report.overall_summary}")

        if report.content_strategy:
            print(f"\n🎯 内容策略:")
            cs = report.content_strategy
            print(f"   主题方向: {', '.join(cs.get('themes', []))}")
            print(f"   叙事模式: {cs.get('narrative_pattern', '')}")
            print(f"   标题策略: {cs.get('title_strategy', '')}")
            print(f"   封面策略: {cs.get('cover_strategy', '')}")

        if report.visual_style:
            print(f"\n🎨 视觉风格:")
            vs = report.visual_style
            print(f"   调色风格: {vs.get('color_palette', '')}")
            print(f"   构图特点: {vs.get('composition', '')}")
            print(f"   镜头运动: {vs.get('camera_movement', '')}")
            print(f"   文字风格: {vs.get('text_style', '')}")

        if report.editing_patterns:
            print(f"\n✂️ 剪辑模式:")
            ep = report.editing_patterns
            print(f"   节奏特点: {ep.get('pace', '')}")
            print(f"   转场方式: {ep.get('transitions', '')}")
            print(f"   剪辑时机: {ep.get('timing', '')}")
            print(f"   特效运用: {ep.get('effects', '')}")

        if report.production_techniques:
            print(f"\n💡 核心生产技巧:")
            for i, technique in enumerate(sorted(report.production_techniques, key=lambda t: t.priority), 1):
                priority = "★★★" if technique.priority <= 2 else "★★" if technique.priority == 3 else "★"
                print(f"   {i}. [{priority}] {technique.category}: {technique.description}")
                if technique.evidence:
                    print(f"      证据: {technique.evidence}")

        if report.suggested_improvements:
            print(f"\n🚀 改进建议:")
            for i, suggestion in enumerate(report.suggested_improvements, 1):
                print(f"   {i}. {suggestion}")

        print("\n" + "=" * 80)


# ================================================================
# 便捷函数
# ================================================================
async def analyze_bilibili_creator(
    home_url: str,
    output_dir: Optional[str] = None,
    max_videos: int = 5,
    analysis_level: str = "medium",
    bv_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """便捷函数：分析 B 站 UP 主"""
    level_map = {
        "light": AnalysisLevel.LIGHT,
        "medium": AnalysisLevel.MEDIUM,
        "deep": AnalysisLevel.DEEP,
    }
    analyzer = BilibiliCreatorAnalyzer(
        output_base_dir=output_dir,
        max_videos=max_videos,
        analysis_level=level_map.get(analysis_level, AnalysisLevel.MEDIUM),
    )
    result = await analyzer.analyze_creator(home_url, bv_ids=bv_ids)
    analyzer.print_report(result["report"])

    if result.get("style_knowledge"):
        sk = result["style_knowledge"]
        print(f"\n🎨 风格知识整合结果:")
        print(f"   独特风格元素: {', '.join(sk.get('unique_elements', []))}")
        if sk.get("ae_effect_preset"):
            effects = sk["ae_effect_preset"].get("effects", [])
            print(f"   生成 AE 效果: {len(effects)} 个")
            for ef in effects:
                print(f"     - {ef.get('effectName', '')}")
        if sk.get("outputs"):
            print(f"   输出文件:")
            for key, path in sk["outputs"].items():
                print(f"     - {key}: {path}")

    return result


# ================================================================
# 主入口
# ================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bilibili UP 主视频知识解构器")
    parser.add_argument("url", help="UP 主主页链接")
    parser.add_argument("--output", "-o", help="输出目录")
    parser.add_argument("--max-videos", "-n", type=int, default=5, help="最多分析视频数")
    parser.add_argument("--level", "-l", choices=["light", "medium", "deep"], default="medium", help="分析深度")
    parser.add_argument("--bv-ids", "-b", nargs="+", help="直接指定 BV 号列表（如 -b BV123 BV456）")
    args = parser.parse_args()

    asyncio.run(analyze_bilibili_creator(
        home_url=args.url,
        output_dir=args.output,
        max_videos=args.max_videos,
        analysis_level=args.level,
        bv_ids=args.bv_ids,
    ))


if __name__ == "__main__":
    main()
