"""core/shot_detector.py - PySceneDetect 素材镜头边界检测

为导演素材预处理提供镜头切割点检测, 帮助导演理解每个素材的内部结构。
依赖: PySceneDetect 0.7+ (已装) + ffmpeg (项目已装)。

用法:
    from core.shot_detector import detect_shots, material_summary

    shots = detect_shots("source.mp4")
    # [{"start": 0.0, "end": 2.3, "duration": 2.3},
    #  {"start": 2.3, "end": 5.1, "duration": 2.8}, ...]

    summary = material_summary("source.mp4")
    # {"shot_count": 4, "total_duration": 12.5, "avg_shot_duration": 3.125, ...}
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def detect_shots(
    video_path: str,
    threshold: float = 27.0,
    min_scene_len: int = 15,
) -> List[Dict[str, float]]:
    """检测视频中的镜头边界。

    Args:
        video_path: 视频文件路径
        threshold: ContentDetector 阈值(越低越敏感, 默认 27.0)
        min_scene_len: 最小镜头帧数(避免碎片)

    Returns:
        镜头列表, 每项 {"start": 秒, "end": 秒, "duration": 秒}
        文件不存在或检测失败时返回空列表
    """
    p = Path(video_path)
    if not p.exists():
        logger.warning(f"Shot detection: file not found: {video_path}")
        return []

    try:
        from scenedetect import detect, ContentDetector
    except ImportError:
        logger.warning("PySceneDetect not installed, shot detection disabled")
        return []

    try:
        scene_list = detect(
            str(p),
            ContentDetector(threshold=threshold, min_scene_len=min_scene_len),
        )
    except Exception as e:
        logger.warning(f"Shot detection failed for {video_path}: {e}")
        return []

    shots: List[Dict[str, float]] = []
    for scene in scene_list:
        start_sec = scene[0].seconds if hasattr(scene[0], 'seconds') else scene[0].get_seconds()
        end_sec = scene[1].seconds if hasattr(scene[1], 'seconds') else scene[1].get_seconds()
        shots.append({
            "start": round(start_sec, 3),
            "end": round(end_sec, 3),
            "duration": round(end_sec - start_sec, 3),
        })

    # 如果检测不到任何边界, 至少返回整个视频作为一个镜头
    if not shots:
        try:
            from core.frame_sampler import probe_video
            info = probe_video(video_path)
            dur = info.get("duration", 0.0)
            if dur > 0:
                shots.append({"start": 0.0, "end": round(dur, 3), "duration": round(dur, 3)})
        except Exception:
            pass

    return shots


def material_summary(
    video_path: str,
    threshold: float = 27.0,
) -> Dict[str, Any]:
    """素材结构摘要 — 镜头数/总时长/平均镜头时长/最短最长镜头。

    Args:
        video_path: 视频文件路径
        threshold: ContentDetector 阈值

    Returns:
        摘要字典, 文件不存在时返回 {"shot_count": 0, "total_duration": 0}
    """
    shots = detect_shots(video_path, threshold=threshold)
    if not shots:
        return {"shot_count": 0, "total_duration": 0.0, "avg_shot_duration": 0.0}

    durations = [s["duration"] for s in shots]
    total = sum(durations)
    return {
        "shot_count": len(shots),
        "total_duration": round(total, 3),
        "avg_shot_duration": round(total / len(durations), 3),
        "min_shot_duration": round(min(durations), 3),
        "max_shot_duration": round(max(durations), 3),
        "shots": shots,
    }
