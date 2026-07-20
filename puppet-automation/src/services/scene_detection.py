"""Scene detection service using PySceneDetect."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class SceneDetectionService:
    """Service for video scene detection."""

    def __init__(self):
        self._scenedetect_available = False
        try:
            import scenedetect
            self._scenedetect_available = True
            logger.info("PySceneDetect available")
        except ImportError:
            logger.warning("PySceneDetect not available, falling back to basic detection")

    async def detect_scenes(self, video_path: str | Path, threshold: float = 30.0, min_scene_len: int = 15) -> Dict[str, Any]:
        """Detect scenes in video using PySceneDetect."""
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not self._scenedetect_available:
            return await self._basic_detection(video_path)

        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector

        loop = asyncio.get_event_loop()

        def _detect():
            video = open_video(str(video_path))
            scene_manager = SceneManager()
            scene_manager.add_detector(
                ContentDetector(threshold=threshold, min_scene_len=min_scene_len)
            )
            scene_manager.detect_scenes(video)
            return scene_manager.get_scene_list()

        scene_list = await loop.run_in_executor(None, _detect)

        scenes = []
        for i, scene in enumerate(scene_list):
            start_frame, end_frame = scene
            scenes.append({
                "id": i + 1,
                "start_frame": int(start_frame.get_frames()),
                "end_frame": int(end_frame.get_frames()),
                "start_time": round(start_frame.get_seconds(), 2),
                "end_time": round(end_frame.get_seconds(), 2),
                "duration": round(end_frame.get_seconds() - start_frame.get_seconds(), 2),
            })

        return {
            "total_scenes": len(scenes),
            "scenes": scenes,
            "method": "py_scenedetect",
            "threshold": threshold,
            "min_scene_len": min_scene_len,
        }

    async def _basic_detection(self, video_path: str | Path) -> Dict[str, Any]:
        """Basic scene detection using OpenCV."""
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        scenes = []
        prev_frame = None
        scene_start = 0
        threshold = 30.0

        for i in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break

            if prev_frame is not None:
                diff = cv2.absdiff(frame, prev_frame)
                non_zero = cv2.countNonZero(cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY))
                if non_zero > threshold * frame.shape[0] * frame.shape[1] / 100:
                    scenes.append({
                        "id": len(scenes) + 1,
                        "start_frame": scene_start,
                        "end_frame": i,
                        "start_time": round(scene_start / fps, 2),
                        "end_time": round(i / fps, 2),
                        "duration": round((i - scene_start) / fps, 2),
                    })
                    scene_start = i

            prev_frame = frame.copy()

        if scene_start < total_frames - 1:
            scenes.append({
                "id": len(scenes) + 1,
                "start_frame": scene_start,
                "end_frame": total_frames - 1,
                "start_time": round(scene_start / fps, 2),
                "end_time": round((total_frames - 1) / fps, 2),
                "duration": round((total_frames - 1 - scene_start) / fps, 2),
            })

        cap.release()

        return {
            "total_scenes": len(scenes),
            "scenes": scenes,
            "method": "opencv_basic",
            "duration": round(duration, 2),
            "fps": round(fps, 2),
        }

    async def extract_keyframes(self, video_path: str | Path, scene_threshold: float = 30.0) -> Dict[str, Any]:
        """Extract keyframes from video scenes."""
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        import cv2

        scenes = await self.detect_scenes(video_path, threshold=scene_threshold)
        keyframes = []

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)

        for scene in scenes["scenes"]:
            mid_frame = (scene["start_frame"] + scene["end_frame"]) // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
            ret, frame = cap.read()

            if ret:
                keyframe_path = video_path.parent / f"keyframe_scene_{scene['id']:03d}.jpg"
                cv2.imwrite(str(keyframe_path), frame)
                keyframes.append({
                    "scene_id": scene["id"],
                    "frame_number": mid_frame,
                    "timestamp": round(mid_frame / fps, 2),
                    "path": str(keyframe_path),
                })

        cap.release()

        return {
            "total_keyframes": len(keyframes),
            "keyframes": keyframes,
            "scenes": scenes,
        }
