"""
OpenMontage Engine - 视频编排与素材搜索
=========================================

封装 external/OpenMontage/ 的核心能力：
- 多平台素材搜索（Pexels/Pixabay/本地等）
- 智能重构图（人脸追踪+自动裁剪）
- 快速视频合成（无需AE）
- 字幕生成

与现有系统的关系：
- OpenMontage.search_stock → 增强 MaterialCollector 素材搜集
- OpenMontage.auto_reframe → 自动适配多平台分辨率
- OpenMontage.compose_video → AE渲染前的快速预览

国内网络适配：
- 素材搜索优先使用国内可访问源（Wikimedia/Archive.org/本地）
- 在线API（Pexels/Pixabay）需要代理或API key
- 离线模式可用本地素材库+自动重构图+合成
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_OM_ROOT = _PROJECT_ROOT / "external" / "OpenMontage"

# 添加 OpenMontage 到 Python 路径
if str(_OM_ROOT) not in sys.path:
    sys.path.insert(0, str(_OM_ROOT))

from ..base import BaseEngine, EngineResult  # noqa: E402


class OpenMontageEngine(BaseEngine):
    """OpenMontage video composition and stock media engine."""

    name = "openmontage"

    def __init__(
        self,
        executable_path: Path | str = sys.executable,
        om_root: Optional[Path] = None,
    ):
        self.om_root = om_root or _OM_ROOT
        super().__init__(executable_path)
        self._verify_installation()
        self._load_tools()

    def _verify_installation(self) -> None:
        """验证 OpenMontage 安装。"""
        if not self.om_root.exists():
            logger.warning(f"OpenMontage not found at {self.om_root}")
        else:
            logger.info(f"OpenMontage ready: {self.om_root}")

    def _load_tools(self) -> None:
        """延迟加载工具模块。"""
        self._tools_loaded = False
        self._clip_search = None
        self._auto_reframe = None
        self._stock_sources = {}

    async def execute(self, *args, **kwargs) -> EngineResult:
        """Dispatch to specific methods."""
        task = kwargs.get("task", "compose")
        if task == "search":
            return await self.search_stock(**{k: v for k, v in kwargs.items() if k != "task"})
        if task == "reframe":
            return await self.auto_reframe(**{k: v for k, v in kwargs.items() if k != "task"})
        if task == "compose":
            return await self.compose_video(**{k: v for k, v in kwargs.items() if k != "task"})
        return EngineResult(success=False, error=f"Unknown task: {task}")

    # ------------------------------------------------------------------
    # 素材搜索
    # ------------------------------------------------------------------

    async def search_stock(
        self,
        query: str,
        kind: str = "video",  # video | image | any
        max_results: int = 10,
        sources: Optional[List[str]] = None,
        download: bool = False,
        download_dir: Optional[Path] = None,
    ) -> EngineResult:
        """多平台素材搜索。

        Args:
            query: 搜索关键词
            kind: 素材类型 (video/image/any)
            max_results: 最大结果数
            sources: 指定搜索源（None=全部可用源）
            download: 是否自动下载
            download_dir: 下载目录
        """
        import time

        start = time.time()

        # 国内可用源（无需翻墙）
        china_friendly_sources = [
            "wikimedia",      # 维基共享资源
            "archive_org",    # 互联网档案馆
            "nasa",           # NASA媒体库
            "noaa",           # NOAA
            "loc",            # 美国国会图书馆
        ]

        # 需要API key的源
        api_sources = [
            "pexels",
            "pixabay",
            "unsplash",
            "mixkit",
            "coverr",
        ]

        # 使用指定源或默认国内源
        active_sources = sources or china_friendly_sources

        logger.info(f"[OpenMontage] Searching '{query}' on {active_sources}")

        all_results = []
        errors = []

        for source_name in active_sources:
            try:
                results = await asyncio.to_thread(
                    self._search_single_source,
                    source_name, query, kind, max_results // len(active_sources) + 1,
                )
                if results:
                    all_results.extend(results)
            except Exception as e:
                errors.append(f"{source_name}: {str(e)[:100]}")
                logger.debug(f"[OpenMontage] Source {source_name} failed: {e}")

        # 去重+排序
        all_results = all_results[:max_results]

        # 自动下载
        downloaded = []
        if download and download_dir:
            download_dir = Path(download_dir)
            download_dir.mkdir(parents=True, exist_ok=True)
            for item in all_results:
                if "url" in item:
                    try:
                        path = await asyncio.to_thread(
                            self._download_media, item["url"], download_dir,
                        )
                        if path:
                            item["local_path"] = str(path)
                            downloaded.append(path)
                    except Exception as e:
                        logger.debug(f"Download failed: {e}")

        duration = time.time() - start

        if not all_results:
            return EngineResult(
                success=False,
                error=f"No results found. Errors: {'; '.join(errors[:3])}",
                duration_seconds=duration,
            )

        return EngineResult(
            success=True,
            metadata={
                "query": query,
                "results": all_results,
                "result_count": len(all_results),
                "downloaded": [str(d) for d in downloaded],
                "sources_tried": active_sources,
                "source_errors": errors,
            },
            duration_seconds=duration,
        )

    def _search_single_source(
        self, source_name: str, query: str, kind: str, limit: int,
    ) -> List[Dict[str, Any]]:
        """搜索单个素材源。"""
        try:
            # 动态导入源模块
            module_path = f"tools.video.stock_sources.{source_name}"
            module = __import__(module_path, fromlist=[""])

            # 查找 Source 类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if hasattr(attr, "search") and hasattr(attr, "is_available"):
                    source = attr()
                    if source.is_available():
                        from tools.video.stock_sources.base import SearchFilters
                        filters = SearchFilters(kind=kind, limit=limit)
                        candidates = source.search(query, filters)
                        return [
                            {
                                "id": getattr(c, "id", ""),
                                "title": getattr(c, "title", ""),
                                "url": getattr(c, "url", ""),
                                "thumbnail": getattr(c, "thumbnail", ""),
                                "source": source_name,
                                "duration": getattr(c, "duration", 0),
                            }
                            for c in candidates[:limit]
                        ]
            return []
        except Exception as e:
            logger.debug(f"Source {source_name} error: {e}")
            return []

    @staticmethod
    def _download_media(url: str, download_dir: Path) -> Optional[Path]:
        """下载单个媒体文件。"""
        import urllib.request

        filename = Path(url).name or "media"
        if "?" in filename:
            filename = filename.split("?")[0]
        if not filename or "." not in filename:
            filename = "media.mp4"

        output_path = download_dir / filename

        try:
            urllib.request.urlretrieve(url, output_path)
            return output_path
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 智能重构图
    # ------------------------------------------------------------------

    async def auto_reframe(
        self,
        input_path: Path | str,
        output_path: Path | str,
        target_aspect: str = "9:16",  # portrait/square/landscape/cinematic
        face_tracking: bool = True,
    ) -> EngineResult:
        """智能重构图（人脸追踪+自动裁剪）。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            target_aspect: 目标比例 (9:16/1:1/16:9/21:9)
            face_tracking: 是否启用人脸追踪
        """
        import time

        start = time.time()
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            return EngineResult(
                success=False, error=f"Input not found: {input_path}",
            )

        # 解析目标比例
        if ":" in target_aspect:
            w, h = map(int, target_aspect.split(":"))
            aspect_ratio = w / h
        else:
            # 预设名称
            presets = {"portrait": 9/16, "square": 1.0, "landscape": 16/9, "cinematic": 21/9}
            aspect_ratio = presets.get(target_aspect, 9/16)

        try:
            # 使用FFmpeg进行重构图（OpenMontage的简化版）
            # 若安装mediapipe则使用人脸追踪，否则居中裁剪
            if face_tracking:
                try:
                    import mediapipe as mp
                    crop_params = await asyncio.to_thread(
                        self._calculate_face_crop, input_path, aspect_ratio,
                    )
                except ImportError:
                    logger.warning("MediaPipe not installed, using center crop")
                    crop_params = self._calculate_center_crop(input_path, aspect_ratio)
            else:
                crop_params = self._calculate_center_crop(input_path, aspect_ratio)

            # 执行FFmpeg裁剪
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-vf", f"crop={crop_params['width']}:{crop_params['height']}:{crop_params['x']}:{crop_params['y']}",
                "-c:a", "copy",
                str(output_path),
            ]

            rc, stdout, stderr = await asyncio.to_thread(
                self._run_subprocess, cmd, timeout=600,
            )

            duration = time.time() - start

            if rc != 0:
                return EngineResult(
                    success=False,
                    error=f"FFmpeg reframe failed: {stderr[:500]}",
                    duration_seconds=duration,
                )

            return EngineResult(
                success=True,
                output_path=output_path,
                metadata={
                    "target_aspect": target_aspect,
                    "aspect_ratio": aspect_ratio,
                    "crop_params": crop_params,
                    "face_tracking": face_tracking,
                },
                duration_seconds=duration,
            )

        except Exception as e:
            return EngineResult(
                success=False, error=f"Reframe error: {str(e)[:500]}",
            )

    def _calculate_face_crop(self, video_path: Path, target_aspect: float) -> Dict[str, int]:
        """使用MediaPipe计算人脸追踪裁剪参数。"""
        import cv2
        import mediapipe as mp

        cap = cv2.VideoCapture(str(video_path))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        mp_face = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)

        face_centers = []
        frame_count = 0
        while cap.isOpened() and frame_count < 30:  # 采样前30帧
            ret, frame = cap.read()
            if not ret:
                break
            results = mp_face.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.detections:
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    cx = int((bbox.xmin + bbox.width / 2) * width)
                    cy = int((bbox.ymin + bbox.height / 2) * height)
                    face_centers.append((cx, cy))
            frame_count += 1

        cap.release()
        mp_face.close()

        if face_centers:
            # 使用人脸中心均值
            avg_cx = int(sum(c[0] for c in face_centers) / len(face_centers))
            avg_cy = int(sum(c[1] for c in face_centers) / len(face_centers))
        else:
            avg_cx, avg_cy = width // 2, height // 2

        # 计算裁剪框
        if width / height > target_aspect:
            # 原视频更宽，裁左右
            new_width = int(height * target_aspect)
            new_height = height
            x = max(0, min(avg_cx - new_width // 2, width - new_width))
            y = 0
        else:
            # 原视频更高，裁上下
            new_width = width
            new_height = int(width / target_aspect)
            x = 0
            y = max(0, min(avg_cy - new_height // 2, height - new_height))

        return {"width": new_width, "height": new_height, "x": x, "y": y}

    def _calculate_center_crop(self, video_path: Path, target_aspect: float) -> Dict[str, int]:
        """计算居中裁剪参数。"""
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        if width / height > target_aspect:
            new_width = int(height * target_aspect)
            new_height = height
            x = (width - new_width) // 2
            y = 0
        else:
            new_width = width
            new_height = int(width / target_aspect)
            x = 0
            y = (height - new_height) // 2

        return {"width": new_width, "height": new_height, "x": x, "y": y}

    # ------------------------------------------------------------------
    # 快速视频合成
    # ------------------------------------------------------------------

    async def compose_video(
        self,
        clips: List[Dict[str, Any]],
        output_path: Path | str,
        transitions: str = "fade",  # fade/none/slide
        audio_path: Optional[Path] = None,
        resolution: str = "1080x1920",
        fps: int = 30,
    ) -> EngineResult:
        """快速多片段合成（无需AE）。

        Args:
            clips: [{"path": "...", "duration": 5.0, "start": 0}, ...]
            output_path: 输出路径
            transitions: 转场类型
            audio_path: 背景音乐路径
            resolution: 输出分辨率
            fps: 输出帧率
        """
        import time

        start = time.time()
        output_path = Path(output_path)

        if not clips:
            return EngineResult(success=False, error="No clips provided")

        # 构建FFmpeg复杂滤镜图
        filter_complex = self._build_filter_complex(clips, transitions)

        cmd = ["ffmpeg", "-y"]

        # 添加输入
        for clip in clips:
            cmd.extend(["-i", str(clip["path"])])

        if audio_path:
            cmd.extend(["-i", str(audio_path)])

        # 添加滤镜
        cmd.extend(["-filter_complex", filter_complex])

        # 输出设置
        cmd.extend([
            "-s", resolution,
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ])

        rc, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=1800,
        )

        duration = time.time() - start

        if rc != 0:
            return EngineResult(
                success=False,
                error=f"Compose failed: {stderr[:1000]}",
                duration_seconds=duration,
            )

        return EngineResult(
            success=True,
            output_path=output_path,
            metadata={
                "clip_count": len(clips),
                "transitions": transitions,
                "resolution": resolution,
                "fps": fps,
            },
            duration_seconds=duration,
        )

    def _build_filter_complex(self, clips: List[Dict], transitions: str) -> str:
        """构建FFmpeg滤镜图。"""
        parts = []
        current_offset = 0.0

        for i, clip in enumerate(clips):
            duration = clip.get("duration", 5.0)
            start = clip.get("start", 0.0)

            # 缩放+裁剪到统一尺寸
            parts.append(
                f"[{i}:v]trim=start={start}:duration={duration},"
                f"setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=decrease,"
                f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2[v{i}];"
            )

            current_offset += duration

        # 连接片段
        concat_inputs = "".join(f"[v{i}]" for i in range(len(clips)))
        parts.append(
            f"{concat_inputs}concat=n={len(clips)}:v=1:a=0[outv]"
        )

        return "".join(parts)

    # ------------------------------------------------------------------
    # 引擎信息
    # ------------------------------------------------------------------

    def get_info(self) -> dict:
        """返回引擎信息。"""
        return {
            "name": self.name,
            "om_root": str(self.om_root),
            "om_exists": self.om_root.exists(),
            "capabilities": [
                "search_stock",
                "auto_reframe",
                "compose_video",
            ],
            "china_friendly_sources": [
                "wikimedia", "archive_org", "nasa", "noaa", "loc",
            ],
            "api_required_sources": [
                "pexels", "pixabay", "unsplash", "mixkit", "coverr",
            ],
        }